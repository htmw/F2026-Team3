import { many, query } from '../db/pool.js'
import { addDays, daysBetween, localDate, monthYear, shortDate, weekday } from '../lib/time.js'

// Academic rules shared by the student, advisor and admin views. Everything here is derived from
// enrollments, requirements and submissions; nothing is stored twice.

export const CREDITS_PER_COURSE = 3
export const FULL_TIME_CREDITS = 9
const GRADE_POINTS = { A: 4, 'A-': 3.7, 'B+': 3.3, B: 3, 'B-': 2.7, 'C+': 2.3, C: 2, 'C-': 1.7, D: 1, F: 0 }
const STATUS_ORDER = { completed: 0, current: 1, planned: 2 }

export const round2 = (n) => Math.round(n * 100) / 100

export function gpa(enrollments) {
  let points = 0
  let credits = 0
  for (const e of enrollments) {
    if (e.grade == null || !(e.grade in GRADE_POINTS)) continue
    points += GRADE_POINTS[e.grade] * e.credits
    credits += e.credits
  }
  return credits ? round2(points / credits) : null
}

// Loads everything needed to evaluate students' progress, for many students at once.
export async function loadStudents(ids, db = { query }) {
  if (ids.length === 0) return new Map()
  // The pool can run these in parallel; a single transaction client must run them one at a time.
  const runAll = db.query === query ? (list) => Promise.all(list.map((fn) => fn())) : async (list) => {
    const out = []
    for (const fn of list) out.push(await fn())
    return out
  }
  const [profiles, enrollments, requirements, work, pending] = await runAll([
    () => db.query(
      `SELECT u.id, u.full_name, u.preferred_name, u.email, u.status, u.last_login_at, u.preferences,
              p.student_number, p.program_id, pr.name AS program, p.advisor_id, a.full_name AS advisor_name, p.study_goal_hours
         FROM users u JOIN student_profiles p ON p.user_id = u.id
         LEFT JOIN programs pr ON pr.id = p.program_id
         LEFT JOIN users a ON a.id = p.advisor_id
        WHERE u.id = ANY($1)`, [ids]),
    () => db.query(
      `SELECT e.*, c.code, c.name, c.credits, c.type, c.offered, t.name AS term, t.starts_on, t.ends_on, t.is_current,
              t.classes_begin, s.instructor, s.days, s.start_time, s.end_time, s.room, s.office_hours
         FROM enrollments e JOIN courses c ON c.id = e.course_id
         LEFT JOIN terms t ON t.id = e.term_id
         LEFT JOIN sections s ON s.course_id = e.course_id AND s.term_id = e.term_id
        WHERE e.student_id = ANY($1) AND e.status <> 'dropped'
        ORDER BY t.starts_on NULLS LAST, c.code`, [ids]),
    () => db.query(
      `SELECT program_id, name, course_type, required_count FROM requirement_groups ORDER BY sort_order, id`),
    () => db.query(
      `SELECT a.id, a.title, a.type, a.due_at, a.course_id, a.weight_pct, c.code AS course_code,
              x.student_id, COALESCE(s.status, 'To do') AS status, s.score, s.submitted_at
         FROM (SELECT a.id AS assignment_id, e.student_id FROM assignments a
                 JOIN enrollments e ON e.course_id = a.course_id AND e.term_id = a.term_id AND e.status = 'current'
                WHERE a.student_id IS NULL AND e.student_id = ANY($1)
               UNION
               SELECT id, student_id FROM assignments WHERE student_id = ANY($1)) x
         JOIN assignments a ON a.id = x.assignment_id
         LEFT JOIN courses c ON c.id = a.course_id
         LEFT JOIN submissions s ON s.assignment_id = a.id AND s.student_id = x.student_id
        ORDER BY a.due_at`, [ids]),
    () => db.query(
      `SELECT * FROM approvals WHERE student_id = ANY($1) AND status = 'Pending' ORDER BY created_at`, [ids]),
  ])

  const result = new Map()
  for (const p of profiles.rows) {
    result.set(p.id, {
      user: p,
      enrollments: [],
      requirements: requirements.rows.filter((r) => r.program_id === p.program_id),
      work: [],
      pendingApprovals: [],
    })
  }
  for (const e of enrollments.rows) result.get(e.student_id)?.enrollments.push(e)
  for (const w of work.rows) result.get(w.student_id)?.work.push(w)
  for (const a of pending.rows) result.get(a.student_id)?.pendingApprovals.push(a)
  return result
}

