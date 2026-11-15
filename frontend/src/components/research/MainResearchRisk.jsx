import { useEffect, useRef, useState } from 'react'

import { api, errorText } from '../../lib/api.js'

import Button from '../ui/Button.jsx'

import Card, { CardHeader } from '../ui/Card.jsx'

import Notice from '../ui/Notice.jsx'
import Pill from '../ui/Pill.jsx'

const STATUS = { in_progress: 'In progress', completed: 'Completed', failed: 'Failed', withdrawn: 'Withdrawn' }

const percent = value => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : 'Not available'

const FEATURE_LABEL = {

  course_day:'Course day', course_progress:'Course progress', window_days_28d:'Observed window length',

  clicks_7d:'Learning-resource activity over the past week', clicks_28d:'Learning-resource activity over the past four weeks',

  active_days_7d:'Days with learning activity over the past week', active_days_28d:'Days with learning activity over the past four weeks',

  engagement_change:'Change in recent interactions', days_since_activity:'Time since the last learning activity', no_activity:'No activity recorded',

  assessments_due:'Assessments due', submissions_so_far:'Submissions observed', overdue_assessments:'Overdue assessments',

  late_submission_rate:'Late submission rate', days_since_submission:'Time since the last submission', no_submission:'No submission recorded',

}

// Wording uses the observed input and the actual contribution direction separately.

// A contribution does not establish a cause or the benefit of an intervention.

