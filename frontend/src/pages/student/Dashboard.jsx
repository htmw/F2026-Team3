import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Pill, { Chip } from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import StatTile from '../../components/ui/StatTile.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import BarChart from '../../components/ui/BarChart.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useApi } from '../../lib/useApi.js'
import { DEADLINE_TONE, EVENT_COLOR } from '../../lib/status.js'

const AMBER = 'var(--color-amber)'
const AI_PROMPTS = ['Which electives fit my schedule?', 'Am I on track to graduate?', 'Plan my Spring semester']

function greeting() {
  const hour = new Date().getHours()
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
}

function GpaCard({ gpa }) {
  const trend = gpa.trend
  const values = trend.map((term) => term.gpa)
  const low = Math.min(3.5, ...values)
  // Headroom above the top point so its value label stays inside the chart.
  const high = Math.max(3.9, ...values) + 0.15
  const xs = trend.map((_, index) => (trend.length === 1 ? 160 : Math.round(24 + (index * 272) / (trend.length - 1))))
  const y = (value) => Math.round(72 - ((value - low) / (high - low || 1)) * 60)
  const points = trend.map((term, index) => [xs[index], y(term.gpa)])
  const line = points.map((point) => point.join(',')).join(' ')
  const area = points.length ? `${line} ${xs.at(-1)},72 ${xs[0]},72` : ''
  const accent = 'var(--color-accent)'
  const last = points.length - 1

  return (
    <div className="box-border flex min-w-0 flex-[2_1_340px] flex-col gap-2 rounded-[var(--radius-tile)] bg-surface p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-muted">Cumulative GPA</span>
        <Pill tone={gpa.cumulative == null || gpa.cumulative >= 3 ? 'teal' : 'amber'}>{gpa.status}</Pill>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <span className="font-display text-[34px] font-bold tracking-[-0.02em]">{gpa.cumulative?.toFixed(2) ?? '—'}</span>
        {gpa.change != null && (
          <span className="pb-1.5 text-[13px] text-muted">
            {gpa.change === 0 ? 'No change' : `${gpa.change > 0 ? 'Up' : 'Down'} ${Math.abs(gpa.change).toFixed(2)}`} from last semester
          </span>
        )}
      </div>
      {trend.length > 0 ? (
        <svg viewBox="0 0 320 96" width="100%" role="img"
          aria-label={`Term GPA progress: ${trend.map((term) => `${term.term} ${term.gpa.toFixed(2)}`).join(', ')}`}>
          {[12, 42, 72].map((gridY) => <line key={gridY} x1="0" y1={gridY} x2="320" y2={gridY} style={{ stroke: 'var(--color-canvas)' }} />)}
          <polygon points={area} style={{ fill: accent }} fillOpacity="0.12" />
          <polyline points={line} fill="none" style={{ stroke: accent }} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
          {points.map(([x, pointY], index) => index < last
            ? <circle key={index} cx={x} cy={pointY} r="4.5" style={{ fill: accent }} />
            : <circle key={index} cx={x} cy={pointY} r="5.5" style={{ fill: 'var(--color-surface)', stroke: AMBER }} strokeWidth="3" />)}
          {points.map(([x, pointY], index) => (
            <text key={`v${index}`} x={x} y={pointY - 10} fontSize="11" fontWeight="700" style={{ fill: 'var(--color-navy)' }} textAnchor="middle">
              {trend[index].gpa.toFixed(2)}
            </text>
          ))}
          {points.map(([x], index) => (
            <text key={`t${index}`} x={x} y="90" fontSize="11" style={{ fill: 'var(--color-muted)' }} textAnchor="middle">{shortTerm(trend[index])}</text>
          ))}
        </svg>
      ) : (
        <span className="py-6 text-sm text-muted">Your GPA chart appears after your first graded term.</span>
      )}
    </div>
  )
}

// 'Spring 2026' -> 'Spr 26' to fit the chart axis; the current term reads 'Now'.
const shortTerm = (point) => (point.current ? 'Now' : point.term.replace(/^(\w{3})\w*\s20(\d\d)$/, '$1 $2'))


