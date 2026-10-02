import { useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Pill, { Chip } from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import {
  student, gpaTrend, stats, requirements, studyHours, todayEvents, tasks, STATUS_TONE, courses, aiPrompts,
} from '../../data/student.js'

const AMBER = '#D97706'

function GpaCard() {
  const xs = [24, 112, 200, 296]
  const y = (gpa) => Math.round(72 - ((gpa - 3.5) / 0.5) * 60)
  const points = gpaTrend.map((term, index) => [xs[index], y(term.gpa)])
  const line = points.map((point) => point.join(',')).join(' ')
  const area = `${line} ${xs[3]},72 ${xs[0]},72`
  const accent = 'var(--color-accent)'

  return (
    <div className="box-border flex min-w-0 flex-[2_1_340px] flex-col gap-2 rounded-[var(--radius-tile)] bg-surface p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-muted">Cumulative GPA</span>
        <Pill tone="teal">On track</Pill>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <span className="font-display text-[34px] font-bold tracking-[-0.02em]">3.72</span>
        <span className="pb-1.5 text-[13px] text-muted">Up 0.08 from last semester</span>
      </div>
      <svg viewBox="0 0 320 96" width="100%" role="img"
        aria-label={`Term GPA progress: ${gpaTrend.map((term) => `${term.term} ${term.gpa.toFixed(2)}`).join(', ')}`}>
        {[12, 42, 72].map((gridY) => <line key={gridY} x1="0" y1={gridY} x2="320" y2={gridY} stroke="#EEF1F4" />)}
        <polygon points={area} style={{ fill: accent }} fillOpacity="0.12" />
        <polyline points={line} fill="none" style={{ stroke: accent }} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        {points.map(([x, pointY], index) => index < 3
          ? <circle key={index} cx={x} cy={pointY} r="4.5" style={{ fill: accent }} />
          : <circle key={index} cx={x} cy={pointY} r="5.5" fill="#FFFFFF" stroke={AMBER} strokeWidth="3" />)}
        {points.map(([x, pointY], index) => (
          <text key={`v${index}`} x={x} y={pointY - 10} fontSize="11" fontWeight="700" fill="#13212E" textAnchor="middle">
            {gpaTrend[index].gpa.toFixed(2)}
          </text>
        ))}
        {points.map(([x], index) => (
          <text key={`t${index}`} x={x} y="90" fontSize="11" fill="#52606D" textAnchor="middle">{gpaTrend[index].term}</text>
        ))}
      </svg>
    </div>
  )
}

function StatCard({ stat }) {
  return (
    <div className="box-border flex min-w-0 flex-[1_1_170px] flex-col gap-2.5 rounded-[var(--radius-tile)] bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <span className="text-sm font-semibold text-muted">{stat.label}</span>
        <Pill tone={stat.tone}>{stat.pill}</Pill>
      </div>
      <span className="font-display text-[28px] font-bold tracking-[-0.02em]">{stat.value}</span>
      <ProgressBar value={stat.pct} color={stat.warn ? AMBER : undefined} label={stat.label} />
      <span className="text-[13px] text-muted">{stat.note}</span>
    </div>
  )
}

function AskAcadmate() {
  const [question, setQuestion] = useState('')
  return (
    <Card dark className="gap-4 md:col-span-2">
      <div className="flex items-center gap-2.5">
        <div className="flex size-9 items-center justify-center rounded-[10px] bg-teal">
          <Icon name="sparkle" color="#13212E" strokeWidth={2.2} />
        </div>
        <h2 className="m-0 text-lg font-bold text-white">Ask Acadmate</h2>
        <span className="ml-auto text-xs text-haze">AI advisor · reviewed by your department</span>
      </div>

      <div className="flex flex-col gap-2.5 rounded-[14px] bg-navy-raised px-[18px] py-4">
        <span className="text-xs font-bold uppercase tracking-[0.06em] text-teal-bright">Spring 2027 recommendation</span>
        <p className="m-0 text-[15px] leading-relaxed text-frost">
          After this semester you will have 6 credits left. Taking your capstone plus one AI elective in Spring keeps you
          on track to graduate in May 2027. Your Algorithms grade also qualifies you to skip the advanced-theory prerequisite.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button to="/student/degree-plan" variant="mint" size="sm">Add to degree plan</Button>
          <Button to="/student/ai-advisor" variant="ghostDark" size="sm">Show alternatives</Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {aiPrompts.map((prompt) => (
          <button key={prompt} type="button" onClick={() => setQuestion(prompt)}
            className="min-h-11 cursor-pointer rounded-full border border-navy-line bg-transparent px-3.5 text-[13px] text-fog hover:bg-navy-raised">
            {prompt}
          </button>
        ))}
      </div>

      <form className="flex items-center gap-2.5" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="acad-ask" className="sr-only">Ask the AI advisor a question</label>
        <input id="acad-ask" type="text" value={question} onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about courses, prerequisites, or your graduation date…"
          className="box-border h-12 min-w-0 flex-1 rounded-xl border border-navy-line bg-ink px-4 text-sm text-white placeholder:text-haze" />
        <button type="submit" aria-label="Send question"
          className="flex size-12 shrink-0 cursor-pointer items-center justify-center rounded-xl border-0 bg-sun">
          <Icon name="send" color="#13212E" strokeWidth={2.2} />
        </button>
      </form>
    </Card>
  )
}

function Requirements() {
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
      <div className="mt-auto flex items-start gap-2.5 rounded-xl bg-amber-soft px-3.5 py-3">
        <Icon name="alert" size={18} color="#92400E" strokeWidth={2.2} className="mt-px shrink-0" />
        <span className="text-[13px] leading-normal text-amber-deep">
          Capstone registration opens Nov 3. Pre-approval form is still missing.
        </span>
      </div>
    </Card>
  )
}

