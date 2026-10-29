import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import BarChart from '../../components/ui/BarChart.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Icon from '../../components/ui/Icon.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import StatTile from '../../components/ui/StatTile.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { apiUrl } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'

const TONE_COLOR = { accent: 'var(--color-accent)', amber: 'var(--color-amber)', violet: 'var(--color-violet)' }
const STATUS_MS = 3000

// Advisor reports (spec 26): the caseload for one term, with a CSV of every advisee.
export default function AdvisorReports() {
  const { user: me } = useAuth()
  const [params, setParams] = useSearchParams()
  const [downloaded, setDownloaded] = useState(null)
  const term = Number(params.get('term')) || null
  const { data, error, reload } = useApi(`/advisor/reports${term ? `?term=${term}` : ''}`)

  useEffect(() => {
    if (!downloaded) return undefined
    const timer = setTimeout(() => setDownloaded(null), STATUS_MS)
    return () => clearTimeout(timer)
  }, [downloaded])

  const pickTerm = (id) => setParams((current) => {
    const next = new URLSearchParams(current)
    if (id === data?.currentTermId) next.delete('term')
    else next.set('term', String(id))
    return next
  }, { replace: true })

  if (error && !data) {
    return (
      <>
        <PageHeader title="Reports" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading reports…" />

  return (
    <>
      <PageHeader title="Reports" subtitle="Your caseload at a glance" initials={me?.initials}
        actions={(
          <>
            <span role="status" className="text-sm text-muted">{downloaded ? `${downloaded} report downloaded.` : ''}</span>
            <Button href={apiUrl(`/advisor/reports.csv?term=${data.termId}`)} download onClick={() => setDownloaded(data.termLabel)}>
              <Icon name="download" size={18} />Download CSV
            </Button>
          </>
        )} />

      <SegmentedTabs label="Term" options={data.terms.map((t) => ({ value: t.id, label: t.label }))} value={data.termId}
        onChange={pickTerm} />

      <section aria-label="Summary" className="flex flex-wrap gap-4">
        {data.stats.map((stat) => <StatTile key={stat.label} label={stat.label} value={stat.value} note={stat.note} />)}
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StatusBars rows={data.byStatus} />
        <Card as="section" aria-label="Meetings per week" className="gap-4">
          <CardHeader title="Meetings per week" subtitle={data.termLabel} />
          {data.weeks.length === 0 ? <Empty>No weeks in this term yet.</Empty>
            : <BarChart label="Meetings per week" data={data.weeks.map((w, i) => ({ ...w, highlight: i === data.weeks.length - 1 }))} />}
        </Card>
      </div>

      <CheckOnList rows={data.checkOn} />
    </>
  )
}

function StatusBars({ rows }) {
  const total = rows.reduce((sum, row) => sum + row.count, 0)
  return (
    <Card as="section" aria-label="Advisees by status" className="gap-4">
      <CardHeader title="Advisees by status" />
      {rows.map((row) => (
        <div key={row.label} className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-semibold">{row.label}</span>
            <span className="text-[13px] text-muted">{row.count} student{row.count === 1 ? '' : 's'}</span>
          </div>
          <ProgressBar value={total ? (row.count / total) * 100 : 0} color={TONE_COLOR[row.tone]} height="h-2.5"
            label={`${row.label}: ${row.count} of ${total}`} />
        </div>
      ))}
    </Card>
  )
}

function CheckOnList({ rows }) {
  return (
    <Card as="section" aria-label="Students to check on" className="gap-3">
      <CardHeader title="Students to check on" action={(
        <Link to="/advisor/advisees?status=Needs%20attention" className="text-sm font-semibold text-navy underline-offset-2 hover:underline">All advisees</Link>
      )} />
      {rows.length === 0 ? <Empty>Nobody needs a check-in right now.</Empty> : (
        <ul className="m-0 flex list-none flex-col p-0">
          {rows.map((row) => (
            <li key={row.studentId} className="flex flex-wrap items-center gap-3 border-t border-canvas py-3 first:border-t-0">
              <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
                <span className="text-sm font-bold">{row.name}</span>
                <span className="text-[13px] text-muted">{row.reason}</span>
              </div>
              <Button variant="secondary" size="sm" to={row.to}>{row.action}</Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
