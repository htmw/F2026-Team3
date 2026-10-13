import { Router } from 'express'
import { z } from 'zod'
import { many, one } from '../db/pool.js'
import { notFound } from '../lib/errors.js'
import { shortDate } from '../lib/time.js'
import { requireAuth, requireRole } from '../middleware/auth.js'

const router = Router()

// Grade breakdown for one of the signed-in student's courses (current, or the most recent attempt).
router.get('/courses/:id/grades', requireRole('student'), async (req, res) => {
  const courseId = z.coerce.number().int().positive().parse(req.params.id)
  const enrollment = await one(
    `SELECT e.*, c.code, c.name, t.name AS term FROM enrollments e JOIN courses c ON c.id = e.course_id
       LEFT JOIN terms t ON t.id = e.term_id
      WHERE e.student_id = $1 AND e.course_id = $2 AND e.status IN ('current', 'completed')
      ORDER BY t.starts_on DESC LIMIT 1`, [req.user.id, courseId])
  if (!enrollment) throw notFound('Course enrollment')
  const parts = await many('SELECT * FROM grade_components WHERE enrollment_id = $1 ORDER BY sort_order, id', [enrollment.id])
  const graded = parts.filter((p) => p.score != null)
  const weight = graded.reduce((s, p) => s + p.weight, 0)
  res.json({
    courseId, code: enrollment.code, name: enrollment.name, term: enrollment.term, status: enrollment.status,
    grade: enrollment.grade ?? '—', progressPct: enrollment.progress_pct,
    weightedScore: weight ? Math.round(graded.reduce((s, p) => s + p.score * p.weight, 0) / weight) : null,
    parts: parts.map((p) => ({
      label: p.label, weight: p.weight, score: p.score, dueOn: p.due_on,
      display: p.score != null ? `${p.score}%` : p.due_on ? shortDate(p.due_on) : 'In progress',
    })),
  })
})

// The latest published catalog, readable by anyone signed in.
router.get('/catalog', requireAuth, async (req, res) => {
  const row = await one('SELECT snapshot, published_at FROM catalog_versions ORDER BY id DESC LIMIT 1')
  if (!row) throw notFound('Published catalog')
  res.json({ publishedAt: row.published_at, ...row.snapshot })
})

export default router
