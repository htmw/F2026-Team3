import { Router } from 'express'
import { z } from 'zod'
import { config } from '../config.js'
import { many, one, query, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { randomToken } from '../lib/crypto.js'
import { badRequest, conflict, notFound } from '../lib/errors.js'
import { initials, shortName } from '../lib/people.js'
import { mergedPreferences } from '../lib/preferences.js'
import { currentTerm, getSetting, timeZone } from '../lib/settings.js'
import {
  addDays, dayLong, daysBetween, hhmm, localDate, localTime, mondayOf, monthName, relativeDay, shortDate, toMinutes, WEEKDAYS, zonedTime,
} from '../lib/time.js'
import { requireRole } from '../middleware/auth.js'
import {
  CREDITS_PER_COURSE, attendance, credits, degreeAudit, fulfills, gpaTrend, graduation, loadStudent, onTime, precheck, recommendation, taskStatus,
} from '../services/academics.js'
import { classMeetings, deadlinesBetween, studentCalendar, studySuggestion } from '../services/calendar.js'
import { buildIcs } from '../services/ics.js'
import { notify } from '../services/notify.js'

const router = Router()
router.use(requireRole('student'))
router.use(async (req, res, next) => {
  req.ctx = await loadStudent(req.user.id)
  if (!req.ctx) throw notFound('Student profile')
  req.tz = await timeZone()
  req.today = localDate(new Date(), req.tz)
  next()
})

const TONES = ['teal', 'indigo', 'amber', 'pink']
const dateParam = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Use a YYYY-MM-DD date.')
const timeParam = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Use a 24-hour HH:MM time.')
const pct = (n) => (n == null ? '—' : `${n}%`)
const when = (e) => (e.days?.length && e.start_time ? `${e.days.join(' & ')} ${hhmm(e.start_time)}–${hhmm(e.end_time)}` : 'Time to be announced')

async function nextTerm(after) {
  return one('SELECT * FROM terms WHERE starts_on > $1 ORDER BY starts_on LIMIT 1', [after])
}

function requirementCount(group) {
  return group.inProgress ? `${group.done} done · ${group.inProgress} in progress` : `${group.done} of ${group.required}`
}

// ------------------------------------------------------------------ dashboard

router.get('/me/dashboard', async (req, res) => {
  const { ctx, tz, today } = req
  const term = await currentTerm()
  const upcoming = term ? await nextTerm(term.starts_on) : null
  // Proactive tips can be switched off by the school (AI settings) or by the student (preferences).
  const tipsOn = (await getSetting('ai')).features.proactiveTips && mergedPreferences(ctx.user.preferences).ai.dashboardSuggestions
  const week = term ? Math.max(1, Math.floor(daysBetween(term.classes_begin ?? term.starts_on, today) / 7) + 1) : null
  const trend = gpaTrend(ctx)
  const credit = credits(ctx)
  const grad = graduation(ctx)
  const ontime = onTime(ctx)
  const attend = attendance(ctx, today)
  const audit = degreeAudit(ctx)

  const monday = mondayOf(today)
  const weekItems = await studentCalendar(ctx, monday, addDays(monday, 6), tz)
  const studyDays = WEEKDAYS.map((day, i) => {
    const date = addDays(monday, i)
    const minutes = weekItems.filter((item) => item.type === 'Study' && item.date === date)
      .reduce((sum, item) => sum + toMinutes(item.end) - toMinutes(item.start), 0)
    return { day, date, hours: Math.round((minutes / 60) * 10) / 10, today: date === today }
  })

  const openForm = ctx.work.find((w) => w.type === 'Form' && !['Submitted', 'Graded'].includes(w.status))
  const alerts = []
  if (upcoming?.registration_opens && upcoming.registration_opens >= today) alerts.push(`${upcoming.name} registration opens ${shortDate(upcoming.registration_opens)}.`)
  if (openForm) alerts.push(`${openForm.title} is still missing (due ${shortDate(localDate(openForm.due_at, tz))}).`)

  // Open work first (soonest due), then the most recently finished.
  const recent = ctx.work.filter((w) => daysBetween(today, localDate(w.due_at, tz)) >= -7 && daysBetween(today, localDate(w.due_at, tz)) <= 30)
  const done = (w) => ['Submitted', 'Graded'].includes(w.status)
  const tasks = [...recent.filter((w) => !done(w)), ...recent.filter(done).reverse()]
    .slice(0, 6)
    .map((w) => ({ id: w.id, title: w.title, course: w.course_code ?? 'Advising', due: shortDate(localDate(w.due_at, tz)), status: taskStatus(w) }))

  const todayItems = weekItems.filter((item) => item.date === today)

  res.json({
    student: {
      firstName: ctx.user.preferred_name || ctx.user.full_name.split(' ')[0],
      initials: initials(ctx.user.full_name),
      program: ctx.user.program,
      termLabel: [term?.name, week && `Week ${week}`, ctx.user.program].filter(Boolean).join(' · '),
      today: dayLong(today),
    },
    gpa: {
      cumulative: trend.cumulative,
      change: trend.change,
      trend: trend.trend,
      status: trend.cumulative == null ? 'No grades yet' : trend.cumulative >= 3 ? 'On track' : 'Below 3.0',
    },
    stats: [
      {
        key: 'onTime', label: 'On-time submission', value: pct(ontime.pct), pct: ontime.pct ?? 0,
        pill: ontime.pct == null ? 'No data' : ontime.pct >= 90 ? 'Good' : ontime.pct >= 75 ? 'Fair' : 'Low',
        tone: ontime.pct == null || ontime.pct >= 90 ? 'teal' : 'amber',
        note: `${ontime.onTime} of ${ontime.total} submitted on time`,
      },
      {
        key: 'credits', label: 'Credits earned', value: `${credit.earned} / ${credit.total}`,
        pct: credit.total ? Math.round((credit.earned / credit.total) * 100) : 0,
        pill: `${credit.total ? Math.round((credit.earned / credit.total) * 100) : 0}%`, tone: 'indigo',
        note: `${credit.inProgress} in progress · ${grad.remaining * CREDITS_PER_COURSE} left after this term`,
      },
      {
        key: 'attendance', label: 'Attendance', value: pct(attend.pct), pct: attend.pct ?? 0,
        pill: attend.pct == null ? 'No data' : attend.pct >= 95 ? 'Great' : attend.pct >= 85 ? 'Good' : 'Low',
        tone: attend.pct == null || attend.pct >= 85 ? 'teal' : 'amber',
        note: `${attend.absences} absence${attend.absences === 1 ? '' : 's'} this term`,
      },
      {
        key: 'graduation', label: 'Expected graduation', value: grad.covered ? grad.label : '—',
        pct: credit.total ? Math.round(((credit.earned + credit.inProgress) / credit.total) * 100) : 0,
        pill: grad.confirmed ? 'Confirmed' : grad.covered ? 'Pending' : 'Not planned', tone: grad.confirmed ? 'teal' : 'amber', warn: !grad.confirmed,
        note: grad.confirmed ? 'Plan approved by your advisor' : grad.covered ? `Pending approval of ${grad.pendingCodes.join(', ')}` : 'Add the remaining courses to your plan',
      },
    ],
    recommendation: tipsOn ? recommendation(ctx, upcoming) : null,
    requirements: audit.map((g) => ({ label: g.name, count: requirementCount(g), pct: g.pct, warn: g.done === 0 && g.inProgress === 0 && g.required > 0 })),
    alert: alerts.join(' ') || null,
    studyHours: { goal: ctx.user.study_goal_hours, total: Math.round(studyDays.reduce((s, d) => s + d.hours, 0) * 10) / 10, days: studyDays },
    today: {
      label: dayLong(today),
      events: todayItems.map((item) => ({ id: item.id, time: item.start, title: item.title, type: item.type, meta: [item.type === 'Class' ? 'Lecture' : item.type, item.location].filter(Boolean).join(' · ') })),
    },
    tasks,
    courses: ctx.enrollments.filter((e) => e.status === 'current').map((e, i) => ({
      courseId: e.course_id, code: e.code, name: e.name, prof: e.instructor ?? 'Instructor TBA', pct: e.progress_pct, grade: e.grade ?? '—', tone: TONES[i % TONES.length],
    })),
  })
})

// ------------------------------------------------------------------ courses

function courseUpcoming(ctx, enrollment, parts, tz, today) {
  const work = ctx.work.filter((w) => w.course_id === enrollment.course_id && localDate(w.due_at, tz) >= today)
    .map((w) => ({ date: localDate(w.due_at, tz), title: w.title, meta: `${w.type} · Course site` }))
  const exams = parts.filter((p) => p.due_on && p.due_on >= today && p.score == null)
    .map((p) => ({ date: p.due_on, title: p.label, meta: `In class · ${enrollment.room ?? 'Room TBA'}` }))
  return [...work, ...exams].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 3)
    .map((u) => ({ ...u, mon: monthName(u.date), day: String(Number(u.date.slice(8))) }))
}