function AskAcadmate({ recommendation }) {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()
  // The question opens in the AI advisor, ready to send.
  const ask = (event) => {
    event.preventDefault()
    navigate('/student/ai-advisor', { state: { question: question.trim() } })
  }
  return (
    <Card dark className="gap-4 md:col-span-2">
      <div className="flex items-center gap-2.5">
        <div className="flex size-9 items-center justify-center rounded-[10px] bg-teal">
          <Icon name="sparkle" color="var(--color-navy)" strokeWidth={2.2} />
        </div>
        <h2 className="m-0 text-lg font-bold text-white">Ask Acadmate</h2>
        <span className="ml-auto text-xs text-haze">AI advisor · reviewed by your department</span>
      </div>

      {recommendation && (
        <div className="flex flex-col gap-2.5 rounded-[14px] bg-navy-raised px-[18px] py-4">
          <span className="text-xs font-bold uppercase tracking-[0.06em] text-teal-bright">{recommendation.title}</span>
          <p className="m-0 text-[15px] leading-relaxed text-frost">{recommendation.text}</p>
          <div className="flex flex-wrap gap-2">
            <Button to="/student/degree-plan" variant="mint" size="sm">Add to degree plan</Button>
            <Button to="/student/ai-advisor" variant="ghostDark" size="sm">Show alternatives</Button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {AI_PROMPTS.map((prompt) => (
          <button key={prompt} type="button" onClick={() => setQuestion(prompt)}
            className="min-h-11 cursor-pointer rounded-full border border-navy-line bg-transparent px-3.5 text-[13px] text-fog hover:bg-navy-raised">
            {prompt}
          </button>
        ))}
      </div>

      <form className="flex items-center gap-2.5" onSubmit={ask}>
        <label htmlFor="acad-ask" className="sr-only">Ask the AI advisor a question</label>
        <input id="acad-ask" type="text" value={question} onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about courses, prerequisites, or your graduation date…"
          className="box-border h-12 min-w-0 flex-1 rounded-xl border border-navy-line bg-ink px-4 text-sm text-white placeholder:text-haze" />
        <button type="submit" aria-label="Send question"
          className="flex size-12 shrink-0 cursor-pointer items-center justify-center rounded-xl border-0 bg-sun">
          <Icon name="send" color="var(--color-navy)" strokeWidth={2.2} />
        </button>
      </form>
    </Card>
  )
}

function Requirements({ requirements, alert }) {
  return (
    <Card className="gap-[18px]">
      <CardHeader title="Degree requirements" action={<Link to="/student/degree-plan" className="text-[13px] font-semibold">Full audit</Link>} />
      {requirements.map((requirement) => (
        <div key={requirement.label} className="flex flex-col gap-2">
          <div className="flex justify-between text-sm">
            <span className="font-semibold">{requirement.label}</span>
            <span className="text-muted">{requirement.count}</span>
          </div>
          <ProgressBar value={requirement.pct} height="h-2.5" color={requirement.warn ? AMBER : undefined} label={requirement.label} />
        </div>
      ))}
      {alert && (
        <Notice tone="amber" className="mt-auto">{alert}</Notice>
      )}
    </Card>
  )
}

function StudyHours({ studyHours }) {
  return (
    <Card className="gap-4">
      <CardHeader title="Study hours" subtitle={`This week · ${studyHours.total} h logged`} action={<Pill tone="teal">Goal {studyHours.goal} h</Pill>} />
      <BarChart max={5} unit="h" label="Study hours"
        data={studyHours.days.map((day) => ({ label: day.day, value: day.hours, highlight: day.today }))} />
    </Card>
  )
}

function Today({ today }) {
  return (
    <Card className="gap-3.5">
      <CardHeader title="Today" action={<span className="text-[13px] text-muted">{today.label}</span>} />
      {today.events.map((event) => (
        <div key={event.id} className="flex items-stretch gap-3.5">
          <span className="w-[52px] shrink-0 pt-3 font-display text-sm font-semibold">{event.time}</span>
          <div className="flex flex-1 flex-col gap-[3px] rounded-xl bg-surface-sunk px-3.5 py-2.5"
            style={{ boxShadow: `inset 4px 0 0 ${EVENT_COLOR[event.type] ?? 'var(--color-accent)'}` }}>
            <span className="text-sm font-bold">{event.title}</span>
            <span className="text-[13px] text-muted">{event.meta}</span>
          </div>
        </div>
      ))}
      {today.events.length === 0 && <Empty>Nothing scheduled today.</Empty>}
    </Card>
  )
}

const FILTERS = ['All', 'Open', 'Due soon', 'Done']

function Deadlines({ tasks }) {
  const [filter, setFilter] = useState('All')
  const visible = tasks.filter((task) => filter === 'All' || (filter === 'Open' ? task.status !== 'Done' : task.status === filter))
  return (
    <Card className="gap-3.5">
      <CardHeader title="Deadlines" action={<Link to="/student/assignments" className="text-[13px] font-semibold">View all</Link>} />
      <SegmentedTabs options={FILTERS} value={filter} onChange={setFilter} label="Filter deadlines" />
      {visible.map((task) => (
        <div key={task.id} className="flex items-center gap-3 border-t border-canvas py-3">
          <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
            <span className="text-sm font-semibold">{task.title}</span>
            <span className="text-xs text-muted">{task.course} · {task.due}</span>
          </div>
          <Pill tone={DEADLINE_TONE[task.status]}>{task.status}</Pill>
        </div>
      ))}
      {visible.length === 0 && <Empty>Nothing here right now.</Empty>}
    </Card>
  )
}

function CurrentCourses({ courses }) {
  return (
    <Card as="section" className="gap-1.5">
      <div className="mb-2"><CardHeader title="Current courses" action={<Link to="/student/courses" className="text-[13px] font-semibold">All my courses</Link>} /></div>
      {courses.map((course) => (
        <div key={course.code} className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] items-center gap-3 border-t border-canvas py-3.5">
          <div className="flex items-center gap-3">
            <Chip tone={course.tone}>{course.code}</Chip>
            <span className="text-sm font-semibold">{course.name}</span>
          </div>
          <span className="text-[13px] text-muted">{course.prof}</span>
          <div className="flex items-center gap-2.5">
            <div className="flex-1"><ProgressBar value={course.pct} height="h-2" label={`${course.name} progress`} /></div>
            <span className="w-[38px] text-[13px] font-bold">{course.pct}%</span>
          </div>
          <span className="text-right text-[13px] text-muted">Current grade <strong className="text-navy">{course.grade}</strong></span>
        </div>
      ))}
      {courses.length === 0 && <Empty>You're not enrolled in any courses this term.</Empty>}
    </Card>
  )
}

export default function StudentDashboard() {
  const { data, error, reload } = useApi('/students/me/dashboard')

  if (error) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading your dashboard…" />

  return (
    <>
      <PageHeader title={`${greeting()}, ${data.student.firstName}`} subtitle={data.student.termLabel} initials={data.student.initials}
        search={{ label: 'Search courses, requirements or deadlines', placeholder: 'Search courses, requirements…' }} />

      <section aria-label="Academic summary" className="flex flex-wrap gap-4">
        <GpaCard gpa={data.gpa} />
        {data.stats.map((stat) => (
          <StatTile key={stat.key} label={stat.label} value={stat.value} pill={{ tone: stat.tone, text: stat.pill }}
            pct={stat.pct} warn={stat.warn} note={stat.note} />
        ))}
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <AskAcadmate recommendation={data.recommendation} />
        <Requirements requirements={data.requirements} alert={data.alert} />
      </section>

      <section className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
        <StudyHours studyHours={data.studyHours} />
        <Today today={data.today} />
        <Deadlines tasks={data.tasks} />
      </section>

      <CurrentCourses courses={data.courses} />
    </>
  )
}
