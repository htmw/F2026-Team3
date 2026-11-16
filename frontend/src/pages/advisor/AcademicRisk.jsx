import { useEffect, useState } from 'react'
import {
  DEFAULT_CUTOFF,
  assessEnrollments,
  formatChange,
  formatProbability,
  requestJSON,
} from '../../research/api.js'

const card = 'rounded-2xl bg-white p-6 shadow-sm border border-slate-200'

export default function AcademicRisk() {
  const [students, setStudents] = useState([])
  const [studentId, setStudentId] = useState('')
  const [summary, setSummary] = useState(null)
  const [cutoff, setCutoff] = useState(DEFAULT_CUTOFF)
  const [reload, setReload] = useState(0)
  const [results, setResults] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    setError('')

    requestJSON('/students', { signal: controller.signal })
      .then((data) => setStudents(data.students))
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message)
        }
      })

    return () => controller.abort()
  }, [reload])

  useEffect(() => {
    setSummary(null)
    setResults({})

    if (!studentId) return

    const controller = new AbortController()

    setError('')

    requestJSON(`/students/${studentId}/insights`, {
      signal: controller.signal,
    })
      .then(setSummary)
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message)
        }
      })

    return () => controller.abort()
  }, [studentId])

  async function assess() {
    setBusy(true)
    setError('')
    setResults({})

    try {
      const response = await assessEnrollments(
        summary.active_enrollments,
        cutoff
      )

      setResults(response)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header>
        <p className="text-sm font-semibold text-teal-700">
          SPRINT 2 · SYNTHETIC DATA
        </p>

        <h1 className="mt-2 text-3xl font-bold">
          Academic risk research
        </h1>

        <p className="mt-2 text-slate-600">
          Review academic evidence and course-level model estimates.
        </p>
      </header>

      <aside className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
        Research demonstration only. Records and LMS events are synthetic.
        OULAD estimates are not validated for AcadMate students and may
        overestimate early risk. Brightspace is the intended source; no live
        connection is used.
      </aside>

      <section className={card}>
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex min-w-64 flex-col gap-2 font-medium">
            Synthetic student

            <select
              aria-label="Synthetic student"
              disabled={busy}
              value={studentId}
              onChange={(event) => setStudentId(event.target.value)}
              className="rounded-lg border border-slate-300 bg-white p-3"
            >
              <option value="">
                Select a student
              </option>

              {students.map((student) => (
                <option
                  key={student.student_id}
                  value={student.student_id}
                >
                  {student.name} · {student.student_id}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2 font-medium">
            Prediction cutoff (UTC)

            <input
              aria-label="Prediction cutoff"
              type="date"
              disabled={busy}
              value={cutoff}
              onChange={(event) => {
                setCutoff(event.target.value)
                setResults({})
              }}
              className="rounded-lg border border-slate-300 p-3"
            />
          </label>

          <button
            disabled={
              busy ||
              !summary?.active_enrollments.length ||
              !cutoff
            }
            onClick={assess}
            className="rounded-lg bg-slate-900 px-5 py-3 font-semibold text-white disabled:opacity-40"
          >
            {busy ? 'Assessing…' : 'Assess active courses'}
          </button>
        </div>

        <p className="mt-3 text-xs text-slate-500">
          Simulated Spring 2027 calendar. Cutoff is end of the selected UTC
          day, not today's date.
        </p>
      </section>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-900"
        >
          {error}

          {!students.length && (
            <button
              className="ml-4 underline"
              onClick={() => setReload((value) => value + 1)}
            >
              Retry loading students
            </button>
          )}
        </div>
      )}

      {summary && (
        <>
          <section className={card}>
            <h2 className="text-xl font-bold">
              {summary.name}
            </h2>

            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                [
                  'Recorded GPA',
                  summary.recorded_gpa ?? 'Not recorded',
                ],
                [
                  'Completed credits',
                  summary.completed_credits,
                ],
                [
                  'Failed courses',
                  summary.failed_courses.length,
                ],
                [
                  'Withdrawn courses',
                  summary.withdrawn_courses.length,
                ],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="text-sm text-slate-500">
                    {label}
                  </p>

                  <strong>
                    {value}
                  </strong>
                </div>
              ))}
            </div>

            <p className="mt-4 text-xs text-slate-500">
              Current academic snapshot, separate from prediction cutoff.{' '}
              {summary.gpa_policy}. These are descriptive indicators, not
              extra model inputs.
            </p>
          </section>

          <section
            className="flex flex-col gap-4"
            aria-live="polite"
          >
            <h2 className="text-xl font-bold">
              Active enrollments ({summary.active_enrollments.length})
            </h2>

            {!summary.active_enrollments.length && (
              <p>
                No active enrollments recorded.
              </p>
            )}

            {summary.active_enrollments.map((enrollment) => {
              const result = results[enrollment.enrollment_id]

              return (
                <article
                  key={enrollment.enrollment_id}
                  className={card}
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-bold">
                        {enrollment.course_code}
                      </h3>

                      <p className="text-sm text-slate-500">
                        {enrollment.term} · Enrollment{' '}
                        {enrollment.enrollment_id}
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-sm text-slate-500">
                        Research model estimate
                      </p>

                      <p className="text-2xl font-bold">
                        {result
                          ? formatProbability(
                              result.research_risk_probability
                            )
                          : 'Not requested'}
                      </p>
                    </div>
                  </div>

                  {result && (
                    <>
                      <p
                        role={
                          result.status === 'request_error'
                            ? 'alert'
                            : undefined
                        }
                        className="mt-3 text-sm"
                      >
                        {result.status === 'scored_research_demo'
                          ? 'Estimated eventual failure or subsequent withdrawal; no automatic alert threshold.'
                          : result.reason}
                      </p>

                      <p className="mt-2 text-xs text-slate-500">
                        Course day {result.as_of_day ?? 'unknown'} ·{' '}
                        {result.cutoff || 'No cutoff'} ·{' '}
                        {result.model_version || 'No model version'}
                      </p>

                      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                        {[
                          [
                            'Assessments due',
                            result.evidence?.assessments_due,
                          ],
                          [
                            'Submitted',
                            result.evidence?.submissions,
                          ],
                          [
                            'Overdue',
                            result.evidence?.overdue_assignments,
                          ],
                          [
                            'Active days (7d)',
                            result.evidence?.active_days_7d,
                          ],
                          [
                            'Interactions (7d)',
                            result.evidence?.clicks_7d,
                          ],
                          [
                            'Interactions (28d)',
                            result.evidence?.clicks_28d,
                          ],
                          [
                            'Change vs prior 7d',
                            result.evidence?.engagement_change == null
                              ? 'Unknown'
                              : formatChange(
                                  result.evidence.engagement_change
                                ),
                          ],
                          [
                            'Due work submitted',
                            result.evidence?.assessment_completion_rate == null
                              ? 'Unknown'
                              : `${(
                                  result.evidence.assessment_completion_rate *
                                  100
                                ).toFixed(0)}%`,
                          ],
                        ].map(([label, value]) => (
                          <div key={label}>
                            <dt className="text-slate-500">
                              {label}
                            </dt>

                            <dd className="font-semibold">
                              {value ?? 'Unknown'}
                            </dd>
                          </div>
                        ))}
                      </dl>

                      {Array.isArray(result.top_factors) &&
                        result.top_factors.length > 0 && (
                          <section className="mt-5">
                            <h4 className="text-sm font-bold text-slate-900">
                              Top model factors
                            </h4>

                            <div className="mt-3 grid gap-3 sm:grid-cols-3">
                              {result.top_factors.map((factor) => (
                                <div
                                  key={factor.feature}
                                  className="rounded-xl border border-slate-200 bg-slate-50 p-3"
                                >
                                  <p className="text-sm font-semibold">
                                    {factor.label}
                                  </p>

                                  <p className="mt-1 text-xs text-slate-500">
                                    Value: {factor.value ?? 'Unknown'}
                                  </p>

                                  <p
                                    className={`mt-2 text-xs font-semibold ${
                                      factor.direction === 'increases risk'
                                        ? 'text-red-700'
                                        : 'text-teal-700'
                                    }`}
                                  >
                                    {factor.direction}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </section>
                        )}

                      {Array.isArray(result.recommendations) &&
                        result.recommendations.length > 0 && (
                          <section className="mt-5">
                            <h4 className="text-sm font-bold text-slate-900">
                              Recommended actions
                            </h4>

                            <div className="mt-3 flex flex-col gap-3">
                              {result.recommendations.map(
                                (recommendation, index) => (
                                  <div
                                    key={`${recommendation.source_feature}-${index}`}
                                    className="rounded-xl border border-slate-200 p-4"
                                  >
                                    <p className="font-semibold">
                                      {recommendation.title}
                                    </p>

                                    <p className="mt-1 text-sm text-slate-600">
                                      {recommendation.detail}
                                    </p>

                                    <p className="mt-2 text-xs font-semibold text-slate-500">
                                      Suggested action:{' '}
                                      {recommendation.action}
                                    </p>
                                  </div>
                                )
                              )}
                            </div>
                          </section>
                        )}

                      <details className="mt-4 text-sm">
                        <summary className="cursor-pointer font-medium">
                          Released scores (descriptive only)
                        </summary>

                        <ul className="mt-2 list-disc pl-5">
                          {!Array.isArray(
                            result.evidence?.released_scores
                          ) ? (
                            <li>
                              Score data unavailable.
                            </li>
                          ) : result.evidence.released_scores.length ? (
                            result.evidence.released_scores.map((score) => (
                              <li key={score.assessment_id}>
                                Assessment {score.assessment_id}:{' '}
                                {score.score} / {score.max_score}
                              </li>
                            ))
                          ) : (
                            <li>
                              No released scores available at this cutoff.
                            </li>
                          )}
                        </ul>

                        <p className="mt-2 text-xs text-slate-500">
                          Assessment scores are not inputs to the frozen model.
                        </p>
                      </details>

                      <p className="mt-3 text-xs text-slate-500">
                        Coverage:{' '}
                        {result.coverage &&
                        Object.keys(result.coverage).length > 0
                          ? Object.entries(result.coverage)
                              .map(
                                ([source, coverage]) =>
                                  `${source}: ${
                                    coverage.complete
                                      ? 'complete'
                                      : 'incomplete'
                                  }`
                              )
                              .join(' · ')
                          : 'Not supplied'}
                      </p>
                    </>
                  )}
                </article>
              )
            })}
          </section>
        </>
      )}
    </>
  )
}