export async function loadStudent(id, db) {
  return (await loadStudents([id], db)).get(id) ?? null
}

const byStatus = (ctx, status) => ctx.enrollments.filter((e) => e.status === status)
const sumCredits = (list) => list.reduce((sum, e) => sum + e.credits, 0)

export function credits(ctx) {
  const totalCourses = ctx.requirements.reduce((sum, r) => sum + r.required_count, 0)
  return {
    earned: sumCredits(byStatus(ctx, 'completed')),
    inProgress: sumCredits(byStatus(ctx, 'current')),
    planned: sumCredits(byStatus(ctx, 'planned')),
    total: totalCourses * CREDITS_PER_COURSE,
    coursesCompleted: byStatus(ctx, 'completed').length,
    coursesTotal: totalCourses,
  }
}

// Per-term GPA for finished terms, then "Now": cumulative GPA including current grades.
export function gpaTrend(ctx) {
  const terms = new Map()
  for (const e of byStatus(ctx, 'completed')) {
    if (!terms.has(e.term)) terms.set(e.term, [])
    terms.get(e.term).push(e)
  }
  const trend = [...terms.entries()].map(([term, list]) => ({ term, gpa: gpa(list) })).filter((t) => t.gpa != null)
  const previous = gpa(byStatus(ctx, 'completed'))
  const now = gpa([...byStatus(ctx, 'completed'), ...byStatus(ctx, 'current')])
  return {
    trend: now != null ? [...trend, { term: 'Now', gpa: now }] : trend,
    cumulative: now ?? previous,
    change: now != null && previous != null ? round2(now - previous) : null,
    currentTerm: gpa(byStatus(ctx, 'current')),
    lastTerm: trend.at(-1)?.gpa ?? null,
  }
}

// Requirement groups with the courses that count toward each.
export function degreeAudit(ctx) {
  return ctx.requirements.map((req) => {
    const items = ctx.enrollments
      .filter((e) => e.type === req.course_type)
      .sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status])
    const done = items.filter((e) => e.status === 'completed').length
    const inProgress = items.filter((e) => e.status === 'current').length
    const planned = items.filter((e) => e.status === 'planned').length
    return {
      name: req.name,
      courseType: req.course_type,
      required: req.required_count,
      done: Math.min(done, req.required_count),
      inProgress,
      planned,
      remainingAfterTerm: Math.max(0, req.required_count - done - inProgress),
      pct: req.required_count ? Math.round((Math.min(done, req.required_count) / req.required_count) * 100) : 100,
      items: items.map((e) => ({
        enrollmentId: e.id,
        courseId: e.course_id,
        code: e.code,
        name: e.name,
        term: e.term,
        status: e.status === 'completed' ? 'Completed'
          : e.status === 'current' ? 'In progress'
          : e.plan_status === 'Approved' ? 'Planned'
          : e.plan_status ?? 'Planned',
      })),
    }
  })
}

export function remainingAfterTerm(ctx) {
  return degreeAudit(ctx).reduce((sum, g) => sum + g.remainingAfterTerm, 0)
}

// Expected graduation: the end of the term in which the last needed course is taken, if the plan covers
// everything. "confirmed" once every planned course it relies on is advisor-approved.
export function graduation(ctx) {
  const audit = degreeAudit(ctx)
  const remaining = audit.reduce((sum, g) => sum + g.remainingAfterTerm, 0)
  const current = byStatus(ctx, 'current')
  if (remaining === 0) {
    const last = [...current].sort((a, b) => (a.ends_on < b.ends_on ? 1 : -1))[0]
      ?? [...byStatus(ctx, 'completed')].sort((a, b) => (a.ends_on < b.ends_on ? 1 : -1))[0]
    return { label: last?.ends_on ? monthYear(last.ends_on) : 'Requirements met', confirmed: true, covered: true, remaining: 0, missing: [] }
  }
  const missing = []
  const needed = []
  for (const group of audit) {
    const planned = ctx.enrollments.filter((e) => e.status === 'planned' && e.type === group.courseType)
    if (planned.length < group.remainingAfterTerm) missing.push(`${group.remainingAfterTerm - planned.length} ${group.name}`)
    needed.push(...planned.slice(0, group.remainingAfterTerm))
  }
  if (missing.length) return { label: 'Not planned yet', confirmed: false, covered: false, remaining, missing }
  const last = needed.filter((e) => e.ends_on).sort((a, b) => (a.ends_on < b.ends_on ? 1 : -1))[0]
  return {
    label: last ? monthYear(last.ends_on) : 'Term not set',
    confirmed: needed.every((e) => e.plan_status === 'Approved'),
    covered: true,
    remaining,
    missing,
    pendingCodes: needed.filter((e) => e.plan_status !== 'Approved').map((e) => e.code),
  }
}