const partScore = (p) => (p.score != null ? `${p.score}%` : p.due_on ? shortDate(p.due_on) : 'In progress')

router.get('/me/courses', async (req, res) => {
  const { status } = z.object({ status: z.enum(['current', 'completed', 'planned']).optional() }).parse(req.query)
  const { ctx, tz, today } = req
  const current = ctx.enrollments.filter((e) => e.status === 'current')
  const parts = current.length
    ? await many('SELECT * FROM grade_components WHERE enrollment_id = ANY($1) ORDER BY sort_order, id', [current.map((e) => e.id)])
    : []
  const audit = degreeAudit(ctx)
  const monday = mondayOf(today)

  const result = {
    counts: {
      current: current.length,
      completed: ctx.enrollments.filter((e) => e.status === 'completed').length,
      planned: ctx.enrollments.filter((e) => e.status === 'planned').length,
    },
  }
  if (!status || status === 'current') {
    result.current = current.map((e, i) => {
      const own = parts.filter((p) => p.enrollment_id === e.id)
      const upcoming = courseUpcoming(ctx, e, own, tz, today)
      return {
        enrollmentId: e.id, courseId: e.course_id, code: e.code, name: e.name, prof: e.instructor ?? 'Instructor TBA',
        when: when(e), room: e.room ?? 'Room TBA', credits: `${e.credits} credits`, pct: e.progress_pct, grade: e.grade ?? '—',
        next: upcoming[0] ? `${upcoming[0].title} · ${shortDate(upcoming[0].date)}` : 'Nothing due soon',
        office: e.office_hours ?? 'By appointment', tone: TONES[i % TONES.length],
        parts: own.map((p) => ({ label: p.label, weight: `${p.weight}%`, score: partScore(p) })),
        upcoming,
      }
    })
    result.week = WEEKDAYS.slice(0, 5).map((day, i) => {
      const date = addDays(monday, i)
      const items = classMeetings(ctx, date, date).map((c) => ({ time: c.start, code: c.courseCode, room: c.location }))
      return { day, items, empty: items.length === 0 }
    })
  }
  if (!status || status === 'completed') {
    result.completed = ctx.enrollments.filter((e) => e.status === 'completed')
      .map((e) => ({ courseId: e.course_id, code: e.code, name: e.name, term: e.term, grade: e.grade ?? '—' }))
  }
  if (!status || status === 'planned') {
    result.planned = ctx.enrollments.filter((e) => e.status === 'planned').map((e) => ({
      enrollmentId: e.id, courseId: e.course_id, code: e.code, name: e.name, term: e.term ?? 'Unscheduled',
      status: e.plan_status ?? 'Planned', fulfills: fulfills(audit, e, ctx), why: e.plan_note ?? '',
    }))
  }
  res.json(result)
})

