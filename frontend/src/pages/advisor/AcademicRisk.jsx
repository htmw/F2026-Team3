import { useEffect, useState } from 'react'
import { DEFAULT_CUTOFF, assessEnrollments, formatChange, formatProbability, requestJSON } from '../../research/api.js'
const card = 'rounded-2xl bg-white p-6 shadow-sm border border-slate-200'
export default function AcademicRisk() {
  const [students, setStudents] = useState([]), [studentId, setStudentId] = useState('')
  const [summary, setSummary] = useState(null), [cutoff, setCutoff] = useState(DEFAULT_CUTOFF)
  const [reload, setReload] = useState(0)
  const [results, setResults] = useState({}), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => {
    const c = new AbortController()
    setError('')
    requestJSON('/students', { signal: c.signal }).then(d => setStudents(d.students)).catch(e => { if (e.name !== 'AbortError') setError(e.message) })
    return () => c.abort()
  }, [reload])
  useEffect(() => {
    setSummary(null); setResults({})
    if (!studentId) return
    const c = new AbortController(); setError('')
    requestJSON(`/students/${studentId}/insights`, { signal: c.signal }).then(setSummary).catch(e => { if (e.name !== 'AbortError') setError(e.message) })
    return () => c.abort()
  }, [studentId])
  async function assess() {
    setBusy(true); setError(''); setResults({})
    try {
      setResults(await assessEnrollments(summary.active_enrollments, cutoff))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <>
    <header><p className="text-sm font-semibold text-teal-700">SPRINT 2 · SYNTHETIC DATA</p><h1 className="mt-2 text-3xl font-bold">Academic risk research</h1><p className="mt-2 text-slate-600">Review academic evidence and course-level model estimates.</p></header>
    <aside className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">Research demonstration only. Records and LMS events are synthetic. OULAD estimates are not validated for AcadMate students and may overestimate early risk. Brightspace is the intended source; no live connection is used.</aside>
    <section className={card}><div className="flex flex-wrap items-end gap-4">
      <label className="flex min-w-64 flex-col gap-2 font-medium">Synthetic student<select aria-label="Synthetic student" disabled={busy} value={studentId} onChange={e => setStudentId(e.target.value)} className="rounded-lg border border-slate-300 bg-white p-3"><option value="">Select a student</option>{students.map(s => <option key={s.student_id} value={s.student_id}>{s.name} · {s.student_id}</option>)}</select></label>
      <label className="flex flex-col gap-2 font-medium">Prediction cutoff (UTC)<input aria-label="Prediction cutoff" type="date" disabled={busy} value={cutoff} onChange={e => { setCutoff(e.target.value); setResults({}) }} className="rounded-lg border border-slate-300 p-3" /></label>
      <button disabled={busy || !summary?.active_enrollments.length || !cutoff} onClick={assess} className="rounded-lg bg-slate-900 px-5 py-3 font-semibold text-white disabled:opacity-40">{busy ? 'Assessing…' : 'Assess active courses'}</button>
    </div><p className="mt-3 text-xs text-slate-500">Simulated Spring 2027 calendar. Cutoff is end of the selected UTC day, not today's date.</p></section>
    {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-900">{error}{!students.length && <button className="ml-4 underline" onClick={() => setReload(value => value+1)}>Retry loading students</button>}</div>}
    {summary && <>
      <section className={card}><h2 className="text-xl font-bold">{summary.name}</h2><div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[['Recorded GPA',summary.recorded_gpa ?? 'Not recorded'],['Completed credits',summary.completed_credits],['Failed courses',summary.failed_courses.length],['Withdrawn courses',summary.withdrawn_courses.length]].map(([label,value]) => <div key={label}><p className="text-sm text-slate-500">{label}</p><strong>{value}</strong></div>)}
      </div><p className="mt-4 text-xs text-slate-500">Current academic snapshot, separate from prediction cutoff. {summary.gpa_policy}. These are descriptive indicators, not extra model inputs.</p></section>
      <section className="flex flex-col gap-4" aria-live="polite"><h2 className="text-xl font-bold">Active enrollments ({summary.active_enrollments.length})</h2>
        {!summary.active_enrollments.length && <p>No active enrollments recorded.</p>}
        {summary.active_enrollments.map(e => { const r = results[e.enrollment_id]; return <article key={e.enrollment_id} className={card}>
          <div className="flex flex-wrap items-start justify-between gap-4"><div><h3 className="text-lg font-bold">{e.course_code}</h3><p className="text-sm text-slate-500">{e.term} · Enrollment {e.enrollment_id}</p></div><div className="text-right"><p className="text-sm text-slate-500">Research model estimate</p><p className="text-2xl font-bold">{r ? formatProbability(r.research_risk_probability) : 'Not requested'}</p></div></div>
          {r && <><p role={r.status === 'request_error' ? 'alert' : undefined} className="mt-3 text-sm">{r.status === 'scored_research_demo' ? 'Estimated eventual failure or subsequent withdrawal; no automatic alert threshold.' : r.reason}</p><p className="mt-2 text-xs text-slate-500">Course day {r.as_of_day ?? 'unknown'} · {r.cutoff} · {r.model_version}</p>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">{[['Assessments due',r.evidence.assessments_due],['Submitted',r.evidence.submissions],['Overdue',r.evidence.overdue_assignments],['Active days (7d)',r.evidence.active_days_7d],['Interactions (7d)',r.evidence.clicks_7d],['Interactions (28d)',r.evidence.clicks_28d],['Change vs prior 7d',formatChange(r.evidence.engagement_change)],['Due work submitted',r.evidence.assessment_completion_rate == null ? 'Unknown' : `${(r.evidence.assessment_completion_rate*100).toFixed(0)}%`]].map(([label,value]) => <div key={label}><dt className="text-slate-500">{label}</dt><dd className="font-semibold">{value ?? 'Unknown'}</dd></div>)}</dl>
          <details className="mt-4 text-sm"><summary className="cursor-pointer font-medium">Released scores (descriptive only)</summary><ul className="mt-2 list-disc pl-5">{!Array.isArray(r.evidence.released_scores) ? <li>Score data unavailable.</li> : r.evidence.released_scores.length ? r.evidence.released_scores.map(s => <li key={s.assessment_id}>Assessment {s.assessment_id}: {s.score} / {s.max_score}</li>) : <li>No released scores available at this cutoff.</li>}</ul><p className="mt-2 text-xs text-slate-500">Assessment scores are not inputs to the frozen model.</p></details>
          <p className="mt-3 text-xs text-slate-500">Coverage: {Object.entries(r.coverage).map(([source,c]) => `${source}: ${c.complete ? 'complete' : 'incomplete'}`).join(' · ') || 'Not supplied'}</p></>}
        </article> })}
      </section>
    </>}
  </>
}
