import express, { Router } from 'express'
import { z } from 'zod'
import { many, one, query, transaction } from '../../db/pool.js'
import { audit } from '../../lib/audit.js'
import { parseCsv } from '../../lib/csv.js'
import { badRequest, conflict, notFound } from '../../lib/errors.js'
import { initials } from '../../lib/people.js'
import { timeZone } from '../../lib/settings.js'
import { relativeDay } from '../../lib/time.js'
import { requireRole } from '../../middleware/auth.js'
import { emailSchema, sendInviteEmail, sendResetEmail } from '../auth.js'
import { advisorWorkload } from './overview.js'

const router = Router()
router.use(requireRole('admin'))

const ROLE_LABEL = { student: 'Student', advisor: 'Advisor', admin: 'Admin' }
const STATUS_LABEL = { active: 'Active', invited: 'Invited', deactivated: 'Deactivated' }
const nameFromEmail = (email) => email.split('@')[0].split(/[._-]+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join(' ')

// Creates an invited account with the right profile row. Returns null if the email is already registered.
export async function createInvitedUser(db, { email, name, role, programId = null, advisorId = null, studentNumber = null, department = null, capacity = 40, title = null }) {
  const { rows } = await db.query(
    `INSERT INTO users (email, full_name, role, status) VALUES ($1, $2, $3, 'invited') ON CONFLICT (email) DO NOTHING RETURNING *`,
    [email, name || nameFromEmail(email), role])
  const user = rows[0]
  if (!user) return null
  if (role === 'student') {
    const program = programId ?? (await db.query('SELECT id FROM programs ORDER BY id LIMIT 1')).rows[0]?.id ?? null
    await db.query('INSERT INTO student_profiles (user_id, program_id, advisor_id, student_number) VALUES ($1, $2, $3, $4)', [user.id, program, advisorId, studentNumber])
  } else {
    await db.query('INSERT INTO staff_profiles (user_id, department, capacity, title, bookable) VALUES ($1, $2, $3, $4, $5)',
      [user.id, department, capacity, title ?? (role === 'advisor' ? `Faculty advisor${department ? `, ${department}` : ''}` : 'Administrator'), role === 'advisor'])
  }
  return user
}

const userRow = (u, tz) => ({
  id: u.id, name: u.full_name, email: u.email, av: initials(u.full_name), role: ROLE_LABEL[u.role], status: STATUS_LABEL[u.status],
  dept: u.role === 'student' ? u.program ?? '' : u.department ?? '', advisor: u.advisor_name ?? '', advisorId: u.advisor_id ?? null,
  programId: u.program_id ?? null, studentNumber: u.student_number ?? null,
  last: u.last_login_at ? relativeDay(u.last_login_at, tz) : 'Never', isStudent: u.role === 'student',
})

const USER_SELECT = `
  SELECT u.*, p.program_id, pr.name AS program, p.advisor_id, a.full_name AS advisor_name, p.student_number, s.department
    FROM users u
    LEFT JOIN student_profiles p ON p.user_id = u.id LEFT JOIN programs pr ON pr.id = p.program_id
    LEFT JOIN users a ON a.id = p.advisor_id LEFT JOIN staff_profiles s ON s.user_id = u.id`

router.get('/users', async (req, res) => {
  const q = z.object({
    role: z.enum(['student', 'advisor', 'admin']).optional(),
    status: z.enum(['active', 'invited', 'deactivated']).optional(),
    q: z.string().trim().max(100).optional(),
    page: z.coerce.number().int().min(1).default(1),
    pageSize: z.coerce.number().int().min(1).max(200).default(50),
  }).parse(req.query)
  const where = ['true']
  const params = []
  if (q.role) { params.push(q.role); where.push(`u.role = $${params.length}`) }
  if (q.status) { params.push(q.status); where.push(`u.status = $${params.length}`) }
  if (q.q) { params.push(`%${q.q}%`); where.push(`(u.full_name ILIKE $${params.length} OR u.email ILIKE $${params.length})`) }
  const tz = await timeZone()
  const [rows, total, counts] = await Promise.all([
    many(`${USER_SELECT} WHERE ${where.join(' AND ')} ORDER BY u.role, u.full_name LIMIT ${q.pageSize} OFFSET ${(q.page - 1) * q.pageSize}`, params),
    one(`SELECT count(*) AS n FROM users u WHERE ${where.join(' AND ')}`, params),
    many(`SELECT role, count(*) AS n FROM users GROUP BY role`),
  ])
  const count = (role) => counts.find((c) => c.role === role)?.n ?? 0
  res.json({
    tabs: [
      { label: 'All', count: counts.reduce((s, c) => s + c.n, 0) },
      { label: 'Students', role: 'student', count: count('student') },
      { label: 'Advisors', role: 'advisor', count: count('advisor') },
      { label: 'Admins', role: 'admin', count: count('admin') },
    ],
    rows: rows.map((u) => userRow(u, tz)),
    total: total.n,
    page: q.page,
    pageSize: q.pageSize,
  })
})

router.get('/users/:id', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const user = await one(`${USER_SELECT} WHERE u.id = $1`, [id])
  if (!user) throw notFound('User')
  res.json(userRow(user, await timeZone()))
})