// ------------------------------------------------------------------ degree audit & plan

router.get('/me/degree-audit', (req, res) => {
  const { ctx } = req
  const credit = credits(ctx)
  const grad = graduation(ctx)
  const audit = degreeAudit(ctx)
  const left = audit.filter((g) => g.remainingAfterTerm > 0)
  const currentCount = ctx.enrollments.filter((e) => e.status === 'current').length
  const share = (n) => (credit.total ? Math.round((n / credit.total) * 100) : 0)
  res.json({
    stats: [
      { label: 'Credits earned', value: `${credit.earned} / ${credit.total}`, pct: share(credit.earned), note: `${credit.coursesCompleted} of ${credit.coursesTotal} courses complete` },
      { label: 'In progress', value: String(credit.inProgress), pct: share(credit.inProgress), note: `${currentCount} course${currentCount === 1 ? '' : 's'} this term` },
      { label: 'Left after this term', value: String(grad.remaining * CREDITS_PER_COURSE), pct: share(credit.total - grad.remaining * CREDITS_PER_COURSE), note: left.length ? left.map((g) => `${g.remainingAfterTerm} ${g.name.toLowerCase()}`).join(' and ') : 'Nothing left' },
      { label: 'Expected graduation', value: grad.label, pct: share(credit.earned + credit.inProgress), warn: !grad.confirmed, note: grad.confirmed ? 'Approved by your advisor' : grad.covered ? 'Pending advisor approval' : 'Plan the remaining courses' },
    ],
    groups: audit.map((g) => ({
      title: g.name,
      count: g.inProgress ? `${g.done} of ${g.required} done · ${g.inProgress} in progress` : `${g.done} of ${g.required} done`,
      allDone: g.done >= g.required,
      required: g.required,
      items: g.items,
    })),
    graduation: grad,
  })
})

