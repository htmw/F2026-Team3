import express, { Router } from 'express'
import { z } from 'zod'
import { many, one, transaction } from '../../db/pool.js'
import { audit } from '../../lib/audit.js'
import { parseCsv } from '../../lib/csv.js'
import { badRequest, notFound } from '../../lib/errors.js'
import { requireRole } from '../../middleware/auth.js'
import { CREDITS_PER_COURSE } from '../../services/academics.js'
import { emailSchema } from '../auth.js'

const router = Router()
router.use(requireRole('admin'))

const TYPES = ['Foundation', 'Core', 'Elective', 'Capstone']
const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Use a YYYY-MM-DD date.')
const codeParam = (req) => z.string().trim().min(1).max(20).parse(decodeURIComponent(req.params.code))

const COURSE_SELECT = `
  SELECT c.*, COALESCE(array_agg(p.code ORDER BY p.code) FILTER (WHERE p.code IS NOT NULL), '{}') AS prereqs
    FROM courses c LEFT JOIN course_prerequisites cp ON cp.course_id = c.id LEFT JOIN courses p ON p.id = cp.prereq_id`

const courseView = (c) => ({
  id: c.id, code: c.code, name: c.name, type: c.type, credits: c.credits, offered: c.offered,
  offerTerm: c.offer_term, offer: c.offered ? c.offer_term ?? 'Offered' : 'Not offered', prereqs: c.prereqs,
})

async function setPrereqs(db, courseId, codes) {
  await db.query('DELETE FROM course_prerequisites WHERE course_id = $1', [courseId])
  if (!codes.length) return
  const { rows } = await db.query('SELECT id, code FROM courses WHERE code = ANY($1)', [codes])
  const unknown = codes.filter((code) => !rows.some((r) => r.code === code))
  if (unknown.length) throw badRequest(`Unknown prerequisite course: ${unknown.join(', ')}`)
  if (rows.some((r) => r.id === courseId)) throw badRequest("A course can't be its own prerequisite.")
  for (const r of rows) await db.query('INSERT INTO course_prerequisites (course_id, prereq_id) VALUES ($1, $2)', [courseId, r.id])
}

const courseBody = z.object({
  code: z.string().trim().min(2).max(20),
  name: z.string().trim().min(1).max(200),
  type: z.enum(TYPES),
  credits: z.number().int().min(1).max(12).default(3),
  offered: z.boolean().default(true),
  offerTerm: z.string().trim().max(40).nullable().optional(),
  prereqs: z.array(z.string().trim().min(1).max(20)).max(10).default([]),
})

router.get('/courses', async (req, res) => {
  const q = z.object({ q: z.string().trim().max(100).optional(), type: z.enum(TYPES).optional() }).parse(req.query)
  const rows = await many(
    `${COURSE_SELECT} WHERE ($1::text IS NULL OR c.code ILIKE $1 OR c.name ILIKE $1) AND ($2::text IS NULL OR c.type = $2)
     GROUP BY c.id ORDER BY c.code`, [q.q ? `%${q.q}%` : null, q.type ?? null])
  res.json({ courses: rows.map(courseView), types: TYPES })
})