export function explanationParagraph(explanation, evidence = {}) {

  if (explanation?.status !== 'available') return 'An explanation is not available for this assessment.'

  const ranked = [...(explanation.contributions ?? [])]

    .filter(c => FEATURE_LABEL[c.feature] && Number.isFinite(c.raw_log_odds_contribution) && Math.abs(c.raw_log_odds_contribution) > 1e-12)

    .sort((a,b) => Math.abs(b.raw_log_odds_contribution)-Math.abs(a.raw_log_odds_contribution))

  // Explain behavior only; course timing/deadline opportunity is not reassurance.

  const behavior = ranked.filter(c => !['course_day', 'course_progress', 'window_days_28d', 'assessments_due'].includes(c.feature))

  const chosen = behavior.slice(0, 2)

  if (!chosen.length) return ranked.length ? 'No clear learning-activity or submission explanation is available. Course timing and the amount of information observed also affect the estimate.' : 'No individual factor stood out in this assessment.'

  const details = chosen.map(c => {

    const value = c.input_value

    if (typeof value !== 'number' || !Number.isFinite(value)) {
      if (['late_submission_rate', 'days_since_submission'].includes(c.feature) && evidence.received_submissions === 0) {
        return { c, notObserved: true, observation: 'No submissions have been received, so submission timeliness cannot yet be assessed' }
      }
      if (c.feature === 'days_since_activity' && explanation.contributions.some(item => item.feature === 'no_activity' && item.input_value === 1)) {
        return { c, notObserved: true, observation: 'No learning activity was recorded in the observed course history' }
      }
      return { c, missing: true, observation: `Information about ${FEATURE_LABEL[c.feature].toLowerCase()} is missing` }
    }

    let observation

    const count = (singular, plural) => `${value} ${value === 1 ? singular : plural}`

    switch (c.feature) {

      case 'overdue_assessments': observation = value === 0 ? 'No assessments were overdue' : `${count('assessment was', 'assessments were')} overdue`; break

      case 'clicks_7d': observation = `${count('learning-resource interaction was', 'learning-resource interactions were')} recorded over the past week`; break

      case 'clicks_28d': observation = `${count('learning-resource interaction was', 'learning-resource interactions were')} recorded over the past four weeks`; break

      case 'active_days_7d': observation = `Learning activity was recorded on ${count('day', 'days')} over the past week`; break

      case 'active_days_28d': observation = `Learning activity was recorded on ${count('day', 'days')} over the past four weeks`; break

      case 'late_submission_rate': {
        const received = evidence.received_submissions, late = evidence.late_submissions
        const verified = Number.isInteger(received) && received > 0 && Number.isInteger(late) && late >= 0 && late <= received && Math.abs(late / received - value) < 1e-9
        observation = verified
          ? late === 0 ? received === 1 ? 'The received submission was on time' : `All ${received} received submissions were on time`
            : late === received ? `${received === 1 ? 'The received submission was' : `All ${received} received submissions were`} late`
            : `${late} of ${received} received submissions were late`
          : value === 0 ? 'None of the observed submissions were late' : `${Math.round(value * 100)}% of the observed submissions were late`
        break
      }

      case 'days_since_activity': observation = value === 0 ? 'Learning activity was recorded on the day covered by this assessment' : `The last recorded learning activity was ${count('day', 'days')} before this assessment`; break

      case 'days_since_submission': observation = value === 0 ? 'A submission was recorded on the day covered by this assessment' : `The last recorded submission was ${count('day', 'days')} before this assessment`; break

      case 'assessments_due': observation = `${count('assessment had', 'assessments had')} reached its deadline`.replace('assessments had reached its', 'assessments had reached their'); break

      case 'submissions_so_far': observation = `${count('submission was', 'submissions were')} recorded`; break

      case 'no_activity': observation = value === 1 ? 'No learning activity was recorded in the observation window' : 'Learning activity was recorded in the observation window'; break

      case 'no_submission': observation = value === 1 ? 'No submissions were recorded by this date' : 'Submissions were recorded by this date'; break

      case 'engagement_change': observation = value === 0 ? 'Resource-use counts were unchanged from the previous week' : `${value < 0 ? 'Fewer' : 'More'} learning-resource interactions were recorded in the past week than in the previous week`; break
      default: observation = FEATURE_LABEL[c.feature]; break

    }

    return { c, observation }

  })

  const concerns = details.filter(item => item.c.raw_log_odds_contribution > 0)
  const balances = details.filter(item => item.c.raw_log_odds_contribution < 0)
  const sentences = []
  const facts = items => items.map((item, index) => index ? item.observation[0].toLowerCase() + item.observation.slice(1) : item.observation).join(', and ') + '.'
  const overdue = concerns.find(item => !item.missing && item.c.feature === 'overdue_assessments' && item.c.input_value > 0)
  const late = concerns.find(item => !item.missing && item.c.feature === 'late_submission_rate' && item.c.input_value > 0)
  const onlyResourceCounts = concerns.length && concerns.every(item => !item.missing && item.c.feature.startsWith('clicks_'))
  if (onlyResourceCounts) {
    if (balances.length) sentences.push(facts(balances))
    sentences.push('Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material.')
    sentences.push('Review assignment progress before deciding whether a follow-up is needed.')
    return sentences.join(' ')
  }
  if (concerns.length) sentences.push(facts(concerns))
  if (balances.length) {
    const observation = facts(balances)
    sentences.push(concerns.length ? 'Alongside this, ' + observation[0].toLowerCase() + observation.slice(1) : observation)
  }
  if (details.some(item => item.missing)) {
    sentences.push('Missing records affect this assessment and should be checked before drawing conclusions about the student; missing information is not reassuring evidence.')
  } else if (overdue) {
    if (late) sentences.push('Both late submissions and outstanding work need follow-up.')
    else if (evidence.received_submissions !== 0) sentences.push('Work that has been received does not account for the assessment' + (overdue.c.input_value === 1 ? ' still outstanding.' : 's still outstanding.'))
    sentences.push('Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.')
  } else if (late) {
    sentences.push('The timing of submissions is the issue to discuss, even where participation is continuing.')
    sentences.push('Ask about barriers to meeting deadlines and agree on the next assignment to focus on.')
  } else if (concerns.length) {
    sentences.push('This assessment highlights the activity or submission pattern as something to explore, rather than proof that the student is disengaged.')
    sentences.push('Ask how the student is managing the coursework before deciding what support would help.')
  } else if (details.some(item => item.notObserved)) {
    sentences.push('The absence of observed activity or received work should not be read as evidence that the student is doing well.')
  } else {
    sentences.push('These are reassuring parts of the activity and submission record, but they do not guarantee a successful outcome.')
  }
  return sentences.join(' ')

}