router.get('/me/plan', async (req, res) => {
  const { ctx } = req
  const terms = new Map()
  for (const e of ctx.enrollments) {
    const key = e.term ?? 'Unscheduled'
    if (!terms.has(key)) terms.set(key, { name: key, startsOn: e.starts_on, items: [] })
    terms.get(key).items.push(e)
  }
  const catalog = await many(`SELECT id, code, name, type, credits, offered, offer_term FROM courses ORDER BY code`)
  const taken = new Set(ctx.enrollments.map((e) => e.course_id))
  const future = await many(`SELECT id, name, starts_on FROM terms WHERE starts_on > (SELECT starts_on FROM terms WHERE is_current) ORDER BY starts_on`)
  res.json({
    terms: [...terms.values()]
      .sort((a, b) => (a.startsOn ?? '9999').localeCompare(b.startsOn ?? '9999'))
      .map((t) => ({
        name: t.name,
        tag: t.items.every((e) => e.status === 'completed') ? 'Done' : t.items.some((e) => e.status === 'current') ? 'Current' : 'Planned',
        credits: `${t.items.reduce((s, e) => s + e.credits, 0)} credits`,
        courses: t.items.map((e) => ({ enrollmentId: e.id, courseId: e.course_id, code: e.code, name: e.name, status: e.status, planStatus: e.plan_status })),
      })),
    available: catalog.filter((c) => !taken.has(c.id)).map((c) => ({ courseId: c.id, code: c.code, name: c.name, type: c.type, credits: c.credits, offered: c.offered, offerTerm: c.offer_term })),
    futureTerms: future.map((t) => ({ id: t.id, name: t.name })),
  })
})

