import { Router } from 'express'
import { z } from 'zod'
import { one, query, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { badRequest, conflict, notFound } from '../lib/errors.js'
import { shortName } from '../lib/people.js'
import { timeZone } from '../lib/settings.js'
import { requireRole } from '../middleware/auth.js'
import { loadStudent, precheck } from '../services/academics.js'
import { notify } from '../services/notify.js'
import { assignmentRow } from './students.js'

const router = Router()
router.use(requireRole('student'))

// The assignment as this student sees it, or 404 if it isn't theirs (not their course, or another student's form).
async function loadOwn(req) {
  const id = z.uuid().parse(req.params.id)
  const ctx = await loadStudent(req.user.id)
  const work = ctx?.work.find((w) => w.id === id)
  if (!work) throw notFound('Assignment')
  const detail = await one(
    `SELECT a.description, a.steps, COALESCE(s.steps_done, '{}') AS steps_done FROM assignments a
       LEFT JOIN submissions s ON s.assignment_id = a.id AND s.student_id = $2 WHERE a.id = $1`, [id, req.user.id])
  return { ctx, work, detail }
}

router.get('/:id', async (req, res) => {
  const { work, detail } = await loadOwn(req)
  const tz = await timeZone()
  res.json({
    ...assignmentRow(work, tz, detail.steps.map((text, i) => ({ id: i, text, done: detail.steps_done.includes(i) }))),
    desc: detail.description ?? '',
  })
})

// Track progress: move between "To do" and "In progress" and tick off steps.
router.patch('/:id/progress', async (req, res) => {
  const body = z.object({
    status: z.enum(['To do', 'In progress']).optional(),
    stepsDone: z.array(z.number().int().min(0).max(50)).max(50).optional(),
  }).parse(req.body)
  const { work, detail } = await loadOwn(req)
  if (['Submitted', 'Graded'].includes(work.status)) throw conflict('This assignment is already submitted.')
  const steps = body.stepsDone ? [...new Set(body.stepsDone)].filter((i) => i < detail.steps.length).sort((a, b) => a - b) : detail.steps_done
  const status = body.status ?? (steps.length ? 'In progress' : work.status)
  await query(
    `INSERT INTO submissions (assignment_id, student_id, status, steps_done) VALUES ($1, $2, $3, $4)
     ON CONFLICT (assignment_id, student_id) DO UPDATE SET status = EXCLUDED.status, steps_done = EXCLUDED.steps_done, updated_at = now()`,
    [work.id, req.user.id, status, steps],
  )
  res.json({ id: work.id, status, stepsDone: steps })
})

// Mark as submitted. Forms (e.g. capstone pre-approval) also go to the advisor as an approval.
router.post('/:id/submit', async (req, res) => {
  const body = z.object({ fields: z.record(z.string().max(60), z.string().max(4000)).optional() }).parse(req.body ?? {})
  const { ctx, work } = await loadOwn(req)
  if (['Submitted', 'Graded'].includes(work.status)) throw conflict('This assignment is already submitted.')
  if (work.type === 'Form' && (!body.fields || Object.keys(body.fields).length === 0)) throw badRequest('Fill in the form fields before submitting.')
  if (work.type === 'Form' && !ctx.user.advisor_id) throw badRequest("You don't have an assigned advisor yet. Contact your department.")

  const approval = work.type === 'Form'
    ? { type: 'Form', title: work.title, payload: { assignmentId: work.id, fields: body.fields } }
    : null
  const check = approval ? await precheck(ctx, approval, { tz: await timeZone() }) : null

  await transaction(async (db) => {
    await db.query(
      `INSERT INTO submissions (assignment_id, student_id, status, submitted_at) VALUES ($1, $2, 'Submitted', now())
       ON CONFLICT (assignment_id, student_id) DO UPDATE SET status = 'Submitted', submitted_at = now(), updated_at = now()`,
      [work.id, req.user.id],
    )
    if (approval) {
      await db.query(
        `INSERT INTO approvals (student_id, advisor_id, type, title, lines, payload, precheck_ok, precheck_text)
         VALUES ($1, $2, 'Form', $3, $4, $5, $6, $7)`,
        [req.user.id, ctx.user.advisor_id, approval.title,
          JSON.stringify(Object.entries(body.fields).map(([a, b]) => ({ a, b: b.trim() || 'Missing' }))),
          JSON.stringify({ ...approval.payload, checks: check.checks }), check.ok, check.text],
      )
      await notify(ctx.user.advisor_id, `${shortName(ctx.user.full_name)} submitted the ${work.title}.`, db)
    }
  })
  await audit(req.user, `Submitted ${work.title}`, { req, target: { type: 'assignment', id: work.id }, subjectUserId: req.user.id })
  res.json({ id: work.id, status: 'Submitted', precheck: check })
})

export default router
