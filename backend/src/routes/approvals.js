import { Router } from 'express'
import { z } from 'zod'
import { many, one, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { badRequest, conflict, notFound } from '../lib/errors.js'
import { initials, shortName } from '../lib/people.js'
import { timeZone } from '../lib/settings.js'
import { localDate, shortDate } from '../lib/time.js'
import { requireRole } from '../middleware/auth.js'
import { loadStudent, precheck } from '../services/academics.js'
import { notify } from '../services/notify.js'

const router = Router()
router.use(requireRole('advisor', 'admin'))

const STATUSES = ['Pending', 'Approved', 'Changes requested']

function view(a, tz) {
  return {
    id: a.id, studentId: a.student_id, name: shortName(a.full_name), av: initials(a.full_name), type: a.type, item: a.title,
    when: shortDate(localDate(a.created_at, tz)), createdAt: a.created_at, status: a.status, ok: a.precheck_ok, check: a.precheck_text,
    checkShort: a.precheck_ok == null ? 'Not checked' : a.precheck_ok ? 'Pre-check passed' : 'Needs a look',
    checks: a.payload.checks ?? [], lines: a.lines, comment: a.comment, decidedAt: a.decided_at,
  }
}

// Advisors see approvals for their own advisees; admins see all.
async function loadApproval(req) {
  const id = z.coerce.number().int().positive().parse(req.params.id)
  const row = await one(`SELECT a.*, u.full_name FROM approvals a JOIN users u ON u.id = a.student_id WHERE a.id = $1`, [id])
  if (!row || (req.user.role === 'advisor' && row.advisor_id !== req.user.id)) throw notFound('Approval')
  return row
}

router.get('/', async (req, res) => {
  const { status } = z.object({ status: z.enum(STATUSES).default('Pending') }).parse(req.query)
  const scope = req.user.role === 'advisor' ? 'AND a.advisor_id = $2' : ''
  const params = req.user.role === 'advisor' ? [status, req.user.id] : [status]
  const tz = await timeZone()
  const [rows, counts] = await Promise.all([
    many(`SELECT a.*, u.full_name FROM approvals a JOIN users u ON u.id = a.student_id WHERE a.status = $1 ${scope} ORDER BY a.created_at`, params),
    many(`SELECT a.status, count(*) AS n FROM approvals a WHERE true ${req.user.role === 'advisor' ? 'AND a.advisor_id = $1' : ''} GROUP BY a.status`,
      req.user.role === 'advisor' ? [req.user.id] : []),
  ])
  res.json({
    tabs: STATUSES.map((label) => ({ label, count: counts.find((c) => c.status === label)?.n ?? 0 })),
    rows: rows.map((a) => view(a, tz)),
  })
})

router.get('/:id', async (req, res) => {
  res.json(view(await loadApproval(req), await timeZone()))
})

// Applies (or undoes) the effect of a decision on the student's record.
async function applyDecision(db, approval, decision) {
  const p = approval.payload
  if (approval.type === 'Course plan') {
    const status = decision === 'Approved' ? 'Approved' : decision === 'Pending' ? 'Pending approval' : 'Needs approval'
    await db.query(`UPDATE enrollments SET plan_status = $1 WHERE id = ANY($2) AND status = 'planned'`, [status, p.enrollmentIds ?? []])
  } else if (approval.type === 'Request' && p.action === 'drop') {
    await db.query(`UPDATE enrollments SET status = $1 WHERE id = $2`, [decision === 'Approved' ? 'dropped' : 'current', p.enrollmentId])
  } else if (approval.type === 'Form' && p.assignmentId) {
    const status = decision === 'Approved' ? 'Graded' : decision === 'Pending' ? 'Submitted' : 'In progress'
    await db.query(`UPDATE submissions SET status = $1, updated_at = now() WHERE assignment_id = $2 AND student_id = $3`, [status, p.assignmentId, approval.student_id])
  }
}

async function decide(req, res, decision) {
  const { comment } = z.object({
    comment: decision === 'Changes requested'
      ? z.string().trim().min(1, 'Add a comment so the student knows what to change.').max(2000)
      : z.string().trim().max(2000).optional(),
  }).parse(req.body ?? {})
  const approval = await loadApproval(req)
  if (approval.status !== 'Pending') throw conflict(`This item is already ${approval.status.toLowerCase()}. Reopen it first.`)

  await transaction(async (db) => {
    await db.query(
      `UPDATE approvals SET status = $1, comment = $2, decided_by = $3, decided_at = now() WHERE id = $4`,
      [decision, comment || null, req.user.id, approval.id])
    await applyDecision(db, approval, decision)
    await notify(approval.student_id, decision === 'Approved'
      ? `${req.user.full_name} approved your ${approval.title}.${comment ? ` "${comment}"` : ''}`
      : `${req.user.full_name} requested changes to your ${approval.title}: "${comment}"`, db)
  })
  await audit(req.user, `${decision === 'Approved' ? 'Approved' : 'Requested changes on'} ${approval.title} for ${shortName(approval.full_name)}`,
    { req, target: { type: 'approval', id: approval.id }, subjectUserId: approval.student_id })
  res.json(view(await loadApproval(req), await timeZone()))
}

router.post('/:id/approve', (req, res) => decide(req, res, 'Approved'))
router.post('/:id/request-changes', (req, res) => decide(req, res, 'Changes requested'))

router.post('/:id/reopen', async (req, res) => {
  const approval = await loadApproval(req)
  if (approval.status === 'Pending') throw badRequest('This item is already open.')
  const ctx = await loadStudent(approval.student_id)
  // Re-run the pre-check: the student's record may have changed since the first decision.
  const check = await precheck(ctx, approval, { tz: await timeZone() })
  await transaction(async (db) => {
    await db.query(
      `UPDATE approvals SET status = 'Pending', decided_by = NULL, decided_at = NULL, precheck_ok = $2, precheck_text = $3,
              payload = payload || jsonb_build_object('checks', $4::jsonb) WHERE id = $1`,
      [approval.id, check.ok, check.text, JSON.stringify(check.checks)])
    await applyDecision(db, approval, 'Pending')
  })
  await audit(req.user, `Reopened ${approval.title} for ${shortName(approval.full_name)}`, { req, target: { type: 'approval', id: approval.id }, subjectUserId: approval.student_id })
  res.json(view(await loadApproval(req), await timeZone()))
})

export default router