router.post('/me/plan', async (req, res) => {
  const body = z.object({
    courseCode: z.string().trim().min(1).max(20),
    termId: z.number().int().positive().optional(),
    note: z.string().trim().max(500).optional(),
  }).parse(req.body)
  const course = await one('SELECT * FROM courses WHERE code = $1', [body.courseCode])
  if (!course) throw notFound('Course')
  if (req.ctx.enrollments.some((e) => e.course_id === course.id)) throw conflict(`${course.code} is already on your record or plan.`)

  const term = await currentTerm()
  const target = body.termId
    ? await one('SELECT * FROM terms WHERE id = $1 AND starts_on > $2', [body.termId, term.starts_on])
    : await nextTerm(term.starts_on)
  if (!target) throw badRequest('Pick a future term for this course.')

  const row = await one(
    `INSERT INTO enrollments (student_id, course_id, term_id, status, plan_status, plan_note)
     VALUES ($1, $2, $3, 'planned', 'Needs approval', $4) RETURNING id`,
    [req.user.id, course.id, target.id, body.note ?? null],
  )
  await audit(req.user, `Added ${course.code} to their ${target.name} plan`, { req, target: { type: 'enrollment', id: row.id }, subjectUserId: req.user.id })
  res.status(201).json({ enrollmentId: row.id, code: course.code, name: course.name, term: target.name, status: 'Needs approval' })
})

router.delete('/me/plan/:enrollmentId', async (req, res) => {
  const id = z.coerce.number().int().positive().parse(req.params.enrollmentId)
  const row = await one(`SELECT e.*, c.code FROM enrollments e JOIN courses c ON c.id = e.course_id WHERE e.id = $1 AND e.student_id = $2 AND e.status = 'planned'`, [id, req.user.id])
  if (!row) throw notFound('Planned course')
  if (row.plan_status === 'Pending approval') throw conflict('This course is part of a plan waiting for approval. Ask your advisor to request changes first.')
  await query('DELETE FROM enrollments WHERE id = $1', [id])
  await audit(req.user, `Removed ${row.code} from their plan`, { req, subjectUserId: req.user.id })
  res.status(204).end()
})

router.post('/me/plan/submit', async (req, res) => {
  const { termId } = z.object({ termId: z.number().int().positive().optional() }).parse(req.body ?? {})
  const { ctx } = req
  const candidates = ctx.enrollments.filter((e) => e.status === 'planned' && ['Needs approval', 'Recommended'].includes(e.plan_status) && (!termId || e.term_id === termId))
  if (candidates.length === 0) throw badRequest('There are no planned courses waiting to be sent for approval.')
  const termIdUsed = candidates[0].term_id
  const items = candidates.filter((e) => e.term_id === termIdUsed)
  if (!ctx.user.advisor_id) throw badRequest("You don't have an assigned advisor yet. Contact your department.")
  if (ctx.pendingApprovals.some((a) => a.type === 'Course plan' && a.payload.termId === termIdUsed)) {
    throw conflict('A plan for this term is already waiting for approval.')
  }

  const sections = await many('SELECT * FROM sections WHERE term_id = $1 AND course_id = ANY($2)', [termIdUsed, items.map((e) => e.course_id)])
  const lines = items.map((e) => {
    const s = sections.find((x) => x.course_id === e.course_id)
    return { a: `${e.code} ${e.name}`, b: `${s?.days?.length ? `${s.days[0]} ${hhmm(s.start_time)} · ` : ''}${e.credits} cr` }
  })
  const approval = {
    type: 'Course plan',
    title: `${items[0].term} plan · ${items.map((e) => e.name).join(' + ')}`,
    payload: { courseIds: items.map((e) => e.course_id), enrollmentIds: items.map((e) => e.id), termId: termIdUsed, termEndsOn: items[0].ends_on },
  }
  const advisorSettings = await one('SELECT settings FROM staff_profiles WHERE user_id = $1', [ctx.user.advisor_id])
  const check = advisorSettings?.settings?.precheck === false ? null : await precheck(ctx, approval, { tz: req.tz })

  const created = await transaction(async (db) => {
    const { rows } = await db.query(
      `INSERT INTO approvals (student_id, advisor_id, type, title, lines, payload, precheck_ok, precheck_text)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id`,
      [req.user.id, ctx.user.advisor_id, approval.type, approval.title, JSON.stringify(lines), JSON.stringify({ ...approval.payload, checks: check?.checks ?? [] }), check?.ok ?? null, check?.text ?? null],
    )
    await db.query(`UPDATE enrollments SET plan_status = 'Pending approval' WHERE id = ANY($1)`, [approval.payload.enrollmentIds])
    await notify(ctx.user.advisor_id, `${shortName(ctx.user.full_name)} sent a ${items[0].term} course plan for your approval.`, db)
    await notify(req.user.id, `Your ${items[0].term} plan is waiting for advisor approval.`, db)
    return rows[0]
  })
  await audit(req.user, `Shared their ${items[0].term} plan for approval`, { req, target: { type: 'approval', id: created.id }, subjectUserId: req.user.id })
  res.status(201).json({ approvalId: created.id, status: 'Pending', precheck: check })
})

