import { Link } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import FlaggedAnswers from '../../components/ai/FlaggedAnswers.jsx'
import SystemStatus from '../../components/admin/SystemStatus.jsx'
import BarChart from '../../components/ui/BarChart.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import ExportButton from '../../components/ui/ExportButton.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import StatTile from '../../components/ui/StatTile.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { apiUrl } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'

const TONE_COLOR = { accent: 'var(--color-accent)', violet: 'var(--color-violet)', pink: 'var(--color-pink-ink)' }
const CHANGE_CLASS = { up: 'text-teal-ink', down: 'text-amber-ink', flat: 'text-muted' }
const WAITING_ALERT = 10

// Admin platform overview (spec 30): usage, AI quality, flags, system status and advisor workload.
export default function AdminOverview() {
  const { user } = useAuth()
  const { data, error, reload } = useApi('/admin/overview')

  if (error) {
    return (
      <>
        <PageHeader title="Platform overview" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading the overview…" />

  return (
    <>
      <PageHeader title="Platform overview" subtitle={data.subtitle} initials={user?.initials}
        actions={(
          <>
            <ExportButton href={apiUrl('/admin/overview.csv')} label="Export report" />
            <Button to="/admin/users?invite=1">Invite users</Button>
          </>
        )} />

      <section aria-label="Platform summary" className="flex flex-wrap gap-4">
        {data.stats.map((stat) => (
          <StatTile key={stat.key} label={stat.label} value={stat.value} note={stat.note}
            pill={stat.tag ? { tone: stat.tone, text: stat.tag } : undefined} />
        ))}
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <WeeklyActive weeks={data.weeklyActive.weeks} change={data.weeklyActive.change} />
        <AiQuality rows={data.aiQuality} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FlaggedAnswers compact />
        <Card as="section" className="gap-2">
          <CardHeader title="System status" subtitle="Imports, feeds and email" />
          <SystemStatus systems={data.systems} />
        </Card>
      </div>

      <Workload advisors={data.advisors} />
    </>
  )
}

function WeeklyActive({ weeks, change }) {
  return (
    <Card as="section" className="gap-4 lg:col-span-2">
      <CardHeader title="Weekly active students" subtitle="Students who signed in at least once that week"
        action={<span className={`text-[13px] font-bold ${CHANGE_CLASS[change.direction]}`}>{change.text}</span>} />
      <BarChart data={weeks} label="Weekly active students" />
    </Card>
  )
}

function AiQuality({ rows }) {
  return (
    <Card as="section" className="gap-4">
      <CardHeader title="AI advisor quality" subtitle="This week" />
      {rows.map((row) => (
        <div key={row.label} className="flex flex-col gap-2">
          <div className="flex justify-between text-sm">
            <span className="font-semibold">{row.label}</span>
            <span className="font-bold">{row.pct == null ? '—' : `${row.pct}%`}</span>
          </div>
          <ProgressBar value={row.pct ?? 0} height="h-2.5" color={TONE_COLOR[row.tone]} label={row.label} />
          <span className="text-xs text-muted">{row.note}</span>
        </div>
      ))}
    </Card>
  )
}

function LoadBar({ advisor }) {
  const over = advisor.load === 'Over'
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-24 shrink-0">
        <ProgressBar value={advisor.loadPct} color={over ? 'var(--color-pink-ink)' : undefined}
          label={`${advisor.name}: ${advisor.advisees} of ${advisor.capacity} advisees`} />
      </div>
      <span className={over ? 'text-[13px] font-bold text-pink-ink' : 'text-[13px] text-muted'}>{advisor.load}</span>
    </div>
  )
}

const waitingClass = (n) => (n > WAITING_ALERT ? 'font-bold text-pink-ink' : 'text-muted')

function Workload({ advisors }) {
  return (
    <Card as="section" className="gap-2">
      <CardHeader title="Advisor workload" subtitle="Advisees against capacity, waiting requests and reply time"
        action={<Link to="/admin/advisors" className="text-[13px] font-bold">Manage advisors</Link>} />
      {advisors.length === 0 ? <Empty>No active advisors yet.</Empty> : (
        <>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.06em] text-muted">
                  <th scope="col" className="py-2.5 pr-4 font-bold">Advisor</th>
                  <th scope="col" className="py-2.5 pr-4 font-bold">Advisees</th>
                  <th scope="col" className="py-2.5 pr-4 font-bold">Waiting</th>
                  <th scope="col" className="py-2.5 pr-4 font-bold">Avg. reply</th>
                  <th scope="col" className="py-2.5 font-bold">Load</th>
                </tr>
              </thead>
              <tbody>
                {advisors.map((advisor) => (
                  <tr key={advisor.advisorId} className="border-t border-canvas">
                    <td className="py-3 pr-4 font-semibold">{advisor.name}</td>
                    <td className="py-3 pr-4 text-muted">{advisor.advisees} / {advisor.capacity}</td>
                    <td className={`py-3 pr-4 ${waitingClass(advisor.waiting)}`}>{advisor.waiting}</td>
                    <td className="py-3 pr-4 text-muted">{advisor.avgReply}</td>
                    <td className="py-3"><LoadBar advisor={advisor} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="m-0 flex list-none flex-col p-0 md:hidden">
            {advisors.map((advisor) => (
              <li key={advisor.advisorId} className="flex flex-col gap-1.5 border-t border-canvas py-3">
                <span className="text-sm font-semibold">{advisor.name}</span>
                <span className="text-[13px] text-muted">
                  {advisor.advisees} of {advisor.capacity} advisees · <span className={waitingClass(advisor.waiting)}>
                    {advisor.waiting} waiting</span> · {advisor.avgReply}
                </span>
                <LoadBar advisor={advisor} />
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}