function ModelExplanation({ explanation, evidence }) {

  return <p className="mt-3 mb-0 text-sm leading-relaxed">{explanationParagraph(explanation, evidence)}</p>

}

export function orderActiveEnrollments(enrollments, results) {

  const score = enrollment => {

    const result = results[enrollment.enrollment_id]

    return result?.status === 'scored_research_demo' && typeof result.research_risk_probability === 'number' && Number.isFinite(result.research_risk_probability)

      ? result.research_risk_probability : -1

  }

  // Sort a new array; retain original order for ties and unavailable estimates.

  return enrollments.filter(e => e.status === 'in_progress').sort((a,b) => score(b)-score(a))

}

function Enrollment({ enrollment, result }) {

  const scored = result?.status === 'scored_research_demo'

  const reason = result && !scored ? 'A current assessment is not available for this course.' : null

  return <article className="min-w-0 rounded-[var(--radius-tile)] border border-line bg-surface-sunk p-5">

    <div className="flex flex-wrap items-start justify-between gap-3">

      <div className="min-w-0">

        <h3 className="m-0 text-[15px] font-bold">{enrollment.course_code} · {enrollment.term}</h3>

        <div className="mt-2"><Pill tone={enrollment.status === 'in_progress' ? 'navy' : 'gray'}>{STATUS[enrollment.status] ?? 'Status not available'}</Pill></div>

      </div>

      <div className="text-left sm:text-right" role="status">

        {scored ? <><p className="m-0 font-display text-[28px] font-bold tracking-[-0.02em] tabular-nums">{percent(result.research_risk_probability)}</p><p className="m-0 text-xs text-muted">Estimated risk of failure or withdrawal</p></>

          : <p className="m-0 font-semibold">{!result ? (enrollment.status === 'in_progress' ? 'Loading assessment…' : 'Course ended') : 'Assessment unavailable'}</p>}

      </div>

    </div>

    {reason && <p className="mt-3 mb-0 text-sm leading-relaxed text-muted">{reason}</p>}

    {scored && <ModelExplanation explanation={result.explanation} evidence={result.evidence} />}

  </article>

}

// Main-only component: use main's session-aware API and assigned-advisor checks.