router.patch('/users/:id', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const body = z.object({
    fullName: z.string().trim().min(1).max(120).optional(),
    role: z.enum(['student', 'advisor', 'admin']).optional(),
    status: z.enum(['active', 'deactivated']).optional(),
    advisorId: z.uuid().nullable().optional(),
    programId: z.number().int().positive().optional(),
    studentNumber: z.string().trim().max(40).nullable().optional(),
  }).strict().parse(req.body)
  const user = await one('SELECT * FROM users WHERE id = $1', [id])
  if (!user) throw notFound('User')
  if (id === req.user.id && (body.role && body.role !== 'admin' || body.status === 'deactivated')) {
    throw badRequest("You can't remove your own admin access or deactivate yourself.")
  }
  if (body.status === 'active' && user.status === 'invited') throw badRequest('Invited users become active when they accept their invite.')
  if (body.advisorId) {
    const advisor = await one(`SELECT 1 FROM users WHERE id = $1 AND role = 'advisor' AND status <> 'deactivated'`, [body.advisorId])
    if (!advisor) throw badRequest('Pick an active advisor.')
  }
  const role = body.role ?? user.role

  const changes = []
  await transaction(async (db) => {
    await db.query(
      `UPDATE users SET full_name = COALESCE($1, full_name), role = $2, status = COALESCE($3, status), updated_at = now() WHERE id = $4`,
      [body.fullName ?? null, role, body.status ?? null, id])
    if (role !== user.role) {
      changes.push(`changed role to ${ROLE_LABEL[role]}`)
      if (role === 'student') {
        await db.query(`INSERT INTO student_profiles (user_id, program_id) VALUES ($1, (SELECT id FROM programs ORDER BY id LIMIT 1)) ON CONFLICT DO NOTHING`, [id])
        await db.query('UPDATE users SET totp_enabled = false, totp_secret = NULL WHERE id = $1', [id])
      } else {
        await db.query(`INSERT INTO staff_profiles (user_id, bookable) VALUES ($1, $2) ON CONFLICT DO NOTHING`, [id, role === 'advisor'])
      }
      if (user.role === 'advisor') await db.query('UPDATE student_profiles SET advisor_id = NULL WHERE advisor_id = $1', [id])
    }
    if (role === 'student' && (body.advisorId !== undefined || body.programId || body.studentNumber !== undefined)) {
      await db.query(
        `UPDATE student_profiles SET advisor_id = CASE WHEN $2::boolean THEN $3::uuid ELSE advisor_id END,
                program_id = COALESCE($4, program_id), student_number = CASE WHEN $5::boolean THEN $6 ELSE student_number END
          WHERE user_id = $1`,
        [id, body.advisorId !== undefined, body.advisorId ?? null, body.programId ?? null, body.studentNumber !== undefined, body.studentNumber ?? null])
      if (body.advisorId !== undefined) changes.push('changed advisor')
    }
    if (body.status === 'deactivated') {
      await db.query('DELETE FROM sessions WHERE user_id = $1', [id])
      changes.push('deactivated the account')
    }
    if (body.status === 'active' && user.status === 'deactivated') changes.push('reactivated the account')
    if (body.fullName) changes.push('renamed the account')
  })
  await audit(req.user, `Updated ${user.full_name}: ${changes.join(', ') || 'no changes'}`, { req, target: { type: 'user', id }, subjectUserId: id })
  const updated = await one(`${USER_SELECT} WHERE u.id = $1`, [id])
  res.json(userRow(updated, await timeZone()))
})

