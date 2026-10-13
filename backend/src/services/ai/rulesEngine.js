import { weekday } from '../../lib/time.js'
import { BOOK_MEETING, OPEN_PLAN } from './guard.js'
import { buildPlan } from './plan.js'
import { SOURCE_LABELS, courseCode, sourceBlock } from './tools.js'

// Rule-based answers over the student's own records. Used when Claude isn't configured or is switched off,
// as the fallback when a Claude request fails, and in tests. Recognises a short list of question types and
// says so honestly when a question is outside them.

const INTENTS = [
  ['what_if_fail', /\b(fail|fails|failing|failed|retake|withdraw|drop (a|my|the|this)?\s?(class|course))\b/],
  ['prerequisites', /\bprereq|\bprerequisite|can i take [a-z]{2,4}\s?\d{3}|before (i can )?tak(e|ing)/],
  ['electives', /\belectives?\b/],
  ['plan_term', /\bplan\b|\bplanning\b|next (semester|term)|\b(spring|fall|summer|winter)\b|\bregist(er|ration)\b|what (courses|classes) should|which (courses|classes) should/],
  ['on_track', /on track|graduat|finish (my )?(degree|program)|done with my degree/],
  ['remaining', /still need|left to take|\bremaining\b|\brequirements?\b|what do i (still )?need|how many (more )?(credits|courses)/],
  ['gpa', /\bgpa\b|\bgrades?\b|\bmarks\b/],
  ['schedule', /\bschedule\b|this week|\btoday\b|\btomorrow\b|\bcalendar\b|when (is|are) my|free time/],
  ['help', /^\s*(hi|hello|hey)\b|what can you (do|help)|\bhelp\b/],
]

// Data each question type needs.
const NEEDS = {
  what_if_fail: ['audits'], prerequisites: ['catalog'], electives: ['catalog'], plan_term: ['audits'], on_track: ['audits'],
  remaining: ['audits'], gpa: ['grades'], schedule: ['schedules'], help: [], fallback: [],
}

export function classify(text) {
  const q = String(text).toLowerCase()
  return INTENTS.find(([, re]) => re.test(q))?.[0] ?? 'fallback'
}

