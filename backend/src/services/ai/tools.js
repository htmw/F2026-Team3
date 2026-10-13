import { z } from 'zod'
import { many, one } from '../../db/pool.js'
import { addDays, daysBetween, hhmm, mondayOf } from '../../lib/time.js'
import {
  credits, degreeAudit, eligibleCourses, fulfills, gpaTrend, graduation, recommendation, riskFlags,
} from '../academics.js'
import { studentCalendar } from '../calendar.js'

// The data the AI advisor may read about the signed-in student. Every tool is bound to that one student
// (there is no student id argument), and a tool is only offered when the school's AI settings and the
// student's own preferences allow its data source.

export const SOURCE_LABELS = { audits: 'Degree audit', catalog: 'Course catalog', grades: 'Grades', schedules: 'Schedule' }

// Why a data source is unavailable: null when allowed, otherwise 'school' or 'student'.
export function sourceBlock(source, { settings, prefs }) {
  if (!settings.sources?.[source]) return 'school'
  if (source === 'grades') {
    if (!settings.features?.gradeInsights) return 'school'
    if (!prefs.ai.useGrades) return 'student'
  }
  if (source === 'schedules' && !prefs.ai.useSchedule) return 'student'
  return null
}

export const courseCode = (text) => {
  const m = /\b([a-z]{2,4})\s?-?(\d{3})\b/i.exec(String(text))
  return m ? `${m[1].toUpperCase()} ${m[2]}` : null
}

const when = (e) => (e.days?.length && e.start_time ? `${e.days.join(' & ')} ${hhmm(e.start_time)}–${hhmm(e.end_time)}` : null)

async function nextTerm() {
  return one(`SELECT * FROM terms WHERE starts_on > (SELECT starts_on FROM terms WHERE is_current) ORDER BY starts_on LIMIT 1`)
}