router.post('/users/:id/password-reset', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const user = await one('SELECT * FROM users WHERE id = $1', [id])
  if (!user) throw notFound('User')
  if (user.status === 'deactivated') throw badRequest('Reactivate the account first.')
  if (user.status === 'invited') await sendInviteEmail(user)
  else await sendResetEmail(user)
  await audit(req.user, `Sent a ${user.status === 'invited' ? 'new invite' : 'password reset'} to ${user.full_name}`, { req, target: { type: 'user', id }, subjectUserId: id })
  res.json({ ok: true, sent: user.status === 'invited' ? 'invite' : 'reset' })
})

router.post('/invites', async (req, res) => {
  const body = z.object({
    emails: z.array(emailSchema).min(1).max(200),
    role: z.enum(['student', 'advisor', 'admin']),
  }).parse(req.body)
  const invited = []
  const skipped = []
  await transaction(async (db) => {
    for (const email of [...new Set(body.emails)]) {
      const user = await createInvitedUser(db, { email, role: body.role })
      if (!user) { skipped.push(email); continue }
      await sendInviteEmail(user, db)
      invited.push(email)
    }
  })
  await audit(req.user, `Invited ${invited.length} ${body.role}${invited.length === 1 ? '' : 's'}`, { req })
  res.status(201).json({ invited, skipped })
})

// CSV columns: email, name, role (student|advisor|admin), program, advisor_email, student_number
router.post('/imports/users', express.text({ type: ['text/csv', 'text/plain'], limit: '2mb' }), async (req, res) => {
  if (typeof req.body !== 'string' || !req.body.trim()) throw badRequest('Send the CSV file as the request body with Content-Type: text/csv.')
  const rows = parseCsv(req.body)
  if (rows.length === 0) throw badRequest('The CSV has no data rows.')
  if (!('email' in rows[0])) throw badRequest('The CSV needs an "email" column.')
  const programs = await many('SELECT id, name FROM programs')
  const advisors = await many(`SELECT id, email FROM users WHERE role = 'advisor'`)
  const result = { created: 0, updated: 0, errors: [] }

  await transaction(async (db) => {
    for (const [i, row] of rows.entries()) {
      const line = i + 2
      const email = emailSchema.safeParse(row.email)
      const role = (row.role || 'student').toLowerCase()
      if (!email.success) { result.errors.push({ line, message: 'Invalid email' }); continue }
      if (!['student', 'advisor', 'admin'].includes(role)) { result.errors.push({ line, message: `Unknown role "${row.role}"` }); continue }
      const program = row.program ? programs.find((p) => p.name.toLowerCase() === row.program.toLowerCase()) : null
      if (row.program && !program) { result.errors.push({ line, message: `Unknown program "${row.program}"` }); continue }
      const advisor = row.advisor_email ? advisors.find((a) => a.email === row.advisor_email.toLowerCase()) : null
      if (row.advisor_email && !advisor) { result.errors.push({ line, message: `Unknown advisor "${row.advisor_email}"` }); continue }

      const created = await createInvitedUser(db, {
        email: email.data, name: row.name, role, programId: program?.id, advisorId: advisor?.id, studentNumber: row.student_number || null,
      })
      if (created) {
        await sendInviteEmail(created, db)
        result.created++
      } else if (role === 'student') {
        await db.query(
          `UPDATE student_profiles SET program_id = COALESCE($2, program_id), advisor_id = COALESCE($3, advisor_id),
                  student_number = COALESCE($4, student_number)
            WHERE user_id = (SELECT id FROM users WHERE email = $1 AND role = 'student')`,
          [email.data, program?.id ?? null, advisor?.id ?? null, row.student_number || null])
        result.updated++
      }
    }
    await db.query(
      `UPDATE integrations SET last_sync_at = now(), log = jsonb_build_array(jsonb_build_object('a', $1::text, 'b', now())) || log WHERE id = 'csv'`,
      [`Imported ${result.created} new and ${result.updated} updated users`])
  })
  await audit(req.user, `Imported users from a CSV file (${result.created} new, ${result.updated} updated)`, { req })
  res.json(result)
})

