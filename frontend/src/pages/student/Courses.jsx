import { useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail from '../../components/layout/MasterDetail.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Pill, { Chip, PILL_TONES } from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useDebounced } from '../../lib/useDebounced.js'
import { COURSE_STATUS_TONE } from '../../lib/status.js'

function CourseCard({ course, selected, onSelect }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onSelect}
      className={`box-border flex min-w-0 cursor-pointer flex-col gap-3 rounded-[var(--radius-tile)] border-2 bg-surface p-5 text-left text-navy ${
        selected ? 'border-accent shadow-[0_6px_20px_rgba(19,33,46,.10)]' : 'border-transparent hover:bg-surface-sunk'}`}>
      <div className="flex items-center justify-between gap-2">
        <Chip tone={course.tone}>{course.code}</Chip>
        <span className="text-[13px] text-muted">{course.credits}</span>
      </div>
      <div className="flex flex-col gap-[3px]">
        <span className="text-[15px] font-bold">{course.name}</span>
        <span className="text-[13px] text-muted">{[course.prof, course.when].filter(Boolean).join(' · ')}</span>
      </div>
      <div className="flex items-center gap-2.5">
        <div className="flex-1"><ProgressBar value={course.pct} height="h-2" label={`${course.name} progress`} /></div>
        <span className="shrink-0 text-[13px] font-bold">{course.pct}% done</span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-canvas pt-3 text-[13px] text-muted">
        <span className="min-w-0">{course.next ? <>Next: <strong className="text-navy">{course.next}</strong></> : 'Nothing due soon'}</span>
        <span>Grade <strong className="text-navy">{course.grade}</strong></span>
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
        <div key={part.label} className="grid grid-cols-[minmax(0,1fr)_44px_minmax(60px,2fr)_76px] items-center gap-3 text-sm">
          <span className="truncate font-semibold">{part.label}</span>
          <span className="text-muted">{part.weight}%</span>
          <ProgressBar value={part.score ?? 0} label={`${part.label} score`} />
          <span className={`text-right ${part.score != null ? 'font-bold' : 'text-muted'}`}>{part.display}</span>
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

const LINK = 'inline-flex items-center gap-1.5 text-[13px] font-semibold'

function CourseDetail({ course }) {
  return (
    <Card as="section" aria-label="Course details" className="gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-3">
            <Chip tone={course.tone}>{course.code}</Chip>
            <h2 className="m-0 text-lg font-bold">{course.name}</h2>
          </div>
          <span className="text-[13px] text-muted">{[course.prof, course.when, course.room].filter(Boolean).join(' · ')}</span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-xs font-semibold text-muted">Current grade</span>
          <span className="font-display text-[32px] font-bold leading-none">{course.grade}</span>
        </div>
      </div>

      {course.insight && (
        <div className="flex gap-3 rounded-[14px] bg-teal-soft px-4 py-3.5">
          <Icon name="sparkle" color="var(--color-teal-ink)" strokeWidth={2.2} />
          <div className="flex flex-col gap-1">
            <span className="text-xs font-bold uppercase tracking-[0.06em] text-teal-ink">Acadmate insight</span>
            <p className="m-0 text-sm leading-relaxed">{course.insight}</p>
          </div>
        </div>
      )}

      <Section title="Grade breakdown">
        <GradeBreakdown courseId={course.courseId} />
      </Section>

      <Section title="Coming up">
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

      <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-canvas pt-4">
        {course.siteUrl && (
          <a href={course.siteUrl} target="_blank" rel="noreferrer" className={LINK}>
            Open course site <Icon name="external" size={14} />
          </a>
        )}
        <Link to="/student/ai-advisor" state={{ question: `Help me with ${course.code} ${course.name}` }} className={LINK}>
          <Icon name="sparkle" size={14} /> Ask Acadmate about this course
        </Link>
        {course.office && (
          <Link to={`/student/book-meeting?with=instructor&course=${encodeURIComponent(course.code)}`} className={LINK}>
            <Icon name="calendar" size={14} /> Office hours: {course.office}
          </Link>
        )}
      </div>
    </Card>
  )
}

function WeeklyTimetable({ week }) {
  return (
    <Card className="gap-4">
      <CardHeader title="Weekly timetable" action={<Link to="/student/schedule" className="text-[13px] font-semibold">Open full schedule</Link>} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-3">
        {week.map((day) => (
          <div key={day.day} className="flex min-w-0 flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">{day.day}</span>
            {day.items.map((item) => (
              <div key={`${item.time}-${item.code}-${item.kind}`}
                className={`flex flex-col gap-0.5 rounded-xl px-3 py-2.5 ${PILL_TONES[item.kind === 'office' ? 'gray' : item.tone]}`}>
                <span className="font-display text-sm font-semibold">{item.time}</span>
                {item.kind === 'office'
                  ? <span className="text-xs">Office hrs · {item.code} · Optional</span>
                  : <span className="text-xs">{item.code} · {item.room}</span>}
              </div>
            ))}
            {day.items.length === 0 && <span className="rounded-xl bg-surface-sunk px-3 py-2.5 text-xs text-muted">No classes</span>}
          </div>
        ))}
      </div>
    </Card>
  )
}

function CurrentCourses({ courses, week }) {
  const [selectedId, setSelectedId] = useState(null)
  // Default to the first visible course (also after a search hides the selected one).
  const selected = courses.find((course) => course.courseId === selectedId) ?? courses[0]
  return (
    <>
      {courses.length === 0 ? <Card><Empty>You're not enrolled in any courses this term.</Empty></Card> : (
        <MasterDetail
          list={(
            <section aria-label="Current courses" className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4">
              {courses.map((course) => (
                <CourseCard key={course.courseId} course={course} selected={course.courseId === selected?.courseId}
                  onSelect={() => setSelectedId(course.courseId)} />
              ))}
            </section>
          )}
          detail={selected && <CourseDetail course={selected} />} />
      )}
      <WeeklyTimetable week={week} />
    </>
  )
}