// Drop request: goes to the advisor as a "Request" approval.
router.post('/me/requests', async (req, res) => {
  const body = z.object({
    type: z.literal('drop'),
    courseCode: z.string().trim().min(1).max(20),
    reason: z.string().trim().max(1000).optional(),
  }).parse(req.body)
  const { ctx } = req
  const enrollment = ctx.enrollments.find((e) => e.code === body.courseCode && e.status === 'current')
  if (!enrollment) throw badRequest(`You are not currently enrolled in ${body.courseCode}.`)
  if (!ctx.user.advisor_id) throw badRequest("You don't have an assigned advisor yet. Contact your department.")
  if (ctx.pendingApprovals.some((a) => a.type === 'Request' && a.payload.courseId === enrollment.course_id)) throw conflict('You already asked to drop this course.')

  const approval = { type: 'Request', title: `Drop ${enrollment.code} ${enrollment.name}`, payload: { action: 'drop', courseId: enrollment.course_id, enrollmentId: enrollment.id, reason: body.reason ?? '' } }
  const check = await precheck(ctx, approval, { tz: req.tz })
  const currentCredits = ctx.enrollments.filter((e) => e.status === 'current').reduce((s, e) => s + e.credits, 0)
  const lines = [{ a: 'Drop', b: `${enrollment.code} · ${enrollment.credits} cr` }, { a: 'Credits after drop', b: String(currentCredits - enrollment.credits) }]
  const row = await transaction(async (db) => {
    const { rows } = await db.query(
      `INSERT INTO approvals (student_id, advisor_id, type, title, lines, payload, precheck_ok, precheck_text)
       VALUES ($1, $2, 'Request', $3, $4, $5, $6, $7) RETURNING id`,
      [req.user.id, ctx.user.advisor_id, approval.title, JSON.stringify(lines), JSON.stringify({ ...approval.payload, checks: check.checks }), check.ok, check.text],
    )
    await notify(ctx.user.advisor_id, `${shortName(ctx.user.full_name)} asked to drop ${enrollment.code}.`, db)
    return rows[0]
  })
  await audit(req.user, `Requested to drop ${enrollment.code}`, { req, target: { type: 'approval', id: row.id }, subjectUserId: req.user.id })
  res.status(201).json({ approvalId: row.id, status: 'Pending', precheck: check })
})

// ------------------------------------------------------------------ schedule

const eventBody = z.object({
  title: z.string().trim().min(1).max(200),
  type: z.enum(['Office hours', 'Advising', 'Study', 'Team']),
  date: dateParam,
  start: timeParam,
  end: timeParam,
  location: z.string().trim().max(200).optional().nullable(),
  note: z.string().trim().max(1000).optional().nullable(),
}).refine((e) => e.end > e.start, { message: 'The end time must be after the start time.', path: ['end'] })

