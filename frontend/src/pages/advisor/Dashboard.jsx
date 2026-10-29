import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Pill from '../../components/ui/Pill.jsx'
import Avatar from '../../components/ui/Avatar.jsx'
import Button from '../../components/ui/Button.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import StatTile from '../../components/ui/StatTile.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { optimisticAction } from '../../lib/optimistic.js'
import { greeting } from '../../lib/dates.js'
import { CASELOAD_COLOR, REQUEST_TYPE_TONE, RISK_TONE } from '../../lib/status.js'

const QUEUE_TABS = ['All', 'Plans', 'Forms and requests']

// Removes one request from the queue and keeps the count and the "Waiting for you" tile in step; `put` puts it back.
const withoutRequest = (item) => (current) => ({
  ...current,
  queue: current.queue.filter((q) => q.id !== item.id),
  queueTotal: current.queueTotal - 1,
  stats: current.stats.map((s) => (s.key === 'waiting' ? waitingStat(Number(s.value) - 1, s) : s)),
})
const withRequest = (item, index) => (current) => ({
  ...current,
  queue: current.queue.some((q) => q.id === item.id) ? current.queue : current.queue.toSpliced(index, 0, item),
  queueTotal: current.queueTotal + 1,
  stats: current.stats.map((s) => (s.key === 'waiting' ? waitingStat(Number(s.value) + 1, s) : s)),
})
const waitingStat = (n, stat) => ({ ...stat, value: String(n), tag: n ? 'Action' : 'Clear', tone: n ? 'amber' : 'teal' })