function StudyHours() {
  const total = studyHours.reduce((sum, day) => sum + day.hours, 0)
  return (
    <Card className="gap-4">
      <CardHeader title="Study hours" subtitle={`This week · ${total} h logged`} action={<Pill tone="teal">Goal 20 h</Pill>} />
      <div className="flex h-[180px] items-end gap-2.5 border-b border-line-soft pt-2" role="img"
        aria-label={studyHours.map((day) => `${day.day} ${day.hours} hours`).join(', ')}>
        {studyHours.map((day) => (
          <div key={day.day} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
            <span className="text-[11px] font-bold text-muted">{day.hours}h</span>
            <div className="w-full max-w-[34px] rounded-[8px_8px_4px_4px]"
              style={{ height: Math.round((day.hours / 5) * 130), background: day.today ? AMBER : 'var(--color-accent)' }} />
          </div>
        ))}
      </div>
      <div className="flex gap-2.5">
        {studyHours.map((day) => <span key={day.day} className="flex-1 text-center text-xs text-muted">{day.day}</span>)}
      </div>
    </Card>
  )
}

function Today() {
  return (
    <Card className="gap-3.5">
      <CardHeader title="Today" action={<span className="text-[13px] text-muted">{student.today}</span>} />
      {todayEvents.map((event) => (
        <div key={event.time} className="flex items-stretch gap-3.5">
          <span className="w-[52px] shrink-0 pt-3 font-display text-sm font-semibold">{event.time}</span>
          <div className="flex flex-1 flex-col gap-[3px] rounded-xl bg-surface-sunk px-3.5 py-2.5"
            style={{ boxShadow: `inset 4px 0 0 ${event.color}` }}>
            <span className="text-sm font-bold">{event.title}</span>
            <span className="text-[13px] text-muted">{event.meta}</span>
          </div>
        </div>
      ))}
    </Card>
  )
}

const FILTERS = ['All', 'Open', 'Due soon', 'Done']

function Deadlines() {
  const [filter, setFilter] = useState('All')
  const visible = tasks.filter((task) => filter === 'All' || (filter === 'Open' ? task.status !== 'Done' : task.status === filter))
  return (
    <Card className="gap-3.5">
      <CardHeader title="Deadlines" action={<Link to="/student/assignments" className="text-[13px] font-semibold">View all</Link>} />
      <div role="group" aria-label="Filter deadlines" className="flex flex-wrap gap-1.5">
        {FILTERS.map((item) => (
          <button key={item} type="button" aria-pressed={filter === item} onClick={() => setFilter(item)}
            className={`min-h-9 cursor-pointer rounded-full border px-3.5 text-[13px] font-semibold ${
              filter === item ? 'border-navy bg-navy text-white' : 'border-line bg-surface text-navy'}`}>
            {item}
          </button>
        ))}
      </div>
      {visible.map((task) => (
        <div key={task.title} className="flex items-center gap-3 border-t border-canvas py-3">
          <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
            <span className="text-sm font-semibold">{task.title}</span>
            <span className="text-xs text-muted">{task.course} · {task.due}</span>
          </div>
          <Pill tone={STATUS_TONE[task.status]}>{task.status}</Pill>
        </div>
      ))}
      {visible.length === 0 && <span className="py-3 text-sm text-muted">Nothing here right now.</span>}
    </Card>
  )
}

function CurrentCourses() {
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
    </Card>
  )
}

export default function StudentDashboard() {
  return (
    <>
      <PageHeader title={`Good morning, ${student.firstName}`} subtitle={student.term} initials={student.initials}
        search={{ label: 'Search courses, requirements or deadlines', placeholder: 'Search courses, requirements…' }} />

      <section aria-label="Academic summary" className="flex flex-wrap gap-4">
        <GpaCard />
        {stats.map((stat) => <StatCard key={stat.label} stat={stat} />)}
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <AskAcadmate />
        <Requirements />
      </section>

      <section className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
        <StudyHours />
        <Today />
        <Deadlines />
      </section>

      <CurrentCourses />
    </>
  )
}