function CompletedCourses({ courses, summary }) {
  return (
    <Card className="gap-2">
      <CardHeader title="Completed courses" action={courses.length > 0 && (
        <span className="text-[13px] text-muted">
          {summary.credits} credits · cumulative GPA <strong className="text-navy">{summary.gpa?.toFixed(2) ?? '—'}</strong>
        </span>
      )} />
      {courses.length === 0 ? <Empty>No completed courses yet.</Empty> : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.06em] text-muted">
                <th scope="col" className="py-2.5 pr-4 font-bold">Code</th>
                <th scope="col" className="py-2.5 pr-4 font-bold">Course</th>
                <th scope="col" className="py-2.5 pr-4 font-bold">Term</th>
                <th scope="col" className="py-2.5 pr-4 font-bold">Credits</th>
                <th scope="col" className="py-2.5 text-right font-bold">Grade</th>
              </tr>
            </thead>
            <tbody>
              {courses.map((course) => (
                <tr key={`${course.courseId}-${course.term}`} className="border-t border-canvas">
                  <td className="py-3 pr-4"><Chip tone="gray">{course.code}</Chip></td>
                  <td className="py-3 pr-4 font-semibold">{course.name}</td>
                  <td className="py-3 pr-4 text-muted">{course.term}</td>
                  <td className="py-3 pr-4 text-muted">{course.credits}</td>
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

function PlannedCourses({ courses, notice }) {
  const toast = useToast()
  const { refreshBadges } = useAuth()
  const [sending, setSending] = useState(false)

  const send = async () => {
    setSending(true)
    try {
      await api('/students/me/plan/submit', { method: 'POST' })
      toast.show({ message: 'Sent to your advisor' })
      refreshBadges()
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {notice && <Notice tone="amber">{notice}</Notice>}
      {courses.length === 0 ? (
        <Card className="gap-1">
          <Empty>Nothing planned yet — add courses from your degree plan.</Empty>
          <Link to="/student/degree-plan" className="text-[13px] font-semibold">Open degree plan</Link>
        </Card>
      ) : (
        <section aria-label="Planned courses" className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          {courses.map((course) => (
            <Card key={course.enrollmentId} className="gap-3">
              <div className="flex items-start justify-between gap-2">
                <Chip tone="indigo">{course.code}</Chip>
                <Pill tone={COURSE_STATUS_TONE[course.status] ?? 'gray'}>{course.status}</Pill>
              </div>
              <span className="text-[15px] font-bold">{course.name}</span>
              {course.why && <p className="m-0 text-sm leading-relaxed">{course.why}</p>}
              <span className="text-[13px] text-muted">
                {course.term} · {course.credits} credits{course.fulfills && <> · fulfills <strong className="text-navy">{course.fulfills}</strong></>}
              </span>
              <div className="mt-auto flex flex-wrap gap-2">
                <Button size="sm" onClick={send} disabled={sending}>{sending ? 'Sending…' : 'Send to advisor'}</Button>
                <Button to={`/student/degree-plan?swap=${course.enrollmentId}`} variant="secondary" size="sm">Swap course</Button>
              </div>
            </Card>
          ))}
        </section>
      )}
    </div>
  )
}

const matches = (query) => (course) => !query || `${course.code} ${course.name}`.toLowerCase().includes(query)

export default function StudentCourses() {
  const { user } = useAuth()
  const { data, error, reload } = useApi('/students/me/courses')
  const [tab, setTab] = useState('current')
  const [search, setSearch] = useState('')
  const query = useDebounced(search).trim().toLowerCase()

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
  const filter = matches(query)
  return (
    <>
      <PageHeader title="My courses" initials={user?.initials} subtitle={data.subtitle}
        search={{ label: 'Search your courses', placeholder: 'Search your courses…', value: search, onChange: setSearch }}
        actions={data.addDropUrl && (
          <Button href={data.addDropUrl} variant="secondary" target="_blank" rel="noreferrer">
            <Icon name="plus" size={16} /> Add or drop a course
          </Button>
        )} />

      <SegmentedTabs label="Course list view" value={tab} onChange={setTab} options={[
        { value: 'current', label: 'Current', count: counts.current },
        { value: 'completed', label: 'Completed', count: counts.completed },
        { value: 'planned', label: 'Planned', count: counts.planned },
      ]} />

      {tab === 'current' && <CurrentCourses courses={data.current.filter(filter)} week={data.week} />}
      {tab === 'completed' && <CompletedCourses courses={data.completed.filter(filter)} summary={data.completedSummary} />}
      {tab === 'planned' && <PlannedCourses courses={data.planned.filter(filter)} notice={data.plannedNotice} />}
    </>
  )
}
