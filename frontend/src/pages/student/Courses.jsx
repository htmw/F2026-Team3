import { useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail from '../../components/layout/MasterDetail.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Pill, { Chip } from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import Button from '../../components/ui/Button.jsx'
import Notice from '../../components/ui/Notice.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { useApi } from '../../lib/useApi.js'
import { COURSE_STATUS_TONE } from '../../lib/status.js'

function CourseCard({ course, selected, onSelect }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onSelect}
      className={`box-border flex min-w-0 cursor-pointer flex-col gap-3 rounded-[var(--radius-tile)] border-0 bg-surface p-5 text-left text-navy ${
        selected ? 'shadow-[inset_4px_0_0_var(--color-accent)] ring-2 ring-accent/20' : 'hover:bg-surface-sunk'}`}>
      <div className="flex items-start justify-between gap-2">
        <Chip tone={course.tone}>{course.code}</Chip>
        <span className="text-[13px] text-muted">Grade <strong className="text-navy">{course.grade}</strong></span>
      </div>
      <div className="flex flex-col gap-[3px]">
        <span className="text-[15px] font-bold">{course.name}</span>
        <span className="text-[13px] text-muted">{course.prof}</span>
      </div>
      <div className="flex items-center gap-2.5">
        <div className="flex-1"><ProgressBar value={course.pct} height="h-2" label={`${course.name} progress`} /></div>
        <span className="w-[38px] text-right text-[13px] font-bold">{course.pct}%</span>
      </div>
    </button>
  )
}

