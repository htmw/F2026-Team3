import { Router } from 'express'
import { z } from 'zod'
import { config } from '../config.js'
import { many, one, query, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { hashPassword, verifyPassword } from '../lib/crypto.js'
import { badRequest, forbidden, unauthorized } from '../lib/errors.js'
import { publicUser } from '../lib/people.js'
import { DEFAULT_PREFERENCES, mergedPreferences } from '../lib/preferences.js'
import { getSetting } from '../lib/settings.js'
import { requireAuth, SESSION_COOKIE } from '../middleware/auth.js'
import { graduation, loadStudent } from '../services/academics.js'
import { checkEmailDomain, emailSchema, passwordSchema } from './auth.js'

const router = Router()
router.use(requireAuth)

router.get('/me', async (req, res) => {
  const full = await one('SELECT password_hash IS NOT NULL AS has_password, google_sub IS NOT NULL AS google, google_email, totp_enabled, preferences FROM users WHERE id = $1', [req.user.id])
  const security = await getSetting('security')
  const profile = { ...publicUser(req.user), hasPassword: full.has_password, twoStepEnabled: full.totp_enabled }
  if (req.user.role === 'student') {
    const ctx = await loadStudent(req.user.id)
    Object.assign(profile, {
      studentNumber: ctx.user.student_number,
      program: ctx.user.program,
      advisor: ctx.user.advisor_name,
      expectedGraduation: graduation(ctx).label,
    })
  }
  res.json({
    profile,
    google: { available: Boolean(config.google) && security.googleSignIn, connected: full.google, email: full.google_email },
    preferences: mergedPreferences(full.preferences),
  })
})

router.patch('/me', async (req, res) => {
  const body = z.object({
    fullName: z.string().trim().min(1).max(120).optional(),
    preferredName: z.string().trim().max(60).nullable().optional(),
    email: emailSchema.optional(),
  }).strict().parse(req.body)
  if (body.email && body.email !== req.user.email) {
    await checkEmailDomain(body.email)
    if (await one('SELECT 1 FROM users WHERE email = $1 AND id <> $2', [body.email, req.user.id])) throw badRequest('Another account already uses that email.')
  }
  const user = await one(
    `UPDATE users SET full_name = COALESCE($1, full_name),
            preferred_name = CASE WHEN $2::boolean THEN $3 ELSE preferred_name END,
            email = COALESCE($4, email), updated_at = now()
      WHERE id = $5 RETURNING *`,
    [body.fullName ?? null, body.preferredName !== undefined, body.preferredName || null, body.email ?? null, req.user.id])
  await audit(req.user, 'Updated their profile', { req, subjectUserId: req.user.id })
  res.json({ user: publicUser(user) })
})

router.patch('/me/preferences', async (req, res) => {
  const flags = (keys) => z.object(Object.fromEntries(keys.map((k) => [k, z.boolean()]))).partial().strict()
  const body = z.object({
    notify: flags(Object.keys(DEFAULT_PREFERENCES.notify)).optional(),
    ai: flags(Object.keys(DEFAULT_PREFERENCES.ai)).optional(),
    reminderTiming: z.enum(['1 day before', '2 days before', '1 week before']).optional(),
    aiStyle: z.enum(['Concise', 'Detailed']).optional(),
  }).strict().parse(req.body)
  const stored = (await one('SELECT preferences FROM users WHERE id = $1', [req.user.id])).preferences
  const current = mergedPreferences(stored)
  const next = {
    notify: { ...current.notify, ...body.notify },
    ai: { ...current.ai, ...body.ai },
    reminderTiming: body.reminderTiming ?? current.reminderTiming,
    // Stored only once the user picks one, so the school's AI reply style applies until then.
    aiStyle: body.aiStyle ?? stored?.aiStyle,
  }
  // Keep unrelated keys (e.g. a student's class-time preference) that other screens store here.
  await query(`UPDATE users SET preferences = preferences || $1::jsonb, updated_at = now() WHERE id = $2`, [JSON.stringify(next), req.user.id])
  res.json({ preferences: mergedPreferences(next) })
})

router.post('/me/password', async (req, res) => {
  const body = z.object({ currentPassword: z.string().max(128).optional(), newPassword: passwordSchema }).parse(req.body)
  const row = await one('SELECT password_hash FROM users WHERE id = $1', [req.user.id])
  if (row.password_hash && !(await verifyPassword(body.currentPassword ?? '', row.password_hash))) {
    throw badRequest('Your current password is not correct.')
  }
  await transaction(async (db) => {
    await db.query('UPDATE users SET password_hash = $1, updated_at = now() WHERE id = $2', [await hashPassword(body.newPassword), req.user.id])
    // Sign out every other device.
    await db.query('DELETE FROM sessions WHERE user_id = $1 AND id <> $2', [req.user.id, req.sessionId])
  })
  await audit(req.user, 'Changed their password', { req, subjectUserId: req.user.id })
  res.json({ ok: true })
})

router.post('/me/google/connect', (req, res) => {
  if (!config.google) throw badRequest('Google sign-in is not configured on this server.')
  // The browser navigates here; the session cookie identifies whose account to link.
  res.json({ url: `${config.apiUrl}/api/auth/google?intent=connect` })
})

router.delete('/me/google', async (req, res) => {
  const row = await one('SELECT password_hash FROM users WHERE id = $1', [req.user.id])
  if (!row.password_hash) throw badRequest('Set a password first, or you would have no way to sign in.')
  await query('UPDATE users SET google_sub = NULL, google_email = NULL, updated_at = now() WHERE id = $1', [req.user.id])
  await audit(req.user, 'Disconnected their Google account', { req, subjectUserId: req.user.id })
  res.status(204).end()
})

// Everything stored about the signed-in user, as a JSON download.
router.post('/me/export', async (req, res) => {
  const id = req.user.id
  const [user, profile, enrollments, submissions, events, meetings, messages, approvals, activity] = await Promise.all([
    one('SELECT id, email, full_name, preferred_name, role, status, preferences, created_at, last_login_at FROM users WHERE id = $1', [id]),
    one('SELECT * FROM student_profiles WHERE user_id = $1', [id]),
    many('SELECT e.status, e.grade, e.progress_pct, e.absences, e.plan_status, c.code, c.name, t.name AS term FROM enrollments e JOIN courses c ON c.id = e.course_id LEFT JOIN terms t ON t.id = e.term_id WHERE e.student_id = $1', [id]),
    many('SELECT a.title, s.status, s.score, s.submitted_at FROM submissions s JOIN assignments a ON a.id = s.assignment_id WHERE s.student_id = $1', [id]),
    many('SELECT title, type, starts_at, ends_at, location, note FROM events WHERE owner_id = $1', [id]),
    many('SELECT topic, format, status, starts_at, ends_at, student_note FROM meetings WHERE student_id = $1 OR staff_id = $1', [id]),
    many('SELECT conversation_id, body, created_at FROM messages WHERE sender_id = $1', [id]),
    many('SELECT type, title, status, comment, created_at, decided_at FROM approvals WHERE student_id = $1', [id]),
    many('SELECT action, created_at FROM audit_log WHERE subject_user_id = $1 ORDER BY created_at DESC LIMIT 1000', [id]),
  ])
  await audit(req.user, 'Downloaded a copy of their data', { req, subjectUserId: id })
  res.attachment('acadmate-export.json').json({ exportedAt: new Date(), user, profile, enrollments, submissions, events, meetings, messages, approvals, activity })
})

router.delete('/me', async (req, res) => {
  const { password } = z.object({ password: z.string().max(128).optional() }).parse(req.body ?? {})
  if (req.user.role !== 'student') throw forbidden('Staff accounts are closed by an administrator.')
  const row = await one('SELECT password_hash FROM users WHERE id = $1', [req.user.id])
  if (row.password_hash && !(await verifyPassword(password ?? '', row.password_hash))) throw unauthorized('Enter your password to delete your account.')
  await audit(req.user, 'Deleted their account', { req })
  await query('DELETE FROM users WHERE id = $1', [req.user.id])
  res.clearCookie(SESSION_COOKIE, { path: '/' })
  res.status(204).end()
})

// Counts for the sidebar badges.
router.get('/me/badges', async (req, res) => {
  const unread = await one(
    `SELECT count(*) AS n FROM messages x JOIN conversation_members m ON m.conversation_id = x.conversation_id AND m.user_id = $1
      WHERE x.created_at > m.last_read_at AND x.sender_id IS DISTINCT FROM $1`, [req.user.id])
  const badges = { messages: unread.n }
  if (req.user.role === 'student') {
    const ctx = await loadStudent(req.user.id)
    const now = new Date()
    badges.assignments = ctx.work.filter((w) => !['Submitted', 'Graded'].includes(w.status) && w.due_at > now && w.due_at - now <= 10 * 86_400_000).length
  } else if (req.user.role === 'advisor') {
    const counts = await one(
      `SELECT (SELECT count(*) FROM student_profiles WHERE advisor_id = $1) AS advisees,
              (SELECT count(*) FROM approvals WHERE advisor_id = $1 AND status = 'Pending') AS approvals`, [req.user.id])
    Object.assign(badges, counts)
  } else {
    const counts = await one(`SELECT (SELECT count(*) FROM ai_flags WHERE status = 'Open') AS flags`)
    Object.assign(badges, counts)
  }
  res.json({ badges })
})

export default router