router.get('/me/events', async (req, res) => {
  const { tz, today, ctx } = req
  const q = z.object({ from: dateParam.optional(), to: dateParam.optional() }).parse(req.query)
  const from = q.from ?? mondayOf(today)
  const to = q.to ?? addDays(from, 6)
  if (to < from || daysBetween(from, to) > 62) throw badRequest('Use a date range of at most 62 days.')
  const items = await studentCalendar(ctx, from, to, tz)
  const deadlines = deadlinesBetween(ctx, from, to, tz)
  const days = Array.from({ length: daysBetween(from, to) + 1 }, (_, i) => addDays(from, i)).map((date) => ({
    date,
    name: WEEKDAYS[(daysBetween(mondayOf(date), date))],
    day: Number(date.slice(8)),
    events: items.filter((item) => item.date === date),
    due: deadlines.filter((d) => d.date === date).map((d) => `${d.course} ${d.title} due`),
  }))
  const upcoming = deadlinesBetween(ctx, today, addDays(today, 14), tz).filter((d) => !['Submitted', 'Graded'].includes(d.status))
  const future = await studentCalendar(ctx, today, addDays(today, 14), tz)
  res.json({
    from, to, today, days,
    deadlines: upcoming.map((d) => ({ ...d, label: shortDate(d.date) })),
    suggestion: studySuggestion(future, upcoming, today),
  })
})

router.post('/me/events', async (req, res) => {
  const body = eventBody.parse(req.body)
  const row = await one(
    `INSERT INTO events (owner_id, title, type, starts_at, ends_at, location, note) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id`,
    [req.user.id, body.title, body.type, zonedTime(body.date, body.start, req.tz), zonedTime(body.date, body.end, req.tz), body.location ?? null, body.note ?? null],
  )
  res.status(201).json({ id: row.id, ...body })
})

router.patch('/me/events/:id', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const existing = await one('SELECT * FROM events WHERE id = $1 AND owner_id = $2', [id, req.user.id])
  if (!existing) throw notFound('Event')
  const merged = eventBody.parse({
    title: existing.title, type: existing.type, date: localDate(existing.starts_at, req.tz), start: localTime(existing.starts_at, req.tz),
    end: localTime(existing.ends_at, req.tz), location: existing.location, note: existing.note, ...req.body,
  })
  await query(
    `UPDATE events SET title = $1, type = $2, starts_at = $3, ends_at = $4, location = $5, note = $6 WHERE id = $7`,
    [merged.title, merged.type, zonedTime(merged.date, merged.start, req.tz), zonedTime(merged.date, merged.end, req.tz), merged.location ?? null, merged.note ?? null, id],
  )
  res.json({ id, ...merged })
})

router.delete('/me/events/:id', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const { rowCount } = await query('DELETE FROM events WHERE id = $1 AND owner_id = $2', [id, req.user.id])
  if (!rowCount) throw notFound('Event')
  res.status(204).end()
})

// Subscribable calendar feed URL (and a way to revoke the old one).
async function feedUrl(userId, rotate = false) {
  let row = await one('SELECT calendar_token FROM users WHERE id = $1', [userId])
  if (!row.calendar_token || rotate) {
    row = await one('UPDATE users SET calendar_token = $1 WHERE id = $2 RETURNING calendar_token', [randomToken(24), userId])
  }
  return `${config.apiUrl}/api/calendar/${row.calendar_token}.ics`
}

router.get('/me/calendar', async (req, res) => res.json({ url: await feedUrl(req.user.id) }))
router.post('/me/calendar/rotate', async (req, res) => res.json({ url: await feedUrl(req.user.id, true) }))

router.get('/me/calendar.ics', async (req, res) => {
  res.type('text/calendar').attachment('acadmate.ics').send(await buildIcs(req.ctx, req.tz))
})

// ------------------------------------------------------------------ assignments

export function assignmentRow(w, tz, steps = []) {
  return {
    id: w.id,
    title: w.title,
    course: w.course_code ?? 'Advising',
    due: shortDate(localDate(w.due_at, tz)),
    dueAt: w.due_at,
    status: w.status,
    deadline: taskStatus(w),
    score: w.score != null ? `${w.score}%` : '—',
    weight: w.weight_pct != null ? `${w.weight_pct}%` : 'Required',
    type: w.type,
    steps,
  }
}