function GradeBreakdown({ courseId }) {
  const { data, error, reload } = useApi(`/courses/${courseId}/grades`)
  if (error) {
    return (
      <Notice tone="pink">
        <div className="flex flex-wrap items-center gap-3">
          <span>{error.message}</span>
          <Button variant="secondary" size="sm" onClick={reload}>Try again</Button>
        </div>
      </Notice>
    )
  }
  if (!data) return <span role="status" className="py-3 text-sm text-muted">Loading grades…</span>
  if (data.parts.length === 0) return <Empty>No graded components posted yet.</Empty>
  return (
    <div className="flex flex-col gap-3.5">
      {data.parts.map((part) => (
        <div key={part.label} className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="font-semibold">{part.label} <span className="font-normal text-muted">· {part.weight}%</span></span>
            <span className={part.score != null ? 'font-bold' : 'text-muted'}>{part.display}</span>
          </div>
          <ProgressBar value={part.score ?? 0} label={`${part.label} score`} />
        </div>
      ))}
      {data.weightedScore != null && (
        <span className="text-[13px] text-muted">Weighted score so far <strong className="text-navy">{data.weightedScore}%</strong></span>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="flex flex-col gap-3 border-t border-canvas pt-4">
      <h3 className="m-0 text-[15px] font-bold">{title}</h3>
      {children}
    </div>
  )
}

function CourseDetail({ course, week }) {
  return (
    <Card className="gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <Chip tone={course.tone}>{course.code}</Chip>
          <h2 className="m-0 text-lg font-bold">{course.name}</h2>
        </div>
        <span className="text-[13px] text-muted">{[course.when, course.room, course.credits].join(' · ')}</span>
        <span className="text-[13px] text-muted">
          Instructor <strong className="text-navy">{course.prof}</strong> · Office hours <strong className="text-navy">{course.office}</strong>
        </span>
      </div>

      <Notice tone="indigo" icon="calendar">Next: {course.next}</Notice>

      <Section title="Grade breakdown">
        <GradeBreakdown courseId={course.courseId} />
      </Section>

      <Section title="Upcoming">
        {course.upcoming.map((item) => (
          <div key={`${item.date}-${item.title}`} className="flex items-center gap-3">
            <div className="flex w-12 shrink-0 flex-col items-center rounded-xl bg-surface-sunk py-1.5">
              <span className="text-[11px] font-bold uppercase text-muted">{item.mon}</span>
              <span className="font-display text-lg font-bold leading-tight">{item.day}</span>
            </div>
            <div className="flex min-w-0 flex-col gap-[3px]">
              <span className="text-sm font-semibold">{item.title}</span>
              <span className="text-xs text-muted">{item.meta}</span>
            </div>
          </div>
        ))}
        {course.upcoming.length === 0 && <Empty>Nothing due soon.</Empty>}
      </Section>

      <Section title="This week">
        <div className="grid grid-cols-5 gap-2">
          {week.map((day) => {
            const items = day.items.filter((item) => item.code === course.code)
            return (
              <div key={day.day} className="flex min-w-0 flex-col gap-1.5">
                <span className="text-center text-xs font-bold text-muted">{day.day}</span>
                {items.map((item) => (
                  <div key={item.time} className="flex flex-col rounded-lg bg-surface-sunk px-2 py-1.5 shadow-[inset_3px_0_0_var(--color-accent)]">
                    <span className="font-display text-[13px] font-semibold">{item.time}</span>
                    <span className="truncate text-[11px] text-muted">{item.room}</span>
                  </div>
                ))}
                {items.length === 0 && <span className="py-1.5 text-center text-[13px] text-mist">—</span>}
              </div>
            )
          })}
        </div>
      </Section>
    </Card>
  )
}

function CurrentCourses({ courses, week }) {
  const [selectedId, setSelectedId] = useState(courses[0]?.courseId ?? null)
  const selected = courses.find((course) => course.courseId === selectedId)
  if (courses.length === 0) return <Card><Empty>You're not enrolled in any courses this term.</Empty></Card>
  return (
    <MasterDetail
      list={(
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4">
          {courses.map((course) => (
            <CourseCard key={course.courseId} course={course} selected={course.courseId === selectedId}
              onSelect={() => setSelectedId(course.courseId)} />
          ))}
        </div>
      )}
      detail={selected && <CourseDetail course={selected} week={week} />} />
  )
}

function CompletedCourses({ courses }) {
  return (
    <Card className="gap-2">
      <CardHeader title="Completed courses" />
      {courses.length === 0 ? <Empty>No completed courses yet.</Empty> : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.06em] text-muted">
                <th scope="col" className="py-2.5 pr-4 font-bold">Code</th>
                <th scope="col" className="py-2.5 pr-4 font-bold">Course</th>
                <th scope="col" className="py-2.5 pr-4 font-bold">Term</th>
                <th scope="col" className="py-2.5 text-right font-bold">Grade</th>
              </tr>
            </thead>
            <tbody>
              {courses.map((course) => (
                <tr key={`${course.courseId}-${course.term}`} className="border-t border-canvas">
                  <td className="py-3 pr-4"><Chip tone="gray">{course.code}</Chip></td>
                  <td className="py-3 pr-4 font-semibold">{course.name}</td>
                  <td className="py-3 pr-4 text-muted">{course.term}</td>
                  <td className="py-3 text-right font-bold">{course.grade}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function PlannedCourses({ courses }) {
  if (courses.length === 0) {
    return (
      <Card className="gap-1">
        <Empty>Nothing planned yet — add courses from your degree plan.</Empty>
        <Link to="/student/degree-plan" className="text-[13px] font-semibold">Open degree plan</Link>
      </Card>
    )
  }
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
      {courses.map((course) => (
        <Card key={course.enrollmentId} className="gap-3">
          <div className="flex items-start justify-between gap-2">
            <Chip tone="indigo">{course.code}</Chip>
            <Pill tone={COURSE_STATUS_TONE[course.status] ?? 'gray'}>{course.status}</Pill>
          </div>
          <div className="flex flex-col gap-[3px]">
            <span className="text-[15px] font-bold">{course.name}</span>
            <span className="text-[13px] text-muted">{course.term}</span>
          </div>
          <span className="text-[13px] text-muted">Fulfills <strong className="text-navy">{course.fulfills}</strong></span>
          {course.why && <p className="m-0 text-sm leading-relaxed">{course.why}</p>}
          {course.status === 'Needs approval' && (
            <div className="mt-auto"><Button to="/student/degree-plan" variant="secondary" size="sm">Review in degree plan</Button></div>
          )}
        </Card>
      ))}
    </div>
  )
}

export default function StudentCourses() {
  const { user } = useAuth()
  const { data, error, reload } = useApi('/students/me/courses')
  const [tab, setTab] = useState('current')

  if (error) {
    return (
      <>
        <PageHeader title="My courses" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading your courses…" />

  const { counts } = data
  return (
    <>
      <PageHeader title="My courses" initials={user?.initials}
        subtitle={`${counts.current} course${counts.current === 1 ? '' : 's'} this term`} />

      <SegmentedTabs label="Course list" value={tab} onChange={setTab} options={[
        { value: 'current', label: 'Current', count: counts.current },
        { value: 'completed', label: 'Completed', count: counts.completed },
        { value: 'planned', label: 'Planned', count: counts.planned },
      ]} />

      {tab === 'current' && <CurrentCourses courses={data.current} week={data.week} />}
      {tab === 'completed' && <CompletedCourses courses={data.completed} />}
      {tab === 'planned' && <PlannedCourses courses={data.planned} />}
    </>
  )
}