// Share of submitted work turned in by the deadline. Overdue unsubmitted work counts as late.
export function onTime(ctx, now = new Date()) {
  let onTimeCount = 0
  let total = 0
  for (const w of ctx.work) {
    const submitted = w.status === 'Submitted' || w.status === 'Graded'
    if (submitted) {
      total++
      if (!w.submitted_at || w.submitted_at <= w.due_at) onTimeCount++
    } else if (w.due_at < now) total++
  }
  return { onTime: onTimeCount, total, pct: total ? Math.round((onTimeCount / total) * 100) : null }
}

// Count of class meetings held so far this term, from each section's weekly days.
export function attendance(ctx, today) {
  let held = 0
  let absences = 0
  for (const e of byStatus(ctx, 'current')) {
    if (!e.days?.length) continue
    const start = e.classes_begin ?? e.starts_on
    const end = today < e.ends_on ? today : e.ends_on
    const span = daysBetween(start, end)
    for (let i = 0; i <= span; i++) if (e.days.includes(weekday(addDays(start, i)))) held++
    absences += e.absences
  }
  return { held, absences, pct: held ? Math.round(((held - absences) / held) * 100) : null }
}

// Deadline status used on the dashboard and in the assignments list.
export function taskStatus(work, now = new Date()) {
  if (work.status === 'Submitted' || work.status === 'Graded') return 'Done'
  const hours = (work.due_at - now) / 3_600_000
  if (hours < 0) return 'Overdue'
  if (hours <= 72) return 'Due soon'
  return work.status === 'In progress' ? 'In progress' : 'Not started'
}

// Rules that put an advisee on the advisor's "needs attention" list.
export function riskFlags(ctx, now = new Date()) {
  const flags = []
  const trend = gpaTrend(ctx)
  if (trend.lastTerm != null && trend.currentTerm != null && trend.lastTerm - trend.currentTerm >= 0.3) {
    flags.push({ level: 'High', text: `Term GPA fell from ${trend.lastTerm.toFixed(1)} to ${trend.currentTerm.toFixed(1)}.` })
  }
  const twoWeeksAgo = new Date(now - 14 * 86_400_000)
  const missed = ctx.work.filter((w) => w.due_at < now && w.due_at > twoWeeksAgo && !['Submitted', 'Graded'].includes(w.status)).length
  if (missed >= 2) flags.push({ level: missed >= 3 ? 'High' : 'Medium', text: `Missed ${missed} deadlines in the last 2 weeks.` })
  for (const approval of ctx.pendingApprovals) {
    if (approval.precheck_ok === false) {
      flags.push({ level: approval.type === 'Request' ? 'High' : 'Medium', text: `${approval.title}: ${approval.precheck_text}` })
    }
  }
  const last = ctx.user.last_login_at
  const idleDays = last ? Math.floor((now - last) / 86_400_000) : null
  if (idleDays == null || idleDays >= 21) {
    flags.push({ level: 'Medium', text: idleDays == null ? 'Has never signed in.' : `Hasn't signed in for ${Math.floor(idleDays / 7)} weeks.` })
  }
  if (remainingAfterTerm(ctx) > 0 && byStatus(ctx, 'planned').length === 0) {
    flags.push({ level: 'Medium', text: 'No plan for next term yet.' })
  }
  return flags
}

export function adviseeStatus(ctx, now) {
  if (remainingAfterTerm(ctx) === 0) return 'Graduating'
  return riskFlags(ctx, now).length ? 'Needs attention' : 'On track'
}

// "Capstone" / "Elective 4 of 5": the requirement slot a planned course would fill.
export function fulfills(audit, enrollment, ctx) {
  const group = audit.find((g) => g.courseType === enrollment.type)
  if (!group) return enrollment.type
  if (group.required <= 1) return group.name
  const planned = ctx.enrollments.filter((e) => e.status === 'planned' && e.type === enrollment.type)
  const position = group.done + group.inProgress + planned.findIndex((e) => e.id === enrollment.id) + 1
  return `${group.name.replace(/s$/, '')} ${Math.min(position, group.required)} of ${group.required}`
}