router.get('/me/assignments', async (req, res) => {
  const q = z.object({
    status: z.enum(['To do', 'In progress', 'Submitted', 'Graded']).optional(),
    course: z.string().trim().max(20).optional(),
  }).parse(req.query)
  const { ctx, tz } = req
  const details = ctx.work.length
    ? await many(
      `SELECT a.id, a.description, a.steps, COALESCE(s.steps_done, '{}') AS steps_done FROM assignments a
         LEFT JOIN submissions s ON s.assignment_id = a.id AND s.student_id = $2 WHERE a.id = ANY($1)`,
      [ctx.work.map((w) => w.id), req.user.id])
    : []
  const detail = new Map(details.map((d) => [d.id, d]))
  const now = new Date()
  const all = ctx.work.map((w) => {
    const d = detail.get(w.id)
    return { ...assignmentRow(w, tz, d.steps.map((text, i) => ({ text, done: d.steps_done.includes(i) }))), desc: d.description ?? '' }
  })
  const open = ctx.work.filter((w) => !['Submitted', 'Graded'].includes(w.status))
  const dueSoon = open.filter((w) => w.due_at > now && w.due_at - now <= 10 * 86_400_000)
  const graded = ctx.work.filter((w) => w.status === 'Graded' && w.score != null)
  const inProgress = ctx.work.filter((w) => w.status === 'In progress')
  const count = (status) => ctx.work.filter((w) => w.status === status).length
  const courses = [...new Set(all.map((a) => a.course))]

  res.json({
    stats: [
      { label: 'Due in next 10 days', value: String(dueSoon.length), note: dueSoon[0] ? `Next: ${dueSoon[0].title} on ${shortDate(localDate(dueSoon[0].due_at, tz))}` : 'Nothing due soon' },
      { label: 'In progress', value: String(inProgress.length), note: [...new Set(inProgress.map((w) => w.course_code ?? 'Advising'))].join(' and ') || 'None' },
      { label: 'Awaiting grade', value: String(count('Submitted')), note: ctx.work.filter((w) => w.status === 'Submitted').map((w) => `${w.title} · ${w.course_code ?? 'Advising'}`)[0] ?? 'Nothing waiting' },
      { label: 'Graded average', value: graded.length ? `${Math.round(graded.reduce((s, w) => s + w.score, 0) / graded.length)}%` : '—', note: `Across ${graded.length} graded item${graded.length === 1 ? '' : 's'}` },
    ],
    tabs: [
      { label: 'All', count: ctx.work.length },
      ...['To do', 'In progress', 'Submitted', 'Graded'].map((label) => ({ label, count: count(label) })),
    ],
    courses,
    rows: all.filter((a) => (!q.status || a.status === q.status) && (!q.course || a.course === q.course)),
  })
})

// ------------------------------------------------------------------ meetings

router.get('/me/meetings', async (req, res) => {
  const rows = await many(
    `SELECT m.*, u.full_name AS staff_name FROM meetings m JOIN users u ON u.id = m.staff_id
      WHERE m.student_id = $1 AND m.status IN ('requested', 'confirmed', 'proposed') AND m.ends_at > now()
      ORDER BY m.starts_at`, [req.user.id])
  res.json({
    meetings: rows.map((m) => {
      const date = localDate(m.starts_at, req.tz)
      return {
        id: m.id, mon: monthName(date), day: String(Number(date.slice(8))), title: m.topic, status: m.status,
        staffId: m.staff_id, staffName: m.staff_name, format: m.format, startsAt: m.starts_at,
        proposedStartsAt: m.proposed_starts_at,
        meta: `${relativeDay(m.starts_at, req.tz)} · ${localTime(m.starts_at, req.tz)} · ${m.format} · ${m.staff_name}`,
      }
    }),
  })
})

export default router
