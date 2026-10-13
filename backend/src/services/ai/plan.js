import { many } from '../../db/pool.js'
import { hhmm } from '../../lib/time.js'
import { degreeAudit, fulfills } from '../academics.js'
import { courseCode } from './tools.js'

const MAX_ITEMS = 6
const when = (e) => (e.days?.length && e.start_time ? `${e.days.join(' & ')} ${hhmm(e.start_time)}` : null)

// Turns proposed plan rows ({ code, why?, fulfills? }) into what the chat shows. Only real courses survive:
// a code must be planned on the student's record or be a catalog course they haven't taken. Names, terms and
// the requirement filled come from the database, never from the proposer.
export async function buildPlan(items, ctx) {
  const wanted = []
  for (const item of items ?? []) {
    const code = courseCode(item.code) ?? String(item.code ?? '').trim().toUpperCase()
    if (code && !wanted.some((w) => w.code === code)) wanted.push({ ...item, code })
  }
  if (!wanted.length) return []
  const audit = degreeAudit(ctx)
  const catalog = new Map((await many('SELECT id, code, name, type, offered, offer_term FROM courses WHERE code = ANY($1)', [wanted.map((w) => w.code)]))
    .map((c) => [c.code, c]))
  const plan = []
  for (const item of wanted) {
    const course = catalog.get(item.code)
    if (!course) continue
    const enrollment = ctx.enrollments.find((e) => e.course_id === course.id)
    if (enrollment && enrollment.status !== 'planned') continue // already taken or in progress
    const group = audit.find((g) => g.courseType === course.type)
    plan.push({
      code: course.code,
      name: course.name,
      meta: enrollment
        ? [enrollment.term ?? 'Unscheduled', when(enrollment), enrollment.plan_status].filter(Boolean).join(' · ')
        : [course.offer_term ?? (course.offered ? 'Offered next term' : 'Not offered next term'), 'Not on your plan yet'].join(' · '),
      fulfills: enrollment ? fulfills(audit, enrollment, ctx) : group?.name ?? course.type,
      why: typeof item.why === 'string' && item.why.trim() ? item.why.trim().slice(0, 200) : null,
      onPlan: Boolean(enrollment),
    })
    if (plan.length === MAX_ITEMS) break
  }
  return plan
}