router.post('/courses', async (req, res) => {
  const body = courseBody.parse(req.body)
  const course = await transaction(async (db) => {
    const { rows } = await db.query(
      `INSERT INTO courses (code, name, type, credits, offered, offer_term) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
      [body.code, body.name, body.type, body.credits, body.offered, body.offerTerm ?? null])
    await setPrereqs(db, rows[0].id, body.prereqs)
    return rows[0]
  })
  await audit(req.user, `Added course ${body.code} to the catalog`, { req, target: { type: 'course', id: body.code } })
  res.status(201).json(courseView(await one(`${COURSE_SELECT} WHERE c.id = $1 GROUP BY c.id`, [course.id])))
})

router.get('/courses/:code', async (req, res) => {
  const course = await one(`${COURSE_SELECT} WHERE c.code = $1 GROUP BY c.id`, [codeParam(req)])
  if (!course) throw notFound('Course')
  res.json(courseView(course))
})

router.patch('/courses/:code', async (req, res) => {
  const code = codeParam(req)
  const body = courseBody.omit({ code: true }).partial().strict().parse(req.body)
  const course = await one('SELECT * FROM courses WHERE code = $1', [code])
  if (!course) throw notFound('Course')
  await transaction(async (db) => {
    await db.query(
      `UPDATE courses SET name = COALESCE($2, name), type = COALESCE($3, type), credits = COALESCE($4, credits),
              offered = COALESCE($5, offered), offer_term = CASE WHEN $6::boolean THEN $7 ELSE offer_term END, updated_at = now()
        WHERE id = $1`,
      [course.id, body.name ?? null, body.type ?? null, body.credits ?? null, body.offered ?? null, body.offerTerm !== undefined, body.offerTerm ?? null])
    if (body.prereqs) await setPrereqs(db, course.id, body.prereqs)
  })
  const changes = Object.keys(body).map((k) => (k === 'offered' ? (body.offered ? 'offered' : 'not offered') : k)).join(', ')
  await audit(req.user, `Changed ${code} (${changes})`, { req, target: { type: 'course', id: code } })
  res.json(courseView(await one(`${COURSE_SELECT} WHERE c.id = $1 GROUP BY c.id`, [course.id])))
})

// ------------------------------------------------------------------ programs & requirements

async function programView(id) {
  const program = await one('SELECT * FROM programs WHERE id = $1', [id])
  if (!program) throw notFound('Program')
  const groups = await many('SELECT * FROM requirement_groups WHERE program_id = $1 ORDER BY sort_order, id', [id])
  return {
    id: program.id, name: program.name,
    requirements: groups.map((g) => ({ id: g.id, name: g.name, courseType: g.course_type, requiredCount: g.required_count })),
    totalCredits: groups.reduce((s, g) => s + g.required_count, 0) * CREDITS_PER_COURSE,
  }
}

router.get('/programs', async (req, res) => {
  const programs = await many('SELECT id FROM programs ORDER BY id')
  res.json({ programs: await Promise.all(programs.map((p) => programView(p.id))) })
})

router.get('/programs/:id/requirements', async (req, res) => {
  res.json(await programView(z.coerce.number().int().positive().parse(req.params.id)))
})

router.put('/programs/:id/requirements', async (req, res) => {
  const id = z.coerce.number().int().positive().parse(req.params.id)
  const { groups } = z.object({
    groups: z.array(z.object({
      courseType: z.enum(TYPES),
      name: z.string().trim().min(1).max(60).optional(),
      requiredCount: z.number().int().min(0).max(30),
    })).min(1).max(4),
  }).parse(req.body)
  if (new Set(groups.map((g) => g.courseType)).size !== groups.length) throw badRequest('Each course type can appear only once.')
  const before = await programView(id)
  await transaction(async (db) => {
    for (const [i, g] of groups.entries()) {
      await db.query(
        `INSERT INTO requirement_groups (program_id, name, course_type, required_count, sort_order) VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (program_id, course_type) DO UPDATE SET required_count = EXCLUDED.required_count,
           name = COALESCE($6, requirement_groups.name), sort_order = EXCLUDED.sort_order`,
        [id, g.name ?? (g.courseType === 'Elective' ? 'Electives' : g.courseType), g.courseType, g.requiredCount, i, g.name ?? null])
    }
  })
  const after = await programView(id)
  await audit(req.user, `Changed degree requirements for ${after.name} (${before.totalCredits} → ${after.totalCredits} credits)`, { req, target: { type: 'program', id } })
  res.json(after)
})

// ------------------------------------------------------------------ terms

const termView = (t) => ({
  id: t.id, name: t.name, startsOn: t.starts_on, endsOn: t.ends_on, isCurrent: t.is_current,
  dates: [
    { id: 'registrationOpens', label: 'Registration opens', value: t.registration_opens },
    { id: 'lastAdd', label: 'Last day to add', value: t.last_add },
    { id: 'lastDrop', label: 'Last day to drop', value: t.last_drop },
    { id: 'classesBegin', label: 'Classes begin', value: t.classes_begin },
  ],
})

router.get('/terms', async (req, res) => {
  res.json({ terms: (await many('SELECT * FROM terms ORDER BY starts_on')).map(termView) })
})

router.get('/terms/:id/dates', async (req, res) => {
  const term = await one('SELECT * FROM terms WHERE id = $1', [z.coerce.number().int().positive().parse(req.params.id)])
  if (!term) throw notFound('Term')
  res.json(termView(term))
})

router.put('/terms/:id/dates', async (req, res) => {
  const id = z.coerce.number().int().positive().parse(req.params.id)
  const body = z.object({
    registrationOpens: date.nullable(), lastAdd: date.nullable(), lastDrop: date.nullable(), classesBegin: date.nullable(),
  }).parse(req.body)
  if (body.lastAdd && body.lastDrop && body.lastDrop < body.lastAdd) throw badRequest('The last day to drop must be after the last day to add.')
  const term = await one(
    `UPDATE terms SET registration_opens = $2, last_add = $3, last_drop = $4, classes_begin = $5 WHERE id = $1 RETURNING *`,
    [id, body.registrationOpens, body.lastAdd, body.lastDrop, body.classesBegin])
  if (!term) throw notFound('Term')
  await audit(req.user, `Updated ${term.name} dates`, { req, target: { type: 'term', id } })
  res.json(termView(term))
})

router.post('/catalog/publish', async (req, res) => {
  const [courses, programs, terms] = await Promise.all([
    many(`${COURSE_SELECT} GROUP BY c.id ORDER BY c.code`),
    many('SELECT id FROM programs ORDER BY id'),
    many('SELECT * FROM terms ORDER BY starts_on'),
  ])
  const snapshot = {
    courses: courses.map(courseView),
    programs: await Promise.all(programs.map((p) => programView(p.id))),
    terms: terms.map(termView),
  }
  const row = await one('INSERT INTO catalog_versions (snapshot, published_by) VALUES ($1, $2) RETURNING id, published_at', [JSON.stringify(snapshot), req.user.id])
  await audit(req.user, `Published catalog version ${row.id}`, { req, target: { type: 'catalog', id: row.id } })
  res.status(201).json({ version: row.id, publishedAt: row.published_at, courses: snapshot.courses.length })
})

// ------------------------------------------------------------------ CSV imports for catalog and grades

const csvBody = express.text({ type: ['text/csv', 'text/plain'], limit: '5mb' })
function readCsv(req, required) {
  if (typeof req.body !== 'string' || !req.body.trim()) throw badRequest('Send the CSV file as the request body with Content-Type: text/csv.')
  const rows = parseCsv(req.body)
  if (rows.length === 0) throw badRequest('The CSV has no data rows.')
  const missing = required.filter((col) => !(col in rows[0]))
  if (missing.length) throw badRequest(`The CSV is missing column(s): ${missing.join(', ')}`)
  return rows
}

async function logImport(db, text) {
  await db.query(
    `UPDATE integrations SET last_sync_at = now(), log = jsonb_build_array(jsonb_build_object('a', $1::text, 'b', now())) || log WHERE id = 'csv'`, [text])
}

// Columns: code, name, type, credits, offered (yes/no), offer_term
router.post('/imports/courses', csvBody, async (req, res) => {
  const rows = readCsv(req, ['code', 'name', 'type'])
  const result = { created: 0, updated: 0, errors: [] }
  await transaction(async (db) => {
    for (const [i, row] of rows.entries()) {
      const type = TYPES.find((t) => t.toLowerCase() === row.type.toLowerCase())
      const credits = row.credits ? Number(row.credits) : 3
      if (!row.code || !row.name || !type || !Number.isInteger(credits) || credits < 1) {
        result.errors.push({ line: i + 2, message: 'Needs a code, name, valid type and whole-number credits' })
        continue
      }
      const { rows: out } = await db.query(
        `INSERT INTO courses (code, name, type, credits, offered, offer_term) VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, type = EXCLUDED.type, credits = EXCLUDED.credits,
           offered = EXCLUDED.offered, offer_term = EXCLUDED.offer_term, updated_at = now()
         RETURNING (xmax = 0) AS inserted`,
        [row.code, row.name, type, credits, !/^(no|false|0)$/i.test(row.offered ?? ''), row.offer_term || null])
      out[0].inserted ? result.created++ : result.updated++
    }
    await logImport(db, `Imported ${result.created + result.updated} catalog courses`)
  })
  await audit(req.user, `Imported ${result.created + result.updated} courses from a CSV file`, { req })
  res.json(result)
})

// Columns: student_email, course_code, term, status (current|completed|planned|dropped), grade, progress_pct, absences
router.post('/imports/grades', csvBody, async (req, res) => {
  const rows = readCsv(req, ['student_email', 'course_code', 'term'])
  const result = { created: 0, updated: 0, errors: [] }
  await transaction(async (db) => {
    for (const [i, row] of rows.entries()) {
      const line = i + 2
      const email = emailSchema.safeParse(row.student_email)
      const status = (row.status || 'completed').toLowerCase()
      const grade = row.grade || null
      if (!email.success) { result.errors.push({ line, message: 'Invalid student_email' }); continue }
      if (!['current', 'completed', 'planned', 'dropped'].includes(status)) { result.errors.push({ line, message: `Unknown status "${row.status}"` }); continue }
      if (grade && !['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F'].includes(grade)) { result.errors.push({ line, message: `Unknown grade "${grade}"` }); continue }
      const { rows: refs } = await db.query(
        `SELECT (SELECT id FROM users WHERE email = $1 AND role = 'student') AS student_id,
                (SELECT id FROM courses WHERE code = $2) AS course_id, (SELECT id FROM terms WHERE name = $3) AS term_id`,
        [email.data, row.course_code, row.term])
      const ref = refs[0]
      if (!ref.student_id || !ref.course_id || !ref.term_id) { result.errors.push({ line, message: 'Unknown student, course or term' }); continue }
      const { rows: out } = await db.query(
        `INSERT INTO enrollments (student_id, course_id, term_id, status, grade, progress_pct, absences) VALUES ($1, $2, $3, $4, $5, $6, $7)
         ON CONFLICT (student_id, course_id, term_id) DO UPDATE SET status = EXCLUDED.status, grade = EXCLUDED.grade,
           progress_pct = EXCLUDED.progress_pct, absences = EXCLUDED.absences
         RETURNING (xmax = 0) AS inserted`,
        [ref.student_id, ref.course_id, ref.term_id, status, grade, Math.min(100, Math.max(0, Number(row.progress_pct) || (status === 'completed' ? 100 : 0))), Math.max(0, Number(row.absences) || 0)])
      out[0].inserted ? result.created++ : result.updated++
    }
    await logImport(db, `Imported ${result.created + result.updated} grades and enrollments`)
  })
  await audit(req.user, `Imported ${result.created + result.updated} grades from a CSV file`, { req })
  res.json(result)
})

export default router