// ------------------------------------------------------------------ advisors

router.get('/advisors', async (req, res) => {
  const rows = await advisorWorkload()
  res.json({
    rows: rows.map((a) => ({
      id: a.id, name: a.full_name, dept: a.department ?? '', load: a.load, cap: a.capacity, pending: a.pending, status: a.status,
      resp: a.resp == null ? '—' : `${a.resp} days`, loadLabel: a.load > a.capacity ? 'Over capacity' : a.load >= a.capacity * 0.9 ? 'Near capacity' : 'OK',
    })),
  })
})

router.post('/advisors', async (req, res) => {
  const body = z.object({
    name: z.string().trim().min(1).max(120),
    email: emailSchema,
    department: z.string().trim().min(1).max(120),
    capacity: z.number().int().min(0).max(500).default(40),
  }).parse(req.body)
  const user = await transaction(async (db) => {
    const created = await createInvitedUser(db, { email: body.email, name: body.name, role: 'advisor', department: body.department, capacity: body.capacity })
    if (!created) throw conflict('An account with that email already exists.')
    await sendInviteEmail(created, db)
    return created
  })
  await audit(req.user, `Added advisor ${body.name}`, { req, target: { type: 'user', id: user.id }, subjectUserId: user.id })
  res.status(201).json({ id: user.id, name: user.full_name, email: user.email, status: 'Invited' })
})

router.patch('/advisors/:id', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const body = z.object({ department: z.string().trim().max(120).optional(), capacity: z.number().int().min(0).max(500).optional() }).strict().parse(req.body)
  const row = await one(
    `UPDATE staff_profiles SET department = COALESCE($2, department), capacity = COALESCE($3, capacity)
      WHERE user_id = $1 AND user_id IN (SELECT id FROM users WHERE role = 'advisor') RETURNING *`,
    [id, body.department ?? null, body.capacity ?? null])
  if (!row) throw notFound('Advisor')
  res.json({ id, department: row.department, capacity: row.capacity })
})

// Moves advisees to another advisor: the listed students, or `count` of them (by default enough to get back under capacity).
router.post('/advisors/:id/reassign', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const body = z.object({
    targetId: z.uuid(),
    studentIds: z.array(z.uuid()).max(500).optional(),
    count: z.number().int().min(1).max(500).optional(),
  }).parse(req.body)
  if (body.targetId === id) throw badRequest('Pick a different advisor to move advisees to.')
  const [from, to] = await Promise.all([
    one(`SELECT u.full_name, s.capacity FROM users u JOIN staff_profiles s ON s.user_id = u.id WHERE u.id = $1 AND u.role = 'advisor'`, [id]),
    one(`SELECT u.full_name, s.capacity FROM users u JOIN staff_profiles s ON s.user_id = u.id WHERE u.id = $1 AND u.role = 'advisor' AND u.status <> 'deactivated'`, [body.targetId]),
  ])
  if (!from || !to) throw notFound('Advisor')

  const moved = await transaction(async (db) => {
    let ids = body.studentIds
    if (!ids) {
      const { rows } = await db.query(
        `SELECT p.user_id FROM student_profiles p JOIN users u ON u.id = p.user_id
          WHERE p.advisor_id = $1 AND u.status <> 'deactivated' ORDER BY u.full_name`, [id])
      const count = body.count ?? Math.max(0, rows.length - from.capacity)
      if (count === 0) throw badRequest('This advisor is within capacity. Say how many advisees to move.')
      ids = rows.slice(0, count).map((r) => r.user_id)
    }
    const { rows } = await db.query(
      `UPDATE student_profiles SET advisor_id = $1 WHERE advisor_id = $2 AND user_id = ANY($3) RETURNING user_id`, [body.targetId, id, ids])
    // Pending approvals follow the student to the new advisor.
    await db.query(`UPDATE approvals SET advisor_id = $1 WHERE status = 'Pending' AND student_id = ANY($2)`, [body.targetId, rows.map((r) => r.user_id)])
    return rows.length
  })
  await audit(req.user, `Reassigned ${moved} advisee${moved === 1 ? '' : 's'} from ${from.full_name} to ${to.full_name}`, { req, target: { type: 'user', id } })
  res.json({ moved, from: from.full_name, to: to.full_name })
})

export default router