const list = (items) => (items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`)
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`
// "1 elective", "2 electives", "1 core course" from a requirement group name.
const countOf = (n, requirement) => {
  const lower = requirement.toLowerCase()
  const singular = lower.replace(/s$/, '')
  return `${n} ${n === 1 ? singular : lower.endsWith('s') ? lower : `${lower}s`}`
}

export const FALLBACK_TEXT = 'I can help with your degree plan, schedule and courses — try asking about one of those, like "Am I on track to graduate?" or "Compare my elective options".'

function blockedSource(intent, tools, settings, prefs) {
  for (const source of NEEDS[intent]) {
    const who = sourceBlock(source, { settings, prefs })
    if (who) return { source, who }
  }
  return null
}

const handlers = {
  async on_track({ tools, style }) {
    const s = await tools.call('get_progress_summary')
    let text
    if (s.coursesLeftAfterThisTerm === 0) {
      text = `You're taking your last required courses this term. Pass them and you'll finish in ${s.expectedGraduation}.`
    } else if (s.planCoversDegree) {
      text = `Yes. If you complete this term's courses and your plan, you'll graduate in ${s.expectedGraduation}.`
        + (s.planApprovedByAdvisor ? ' Your advisor has approved the plan.' : ` ${list(s.awaitingApproval)} still ${s.awaitingApproval.length === 1 ? 'needs' : 'need'} your advisor's approval.`)
    } else {
      text = `Not yet. After this term you still need ${list(s.missingFromPlan).toLowerCase()} course(s) that aren't on your plan. Add them to your degree plan to get a graduation date.`
    }
    if (style === 'Detailed') text += ` So far you've earned ${s.credits.earned} of ${s.credits.required} credits, with ${s.credits.inProgress} in progress.`
    return {
      text,
      follow: s.warnings.length ? `Worth a look: ${s.warnings.join(' ')}` : null,
      actions: s.planCoversDegree ? [] : [OPEN_PLAN],
    }
  },

  async plan_term({ ctx, tools, settings }) {
    const current = await tools.call('get_current_plan')
    const proposals = current.planned.map((p) => ({ code: p.code }))
    const summary = await tools.call('get_progress_summary')
    let suggested = 0
    if (!summary.planCoversDegree && tools.allowed('catalog')) {
      const audit = await tools.call('get_degree_audit')
      for (const group of audit) {
        const short = group.stillNeededAfterThisTerm - group.planned
        if (short <= 0) continue
        const fitting = (await tools.call('search_catalog', { type: group.courseType })).filter((c) => c.offeredNextTerm && c.prerequisitesMet)
        for (const c of fitting.slice(0, short)) proposals.push({ code: c.code, why: `Suggested for ${group.requirement.toLowerCase()}: offered next term and you meet the prerequisites.` })
        suggested += Math.min(short, fitting.length)
      }
    }
    const plan = settings.features.planSuggestions ? await buildPlan(proposals, ctx) : []
    let text = current.recommendation.text
    if (suggested) text += ` I've added ${plural(suggested, 'suggested course')} below that would fill the gap — they aren't on your plan until you add them.`
    return {
      text,
      plan,
      follow: current.recommendation.readyToSubmit ? 'When the plan looks right, submit it to your advisor from your degree plan.' : null,
      actions: [OPEN_PLAN],
    }
  },

  async electives({ ctx, tools, settings }) {
    const options = await tools.call('search_catalog', { type: 'Elective' })
    let needed = null
    if (tools.allowed('audits')) {
      const group = (await tools.call('get_degree_audit')).find((g) => g.courseType === 'Elective')
      if (group) needed = Math.max(0, group.stillNeededAfterThisTerm - group.planned)
    }
    if (!options.length) return { text: 'There are no electives left in the catalog that you haven\'t already taken or planned.', actions: [OPEN_PLAN] }
    const ranked = [...options].sort((a, b) => Number(b.prerequisitesMet && b.offeredNextTerm) - Number(a.prerequisitesMet && a.offeredNextTerm))
    const ready = ranked.filter((c) => c.prerequisitesMet && c.offeredNextTerm)
    const plan = settings.features.planSuggestions
      ? await buildPlan(ranked.map((c) => ({
          code: c.code,
          why: c.prerequisitesMet ? (c.offeredNextTerm ? 'You meet the prerequisites.' : 'Not offered next term.') : `Needs ${list(c.missingPrerequisites)} first.`,
        })), ctx)
      : []
    const needText = needed == null ? '' : needed === 0 ? ' Your plan already covers your elective requirement, so these would be extra.' : ` You still need ${plural(needed, 'elective')} beyond what's planned.`
    return {
      text: `${plural(options.length, 'elective')} ${options.length === 1 ? 'is' : 'are'} still open to you; ${ready.length} ${ready.length === 1 ? 'is' : 'are'} offered next term with prerequisites met.${needText}`,
      plan,
      follow: ready.length < options.length ? 'Electives with unmet prerequisites are listed last; their notes say what you need first.' : null,
      actions: [OPEN_PLAN],
    }
  },

  async remaining({ tools, style }) {
    const audit = await tools.call('get_degree_audit')
    const left = audit.filter((g) => g.stillNeededAfterThisTerm > 0)
    if (!left.length) return { text: 'Nothing beyond this term. Your current courses complete every requirement.' }
    const unplanned = left.map((g) => ({ ...g, open: g.stillNeededAfterThisTerm - g.planned })).filter((g) => g.open > 0)
    let text = `After this term you still need ${list(left.map((g) => countOf(g.stillNeededAfterThisTerm, g.requirement)))}.`
    text += unplanned.length ? ` ${list(unplanned.map((g) => countOf(g.open, g.requirement)))} ${unplanned.length === 1 && unplanned[0].open === 1 ? 'isn\'t' : 'aren\'t'} on your plan yet.` : ' Your plan covers all of them.'
    if (style === 'Detailed') text += ` ${audit.map((g) => `${g.requirement}: ${g.completed} of ${g.required} done${g.inProgress ? `, ${g.inProgress} in progress` : ''}.`).join(' ')}`
    return { text, actions: unplanned.length ? [OPEN_PLAN] : [] }
  },

  async prerequisites({ tools, text: question }) {
    const code = courseCode(question)
    if (!code) return { kind: 'fallback', text: 'Which course do you mean? Include its code, for example "What are the prerequisites for CS 640?"' }
    const c = await tools.call('get_course_prerequisites', { code })
    if (!c.found) return { kind: 'fallback', text: `I couldn't find ${c.code} in the course catalog. Check the code and try again.` }
    if (c.onRecord === 'completed' || c.onRecord === 'current') return { text: `You've ${c.onRecord === 'completed' ? 'already completed' : 'already enrolled in'} ${c.code} ${c.name}.` }
    const missing = c.prerequisites.filter((p) => !p.met)
    const prereqText = !c.prerequisites.length ? `${c.code} ${c.name} has no prerequisites.`
      : missing.length ? `${c.code} ${c.name} requires ${list(c.prerequisites.map((p) => p.code))}. You still need ${list(missing.map((p) => p.code))}.`
      : `You meet the prerequisites for ${c.code} ${c.name} (${list(c.prerequisites.map((p) => p.code))}).`
    const offered = c.offeredNextTerm ? ` It's offered${c.offerTerm ? ` in ${c.offerTerm}` : ' next term'}.` : ' It isn\'t offered next term.'
    return { text: prereqText + offered + (c.onRecord === 'planned' ? ' It\'s already on your plan.' : '') }
  },

  async gpa({ tools, style }) {
    const t = await tools.call('get_gpa_trend')
    if (t.cumulative == null) return { text: 'You don\'t have any grades on record yet.' }
    let text = `Your cumulative GPA is ${t.cumulative.toFixed(2)}`
    text += t.changeFromLastTerm == null ? '.' : ` (${t.changeFromLastTerm >= 0 ? 'up' : 'down'} ${Math.abs(t.changeFromLastTerm).toFixed(2)} from last term).`
    if (style === 'Detailed' && t.byTerm.length) text += ` By term: ${t.byTerm.map((x) => `${x.term} ${x.gpa.toFixed(2)}`).join(', ')}.`
    return { text }
  },

  async schedule({ tools }) {
    const s = await tools.call('get_schedule', {})
    if (!s.items.length) return { text: 'Nothing is on your calendar for the rest of this week.' }
    const shown = s.items.slice(0, 8).map((i) => `${weekday(i.date)} ${i.start} ${i.title}`)
    return {
      text: `Coming up this week: ${shown.join('; ')}.${s.items.length > 8 ? ` Plus ${s.items.length - 8} more on your calendar.` : ''}`,
      actions: [{ label: 'Open schedule', to: '/student/schedule' }],
    }
  },

  async what_if_fail({ tools }) {
    const s = await tools.call('get_progress_summary')
    const audit = await tools.call('get_degree_audit')
    const counts = audit.flatMap((g) => g.courses.filter((c) => c.status === 'In progress').map((c) => `${c.code} counts toward ${g.requirement.toLowerCase()}`))
    return {
      text: `A course you don't pass won't count toward its requirement, so you'd need to retake it or replace it, which can move your graduation date (currently ${s.expectedGraduation}).${counts.length ? ` This term, ${list(counts)}.` : ''}`,
      follow: 'If you\'re worried about a course, talk to your advisor early — they can go over options like withdrawing or retaking before deadlines pass.',
      actions: [BOOK_MEETING],
    }
  },

  async help({ tools }) {
    const sources = [...['audits', 'catalog', 'grades', 'schedules'].filter((s) => tools.allowed(s)).map((s) => SOURCE_LABELS[s].toLowerCase())]
    return {
      text: `I can answer questions about your degree progress, plan, electives, prerequisites${tools.allowed('grades') ? ', GPA' : ''}${tools.allowed('schedules') ? ' and schedule' : ''}, using your ${list(sources)}.`,
    }
  },

  async fallback() {
    return { kind: 'fallback', text: FALLBACK_TEXT }
  },
}

export async function rulesAnswer({ ctx, text, tools, settings, prefs, style }) {
  const intent = classify(text)
  const blocked = blockedSource(intent, tools, settings, prefs)
  if (blocked) {
    const label = SOURCE_LABELS[blocked.source].toLowerCase()
    return {
      kind: 'handoff',
      text: blocked.who === 'school'
        ? `I can't answer that because your school has turned off AI access to your ${label}. Your advisor can help instead.`
        : `I can't answer that because you've turned off AI access to your ${label}. You can change that in Settings, or ask your advisor.`,
      plan: [], follow: null,
      actions: blocked.who === 'student' ? [{ label: 'Open settings', to: '/student/settings' }, BOOK_MEETING] : [BOOK_MEETING],
      intent,
    }
  }
  const reply = await handlers[intent]({ ctx, text, tools, settings, prefs, style })
  return {
    kind: reply.kind ?? 'answer',
    text: reply.text,
    plan: reply.plan ?? [],
    follow: style === 'Concise' ? null : reply.follow ?? null,
    actions: reply.actions ?? [],
    intent,
  }
}
