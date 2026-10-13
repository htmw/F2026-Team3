import { Router } from 'express'
import { z } from 'zod'
import { many, one } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { notFound } from '../lib/errors.js'
import { initials, shortName } from '../lib/people.js'
import { timeZone } from '../lib/settings.js'
import { localDate, localTime, relativeDay, shortDate } from '../lib/time.js'
import { mergedPreferences } from '../lib/preferences.js'
import { requireRole } from '../middleware/auth.js'
import { CREDITS_PER_COURSE, adviseeStatus, credits, degreeAudit, gpaTrend, graduation, loadStudent, onTime, riskFlags } from '../services/academics.js'
import { toMessage } from './studentAi.js'

// Mounted at /api/students ahead of the student-only router; only matches /:uuid/... paths.
const router = Router()
const staff = requireRole('advisor', 'admin')

// An advisor may only open their own advisees; admins may open anyone.
export async function accessibleStudent(req, id) {
  const ctx = await loadStudent(id)
  if (!ctx || (req.user.role === 'advisor' && ctx.user.advisor_id !== req.user.id)) throw notFound('Student')
  return ctx
}

router.get('/:id/record', staff, async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const ctx = await accessibleStudent(req, id)
  const tz = await timeZone()
  const trend = gpaTrend(ctx)
  const credit = credits(ctx)
  const ontime = onTime(ctx)
  const grad = graduation(ctx)
  const audit = degreeAudit(ctx)
  const [approval, notes, meetings, activity] = await Promise.all([
    one(`SELECT * FROM approvals WHERE student_id = $1 ORDER BY (status = 'Pending') DESC, created_at DESC LIMIT 1`, [id]),
    many(`SELECT n.*, u.full_name AS author FROM advisor_notes n LEFT JOIN users u ON u.id = n.author_id WHERE n.student_id = $1 ORDER BY n.created_at DESC`, [id]),
    many(`SELECT * FROM meetings WHERE student_id = $1 AND status IN ('confirmed', 'requested') AND starts_at > now() ORDER BY starts_at LIMIT 5`, [id]),
    many(`SELECT action, created_at FROM audit_log WHERE subject_user_id = $1 ORDER BY created_at DESC LIMIT 10`, [id]),
  ])

  res.json({
    student: {
      id, name: ctx.user.full_name, shortName: shortName(ctx.user.full_name), av: initials(ctx.user.full_name),
      email: ctx.user.email, program: ctx.user.program, studentNumber: ctx.user.student_number, advisor: ctx.user.advisor_name,
      status: adviseeStatus(ctx), preference: ctx.user.preferences?.classTime ?? null,
    },
    stats: [
      { label: 'Cumulative GPA', value: trend.cumulative?.toFixed(2) ?? '—', note: trend.change == null ? 'No change data' : `${trend.change >= 0 ? 'Up' : 'Down'} ${Math.abs(trend.change).toFixed(2)} from last term`, tag: trend.cumulative >= 3 ? 'On track' : 'Watch' },
      { label: 'Credits', value: `${credit.earned} / ${credit.total}`, note: `${credit.inProgress} in progress · ${grad.remaining * CREDITS_PER_COURSE} left after this term`, tag: `${credit.total ? Math.round((credit.earned / credit.total) * 100) : 0}%` },
      { label: 'On-time submission', value: ontime.pct == null ? '—' : `${ontime.pct}%`, note: `${ontime.onTime} of ${ontime.total} on time`, tag: ontime.pct >= 90 ? 'Good' : 'Watch' },
      { label: 'Expected graduation', value: grad.label, note: grad.confirmed ? 'Plan approved' : 'If the pending plan is approved', tag: grad.confirmed ? 'Confirmed' : 'Pending' },
    ],
    approval: approval && {
      id: approval.id, type: approval.type, title: approval.title, status: approval.status, lines: approval.lines,
      ok: approval.precheck_ok, check: approval.precheck_text, checks: approval.payload.checks ?? [], comment: approval.comment,
      when: shortDate(localDate(approval.created_at, tz)),
    },
    flags: riskFlags(ctx),
    reqs: audit.map((g) => ({ label: g.name, count: g.inProgress ? `${g.done} of ${g.required} · ${g.inProgress} in progress` : `${g.done} of ${g.required}` })),
    notes: notes.map((n) => ({ id: n.id, text: n.body, author: n.author, when: shortDate(localDate(n.created_at, tz)) })),
    meet: meetings.map((m) => ({ id: m.id, title: m.topic, status: m.status, meta: `${relativeDay(m.starts_at, tz)} · ${localTime(m.starts_at, tz)} · ${m.format}` })),
    activity: activity.map((a) => ({ when: shortDate(localDate(a.created_at, tz)), text: a.action })),
  })
})

router.post('/:id/notes', staff, async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const { text } = z.object({ text: z.string().trim().min(1, 'Write a note first.').max(5000) }).parse(req.body)
  const ctx = await accessibleStudent(req, id)
  const note = await one(`INSERT INTO advisor_notes (student_id, author_id, body) VALUES ($1, $2, $3) RETURNING *`, [id, req.user.id, text])
  await audit(req.user, `Added a private note on ${shortName(ctx.user.full_name)}`, { req, target: { type: 'note', id: note.id } })
  res.status(201).json({ id: note.id, text: note.body, author: req.user.full_name, when: shortDate(localDate(note.created_at, await timeZone())) })
})

// A student's AI advisor conversations, read-only, only when the student chose to share them
// (Settings → "Share AI plans with my advisor").
router.get('/:id/ai/threads', staff, async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const ctx = await accessibleStudent(req, id)
  if (!mergedPreferences(ctx.user.preferences).ai.shareWithAdvisor) return res.json({ shared: false, threads: [] })
  const [threads, messages] = await Promise.all([
    many('SELECT * FROM ai_threads WHERE student_id = $1 ORDER BY updated_at DESC LIMIT 50', [id]),
    many(`SELECT m.* FROM ai_messages m JOIN ai_threads t ON t.id = m.thread_id WHERE t.student_id = $1 ORDER BY m.id`, [id]),
  ])
  await audit(req.user, `Viewed the AI advisor history of ${shortName(ctx.user.full_name)}`, { req, subjectUserId: id })
  res.json({
    shared: true,
    threads: threads.map((t) => ({
      id: t.id, title: t.title, updatedAt: t.updated_at,
      messages: messages.filter((m) => m.thread_id === t.id).map(toMessage),
    })),
  })
})

export default router