export default function MainResearchRisk({ studentId }) {

  const [data, setData] = useState(null)

  const [error, setError] = useState(null)

  const [results, setResults] = useState({})

  const [busy, setBusy] = useState(true)

  const [retry, setRetry] = useState(0)

  const request = useRef(0)

  useEffect(() => {

    let disposed = false

    let controller

    async function refresh(force = false) {

      const version = ++request.current

      controller?.abort()

      controller = new AbortController()

      const signal = controller.signal

      setData(null); setError(null); setResults({}); setBusy(true)

      try {

        const value = await api(`/advisor/research/students/${studentId}/insights`, { signal })

        if (disposed || version !== request.current) return

        const cutoff = value.demo_cutoff

        if (!cutoff || !Number.isFinite(Date.parse(cutoff))) throw new Error('A current assessment is not available.')

        setData({ ...value, owner: String(studentId) })

        const entries = await Promise.all(value.enrollments.filter(e => e.status === 'in_progress').map(async enrollment => {

          try {

            const result = await api(`/advisor/research/enrollments/${enrollment.enrollment_id}/risk-assessment?cutoff=${encodeURIComponent(cutoff)}&include_explanation=true${force === true ? '&force_refresh=true' : ''}`, { signal })

            // Reject mismatched snapshots/identities instead of showing an old result.

            if (result.enrollment_id !== undefined && String(result.enrollment_id) !== String(enrollment.enrollment_id)) throw new Error('Assessment identity mismatch')

            if (result.student_id !== undefined && String(result.student_id) !== String(studentId)) throw new Error('Assessment student mismatch')

            if (Date.parse(result.cutoff) !== Date.parse(cutoff)) throw new Error('Assessment snapshot mismatch')

            return [enrollment.enrollment_id, result]

          } catch (err) {

            return [enrollment.enrollment_id, { status: 'unavailable' }]

          }

        }))

        if (!disposed && version === request.current) setResults(Object.fromEntries(entries))

      } catch (err) {

        if (!disposed && version === request.current && err.name !== 'AbortError') setError('A current assessment is not available. Please try again.')

      } finally {

        if (!disposed && version === request.current) setBusy(false)

      }

    }

    const expire = () => {

      ++request.current; controller?.abort(); setData(null); setResults({}); setBusy(false)

      setError('A current assessment is not available. Please try again.')

    }

    const visibility = () => { if (document.visibilityState === 'hidden') expire(); else refresh() }

    refresh(retry > 0)

    const timer = window.setInterval(refresh, 12 * 60 * 60 * 1000)

    window.addEventListener('focus', refresh)

    window.addEventListener('online', refresh)

    window.addEventListener('offline', expire)

    document.addEventListener('visibilitychange', visibility)

    return () => {

      disposed = true; ++request.current; controller?.abort(); window.clearInterval(timer)

      window.removeEventListener('focus', refresh); window.removeEventListener('online', refresh)

      window.removeEventListener('offline', expire); document.removeEventListener('visibilitychange', visibility)

    }

  }, [studentId, retry])

  const currentData = data?.owner === String(studentId) ? data : null

  const active = orderActiveEnrollments(currentData?.enrollments ?? [], results)

  const historical = currentData?.enrollments.filter(e => e.status !== 'in_progress') ?? []

  return <Card as="section" aria-label="Course risk assessment" className="gap-4 font-sans text-sm">

    <CardHeader title="Course risk assessment" subtitle="Understand what may need attention in each course" />

    <details className="text-sm text-muted">

      <summary className="cursor-pointer">About this estimate</summary>

      <p className="mb-0 leading-relaxed">This demonstration uses synthetic learning activity and a model trained on the Open University Learning Analytics Dataset (OULAD). It has not been validated for AcadMate or Brightspace students. Estimates concern course failure or withdrawal, support advisor judgment, and do not trigger automatic decisions. Explanations describe model factors, not proven causes or guaranteed ways to improve outcomes.</p>

    </details>

    {error && <Notice tone="pink" role="alert">{error}</Notice>}

    {!currentData ? <div role="status">{busy ? 'Loading current assessments…' : 'A current assessment is not available.'}</div> : <>

      <section aria-label="Active enrollments" className="flex flex-col gap-3">

        <h3 className="m-0 text-[15px] font-bold">Active enrollments ({active.length})</h3>

        {!active.length && <p className="m-0 text-muted">No active enrollments recorded.</p>}

        {active.map(enrollment => <Enrollment key={enrollment.enrollment_id} enrollment={enrollment} result={results[enrollment.enrollment_id]} />)}

      </section>

      {!!historical.length && <details className="rounded-[var(--radius-tile)] border border-line p-4">

        <summary className="cursor-pointer font-semibold">Historical enrollments ({historical.length})</summary>

        <p className="mt-2 text-xs text-muted">Completed, failed or withdrawn courses. Current risk estimates apply to active courses only.</p>

        <div className="mt-3 flex flex-col gap-3">{historical.map(enrollment => <Enrollment key={enrollment.enrollment_id} enrollment={enrollment} result={results[enrollment.enrollment_id]} />)}</div>

      </details>}

      {!currentData.enrollments.length && <p className="m-0 text-muted">No recorded enrollments.</p>}

    </>}

    <div><Button variant="secondary" disabled={busy} onClick={() => setRetry(value => value + 1)}>{busy ? 'Updating…' : 'Refresh assessment'}</Button></div>

  </Card>

}