// `prechecks` is the advisor's "Run Acadmate pre-checks" setting (spec 27): off hides the check line and never
// disables a quick Approve.
function ApprovalQueue({ items, total, onApprove, prechecks = true }) {
  const [tab, setTab] = useState('All')
  const visible = items.filter((item) => tab === 'All' || (tab === 'Plans') === (item.type === 'Course plan'))
  return (
    <Card as="section" id="approvals" className="gap-3.5 md:col-span-2">
      <CardHeader title="Approval queue" subtitle="Plans and forms students sent from Acadmate"
        action={<Link to="/advisor/approvals" className="text-[13px] font-semibold">All approvals{total > items.length ? ` (${total})` : ''}</Link>} />
      <SegmentedTabs options={QUEUE_TABS} value={tab} onChange={setTab} label="Filter approval queue" />
      {visible.map((item) => (
        <div key={item.id} className="flex flex-wrap items-center gap-3 border-t border-canvas py-3">
          <Avatar name={item.name} initials={item.initials} size="sm" />
          <div className="flex min-w-[220px] flex-1 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-bold">{item.name}</span>
              <Pill tone={REQUEST_TYPE_TONE[item.type]}>{item.type}</Pill>
              <span className="text-xs text-muted">{item.when}</span>
            </div>
            <span className="text-sm">{item.item}</span>
            {prechecks && (
              <span className={`text-[13px] font-semibold ${item.ok ? 'text-teal-ink' : 'text-amber-ink'}`}>
                {item.ok ? '✓' : '!'} Acadmate check: {item.check}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm"
              to={item.type === 'Course plan' ? `/advisor/advisees/${item.studentId}` : `/advisor/approvals?id=${item.id}`}>
              Review
            </Button>
            <Button variant={item.ok || !prechecks ? 'primary' : 'disabled'} size="sm" disabled={prechecks && !item.ok}
              title={item.ok || !prechecks ? undefined : 'Review this request before approving it'} onClick={() => onApprove(item)}>
              Approve
            </Button>
          </div>
        </div>
      ))}
      {visible.length === 0 && <Empty>Nothing waiting in this view.</Empty>}
    </Card>
  )
}

function TodayMeetings({ label, meetings }) {
  return (
    <Card as="section" aria-label="Today's meetings" className="gap-3.5">
      <CardHeader title="Today" action={<span className="text-[13px] text-muted">{label}</span>} />
      {meetings.map((m) => (
        <div key={m.id} className="flex items-center gap-3 border-t border-canvas py-3">
          <span className="w-[52px] shrink-0 font-display text-sm font-semibold">{m.time}</span>
          <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
            <span className="text-sm font-bold">{m.who}</span>
            <span className="text-[13px] text-muted">{m.topic}</span>
          </div>
          {m.action === 'Join'
            ? <a href={m.href} target="_blank" rel="noreferrer" className="text-[13px] font-bold">Join</a>
            : <Link to={m.href} className="text-[13px] font-bold">{m.action}</Link>}
        </div>
      ))}
      {meetings.length === 0 && <Empty>No meetings today.</Empty>}
    </Card>
  )
}

function AttentionList({ students }) {
  return (
    <Card as="section" className="gap-3.5 md:col-span-2">
      <CardHeader title="Students needing attention" subtitle="Flagged by Acadmate · you decide what to do"
        action={<Link to="/advisor/advisees?status=Needs%20attention" className="text-[13px] font-semibold">All advisees</Link>} />
      {students.map((s) => (
        <div key={s.studentId} className="flex flex-wrap items-center gap-3 border-t border-canvas py-3">
          <Avatar name={s.name} initials={s.initials} size="sm" />
          <div className="flex min-w-[220px] flex-1 flex-col gap-1">
            <Link to={`/advisor/advisees/${s.studentId}`} className="text-sm font-bold text-navy">{s.name}</Link>
            <span className="text-sm">{s.flag}</span>
            <span className="text-xs text-muted">GPA {s.gpa} · last contact {s.last}</span>
          </div>
          <Pill tone={RISK_TONE[s.level]}>{s.level}</Pill>
          <Button variant="secondary" size="sm" to={`/advisor/messages?to=${s.userId}`}>Message</Button>
        </div>
      ))}
      {students.length === 0 && <Empty>No one needs attention right now.</Empty>}
    </Card>
  )
}

function Caseload({ caseload, graduation }) {
  const total = caseload.reduce((sum, row) => sum + row.n, 0)
  return (
    <Card as="section" className="gap-3.5">
      <CardHeader title="Caseload" subtitle={`${total} advisees`} />
      {caseload.map((row) => (
        <div key={row.label} className="flex flex-col gap-1.5">
          <div className="flex justify-between text-sm">
            <span className="font-semibold">{row.label}</span>
            <span className="font-bold">{row.n}</span>
          </div>
          <ProgressBar value={total ? (row.n / total) * 100 : 0} color={CASELOAD_COLOR[row.tone]} height="h-2" label={row.label} />
        </div>
      ))}
      <h3 className="m-0 mt-2 text-sm font-bold">Expected graduation</h3>
      <div className="grid grid-cols-3 gap-2.5">
        {graduation.map((bucket) => (
          <div key={bucket.label} className="flex flex-col items-center gap-0.5 rounded-xl bg-surface-sunk px-2 py-3">
            <span className="font-display text-2xl font-bold">{bucket.n}</span>
            <span className="text-xs text-muted">{bucket.label}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default function AdvisorDashboard() {
  const { data, error, reload, setData } = useApi('/advisor/dashboard')
  const { refreshBadges } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  if (error) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading your dashboard…" />

  const approve = async (item) => {
    const index = data.queue.findIndex((q) => q.id === item.id)
    await optimisticAction({
      setData, toast,
      apply: withoutRequest(item),
      revert: withRequest(item, index),
      request: () => api(`/advisor/approvals/${item.id}/approve`, { method: 'POST' }),
      undo: async () => {
        await api(`/advisor/approvals/${item.id}/reopen`, { method: 'POST' })
        reload()
        refreshBadges()
      },
      message: `Approved ${item.name}'s ${item.item.split(' · ')[0]}.`,
    })
    reload()
    refreshBadges()
  }

  return (
    <>
      <PageHeader title={`${greeting()}, ${data.advisor.displayName}`} subtitle={data.advisor.subtitle} initials={data.advisor.initials}
        search={{
          label: 'Search advisees', placeholder: 'Search advisees…',
          onSubmit: (q) => navigate(`/advisor/advisees${q ? `?q=${encodeURIComponent(q)}` : ''}`),
        }}
        actions={<Button variant="secondary" to="/advisor/meetings#office-hours">Set office hours</Button>} />

      <section aria-label="Summary" className="flex flex-wrap gap-4">
        {data.stats.map((stat) => (
          <StatTile key={stat.key} label={stat.label} value={stat.value}
            pill={stat.tag ? { tone: stat.tone, text: stat.tag } : undefined} note={stat.note} />
        ))}
      </section>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <ApprovalQueue items={data.queue} total={data.queueTotal} onApprove={approve} prechecks={data.prechecks} />
        <TodayMeetings label={data.today.label} meetings={data.today.meetings} />
        <AttentionList students={data.attention} />
        <Caseload caseload={data.caseload} graduation={data.graduation} />
      </div>
    </>
  )
}