// Builds the tool set for one request. `used` collects the data sources that tools actually read, which is
// what the reply's "Based on" line shows.
export function createTools({ ctx, settings, prefs, tz, today }) {
  const used = new Set()
  const allowed = (source) => sourceBlock(source, { settings, prefs }) === null
  const mark = (...sources) => sources.forEach((s) => used.add(SOURCE_LABELS[s]))
  const gradesOn = allowed('grades')

  const definitions = [
    {
      name: 'get_progress_summary',
      source: 'audits',
      description: 'Overall degree progress: program, credits earned / in progress / planned / required, expected graduation, whether the plan covers every requirement, courses still missing from the plan, plan courses awaiting advisor approval, and any warnings.',
      inputSchema: z.object({}),
      run: () => {
        mark('audits')
        const credit = credits(ctx)
        const grad = graduation(ctx)
        const warnings = riskFlags(ctx).map((f) => f.text).filter((t) => gradesOn || !/GPA/.test(t))
        return {
          program: ctx.user.program,
          credits: { earned: credit.earned, inProgress: credit.inProgress, planned: credit.planned, required: credit.total },
          expectedGraduation: grad.label,
          planCoversDegree: grad.covered,
          planApprovedByAdvisor: grad.confirmed,
          coursesLeftAfterThisTerm: grad.remaining,
          missingFromPlan: grad.missing,
          awaitingApproval: grad.pendingCodes ?? [],
          warnings,
          advisor: ctx.user.advisor_name ?? null,
        }
      },
    },
    {
      name: 'get_degree_audit',
      source: 'audits',
      description: 'Requirement groups (e.g. Core, Electives, Capstone) with how many courses each needs and which courses count toward it, by status.',
      inputSchema: z.object({}),
      run: () => {
        mark('audits')
        return degreeAudit(ctx).map((g) => ({
          requirement: g.name, courseType: g.courseType, required: g.required, completed: g.done, inProgress: g.inProgress, planned: g.planned,
          stillNeededAfterThisTerm: g.remainingAfterTerm,
          courses: g.items.map((i) => ({ code: i.code, name: i.name, term: i.term, status: i.status })),
        }))
      },
    },
    {
      name: 'get_current_plan',
      source: 'audits',
      description: 'Courses the student has planned for future terms, which requirement each fills, and their approval status, plus the next-term recommendation.',
      inputSchema: z.object({}),
      run: async () => {
        mark('audits')
        const audit = degreeAudit(ctx)
        const rec = recommendation(ctx, await nextTerm())
        return {
          planned: ctx.enrollments.filter((e) => e.status === 'planned').map((e) => ({
            code: e.code, name: e.name, term: e.term ?? 'Unscheduled', approval: e.plan_status ?? 'Planned',
            fulfills: fulfills(audit, e, ctx), when: when(e),
          })),
          recommendation: { title: rec.title, text: rec.text, readyToSubmit: rec.canSubmit },
        }
      },
    },
    {
      name: 'get_courses',
      source: 'audits',
      description: `The student's current and completed courses${gradesOn ? ' with grades' : ''}, with instructor and meeting times for current courses.`,
      inputSchema: z.object({ status: z.enum(['current', 'completed']).optional().describe('Only courses with this status') }),
      run: ({ status } = {}) => {
        mark('audits')
        const list = ctx.enrollments.filter((e) => (status ? e.status === status : e.status === 'current' || e.status === 'completed'))
        if (gradesOn && list.some((e) => e.grade)) mark('grades')
        return list.map((e) => ({
          code: e.code, name: e.name, term: e.term, status: e.status, type: e.type,
          ...(gradesOn ? { grade: e.grade ?? null } : {}),
          ...(e.status === 'current' ? { instructor: e.instructor ?? null, when: when(e), room: e.room ?? null } : {}),
        }))
      },
    },
    {
      name: 'get_gpa_trend',
      source: 'grades',
      description: 'Cumulative GPA, GPA by finished term, and the change from last term.',
      inputSchema: z.object({}),
      run: () => {
        mark('grades')
        const t = gpaTrend(ctx)
        return { cumulative: t.cumulative, changeFromLastTerm: t.change, currentTermGpa: t.currentTerm, byTerm: t.trend }
      },
    },
    {
      name: 'get_schedule',
      source: 'schedules',
      description: "Classes, events, study blocks and advising meetings on the student's calendar between two dates (inclusive, at most 14 days). Defaults to today through the end of this week.",
      inputSchema: z.object({
        from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe('YYYY-MM-DD'),
        to: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe('YYYY-MM-DD'),
      }),
      run: async ({ from, to } = {}) => {
        mark('schedules')
        const start = from ?? today
        let end = to ?? addDays(mondayOf(today), 6)
        if (end < start) end = start
        if (daysBetween(start, end) > 13) end = addDays(start, 13)
        const items = await studentCalendar(ctx, start, end, tz)
        return { from: start, to: end, items: items.map((i) => ({ date: i.date, start: i.start, end: i.end, type: i.type, title: i.title, location: i.location ?? null })) }
      },
    },
    {
      name: 'search_catalog',
      source: 'catalog',
      description: 'Catalog courses the student has not taken or planned yet, with whether they are offered next term and whether their prerequisites are met. Filter by course type and/or a search text.',
      inputSchema: z.object({
        type: z.enum(['Foundation', 'Core', 'Elective', 'Capstone']).optional(),
        query: z.string().max(60).optional().describe('Text to match in the course code or name'),
      }),
      run: async ({ type, query } = {}) => {
        mark('catalog')
        const q = query?.trim().toLowerCase()
        const rows = (await eligibleCourses(ctx, { type })).filter((c) => !q || `${c.code} ${c.name}`.toLowerCase().includes(q))
        return rows.slice(0, 25).map((c) => ({
          code: c.code, name: c.name, type: c.type, credits: c.credits, offeredNextTerm: c.offered, offerTerm: c.offerTerm,
          prerequisites: c.prereqs, prerequisitesMet: c.prereqsMet, missingPrerequisites: c.missingPrereqs,
        }))
      },
    },
    {
      name: 'get_course_prerequisites',
      source: 'catalog',
      description: "One catalog course by code (e.g. 'CS 640'): its prerequisites, whether the student has met each one, whether it is offered, and whether the course is already on the student's record.",
      inputSchema: z.object({ code: z.string().min(3).max(12) }),
      run: async ({ code }) => {
        mark('catalog')
        const normalized = courseCode(code) ?? code.trim().toUpperCase()
        const course = await one('SELECT * FROM courses WHERE code = $1', [normalized])
        if (!course) return { found: false, code: normalized }
        const prereqs = await many(
          `SELECT p.id, p.code, p.name FROM course_prerequisites cp JOIN courses p ON p.id = cp.prereq_id WHERE cp.course_id = $1 ORDER BY p.code`, [course.id])
        const statusOf = (id) => ctx.enrollments.find((e) => e.course_id === id)?.status ?? null
        const passed = (id) => ['completed', 'current'].includes(statusOf(id))
        return {
          found: true, code: course.code, name: course.name, type: course.type, offeredNextTerm: course.offered, offerTerm: course.offer_term,
          onRecord: statusOf(course.id),
          prerequisites: prereqs.map((p) => ({ code: p.code, name: p.name, met: passed(p.id), status: statusOf(p.id) ?? 'not taken' })),
        }
      },
    },
  ]

  const available = definitions.filter((d) => allowed(d.source))
  const byName = new Map(available.map((d) => [d.name, d]))
  return {
    available,
    used,
    allowed,
    async call(name, input = {}) {
      const tool = byName.get(name)
      if (!tool) return null
      return tool.run(tool.inputSchema.parse(input))
    },
  }
}