// The next-term recommendation shown on the dashboard and given by the AI advisor. `upcoming` is the
// next term row (or null).
export function recommendation(ctx, upcoming) {
  const grad = graduation(ctx)
  const plannedNext = byStatus(ctx, 'planned')
  if (grad.covered && grad.remaining > 0) {
    return {
      title: `${plannedNext[0]?.term ?? upcoming?.name ?? 'Next term'} plan`,
      text: `After this semester you will have ${grad.remaining * CREDITS_PER_COURSE} credits left. Your plan (${plannedNext.map((e) => `${e.code} ${e.name}`).join(', ')}) keeps you on track to graduate in ${grad.label}.${grad.confirmed ? ' Your advisor has approved it.' : ' It still needs your advisor\'s approval.'}`,
      canSubmit: plannedNext.some((e) => e.plan_status === 'Needs approval' || e.plan_status === 'Recommended'),
    }
  }
  if (grad.remaining === 0) {
    return { title: 'Final term', text: `You are taking your last required courses this term. Expected graduation: ${grad.label}. Remember to file your graduation application.`, canSubmit: false }
  }
  return { title: `${upcoming?.name ?? 'Next term'} planning`, text: `After this term you still need ${grad.missing.join(', ').toLowerCase()} course(s). Add courses to your degree plan to see your graduation date.`, canSubmit: false }
}

// Catalog courses the student has not taken or planned, with whether their prerequisites are met
// (completed or in progress). Optionally limited to one course type.
export async function eligibleCourses(ctx, { type, db = { query } } = {}) {
  const { rows } = await db.query(
    `SELECT c.id, c.code, c.name, c.type, c.credits, c.offered, c.offer_term,
            COALESCE(array_agg(p.code ORDER BY p.code) FILTER (WHERE p.code IS NOT NULL), '{}') AS prereq_codes,
            COALESCE(array_agg(p.id) FILTER (WHERE p.id IS NOT NULL), '{}') AS prereq_ids
       FROM courses c
       LEFT JOIN course_prerequisites cp ON cp.course_id = c.id
       LEFT JOIN courses p ON p.id = cp.prereq_id
      WHERE ($1::text IS NULL OR c.type = $1)
      GROUP BY c.id ORDER BY c.code`, [type ?? null])
  const onRecord = new Set(ctx.enrollments.map((e) => e.course_id))
  const passed = new Set(ctx.enrollments.filter((e) => e.status === 'completed' || e.status === 'current').map((e) => e.course_id))
  return rows.filter((c) => !onRecord.has(c.id)).map((c) => {
    const missing = c.prereq_codes.filter((_, i) => !passed.has(c.prereq_ids[i]))
    return {
      courseId: c.id, code: c.code, name: c.name, type: c.type, credits: c.credits, offered: c.offered,
      offerTerm: c.offer_term, prereqs: c.prereq_codes, prereqsMet: missing.length === 0, missingPrereqs: missing,
    }
  })
}

// ------------------------------------------------------------------ approval pre-checks

// Runs the automatic checks shown to advisors before they decide on a plan, form or request.
// Returns { ok, text, checks: [{ text, ok, blocking }] }.
export async function precheck(ctx, approval, { tz = 'UTC', db = { query } } = {}) {
  const checks = []
  const add = (ok, text, blocking = true) => checks.push({ ok, text, blocking })
  const currentCredits = sumCredits(byStatus(ctx, 'current'))

  if (approval.type === 'Course plan') {
    const ids = approval.payload.courseIds ?? []
    const { rows: courses } = await db.query(
      `SELECT c.*, COALESCE(array_agg(p.prereq_id) FILTER (WHERE p.prereq_id IS NOT NULL), '{}') AS prereqs
         FROM courses c LEFT JOIN course_prerequisites p ON p.course_id = c.id
        WHERE c.id = ANY($1) GROUP BY c.id`, [ids])
    const planCredits = sumCredits(courses)
    const audit = degreeAudit(ctx)
    const short = []
    for (const group of audit) {
      const inPlan = courses.filter((c) => c.type === group.courseType).length
      if (inPlan < group.remainingAfterTerm) short.push(`${group.remainingAfterTerm - inPlan} ${group.name.toLowerCase()}`)
    }
    const completes = short.length === 0
    const remaining = audit.reduce((sum, g) => sum + g.remainingAfterTerm, 0) * CREDITS_PER_COURSE
    add(true, completes ? `Covers all remaining requirements (${remaining} credits)` : `Leaves ${short.join(', ')} for a later term`, false)

    const passed = new Set(ctx.enrollments.filter((e) => e.status === 'completed' || e.status === 'current').map((e) => e.course_id))
    const missingPrereqs = []
    if (courses.some((c) => c.prereqs.length)) {
      const { rows: prereqCourses } = await db.query('SELECT id, code FROM courses WHERE id = ANY($1)', [courses.flatMap((c) => c.prereqs)])
      const codeOf = new Map(prereqCourses.map((p) => [p.id, p.code]))
      for (const c of courses) {
        const missing = c.prereqs.filter((p) => !passed.has(p)).map((p) => codeOf.get(p))
        if (missing.length) missingPrereqs.push(`${c.code} requires ${missing.join(', ')}, which is not completed or in progress.`)
      }
    }
    add(missingPrereqs.length === 0, missingPrereqs[0] ?? `Prerequisites met for ${courses.length === 1 ? 'the course' : `all ${courses.length} courses`}`)

    const notOffered = courses.filter((c) => !c.offered).map((c) => c.code)
    add(notOffered.length === 0, notOffered.length ? `${notOffered.join(', ')} ${notOffered.length === 1 ? 'is' : 'are'} not offered next term.` : 'Every course is offered next term')

    const fullTime = planCredits >= FULL_TIME_CREDITS || completes
    add(fullTime, fullTime
      ? `${planCredits} credits${completes && planCredits < FULL_TIME_CREDITS ? ' (final term, full-time rule waived)' : ' keeps full-time status'}`
      : `${planCredits} credits is below full-time status (${FULL_TIME_CREDITS}).`)

    if (courses.some((c) => c.type === 'Capstone')) {
      const form = ctx.work.find((w) => w.type === 'Form' && /capstone/i.test(w.title) && !['Submitted', 'Graded'].includes(w.status))
      if (form) add(false, `Capstone pre-approval form not submitted yet (due ${shortDate(localDate(form.due_at, tz))})`, false)
    }
    const blocking = checks.find((c) => !c.ok && c.blocking)
    const grad = graduation({ ...ctx, enrollments: [...ctx.enrollments.filter((e) => e.status !== 'planned'), ...courses.map((c) => ({ ...c, course_id: c.id, status: 'planned', ends_on: approval.payload.termEndsOn }))] })
    return {
      ok: !blocking,
      text: blocking?.text ?? (completes ? `Meets every remaining requirement. Graduation stays on track for ${grad.label}.` : 'Pre-check passed.'),
      checks,
    }
  }

  if (approval.type === 'Request') {
    const course = ctx.enrollments.find((e) => e.course_id === approval.payload.courseId && e.status === 'current')
    if (!course) return { ok: false, text: 'The student is not enrolled in this course.', checks: [{ ok: false, text: 'Not enrolled', blocking: true }] }
    const after = currentCredits - course.credits
    add(after >= FULL_TIME_CREDITS, after >= FULL_TIME_CREDITS
      ? `${after} credits after the drop keeps full-time status`
      : `Dropping leaves ${after} credits, below full-time status. This may affect funding or visa requirements; check before approving.`)
    const blocking = checks.find((c) => !c.ok && c.blocking)
    return { ok: !blocking, text: blocking?.text ?? 'Pre-check passed.', checks }
  }

  // Form: every field must be filled in.
  const fields = approval.payload.fields ?? {}
  const empty = Object.entries(fields).filter(([, value]) => !String(value ?? '').trim()).map(([key]) => key)
  for (const [key, value] of Object.entries(fields)) add(Boolean(String(value ?? '').trim()), `${key}: ${String(value ?? '').trim() ? 'provided' : 'missing'}`)
  return {
    ok: empty.length === 0,
    text: empty.length ? `The ${empty[0].toLowerCase()} section is empty. Approving now would leave the form incomplete.` : 'Every section of the form is filled in.',
    checks,
  }
}

export async function bookableStaff() {
  return many(
    `SELECT u.id, u.full_name, s.title, s.helps FROM users u JOIN staff_profiles s ON s.user_id = u.id
      WHERE u.status = 'active' AND s.bookable ORDER BY u.full_name`)
}
