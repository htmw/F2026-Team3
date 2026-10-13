import PageHeader from '../../components/layout/PageHeader.jsx'
import FlaggedAnswers from '../../components/ai/FlaggedAnswers.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import { ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { useApi } from '../../lib/useApi.js'

// Only the AI parts of the admin overview are built (spec 17); usage, systems and workload come later.
export default function AdminOverview() {
  const { user } = useAuth()
  const { data, error, reload } = useApi('/admin/overview')

  if (error) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading the overview…" />

  return (
    <>
      <PageHeader title="Overview" subtitle="AI advisor activity and answer quality" initials={user?.initials}
        actions={<Button to="/admin/ai" variant="secondary">AI settings</Button>} />
      <Notice tone="indigo">Usage, systems and advisor workload are coming soon.</Notice>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_3fr]">
        <div className="flex flex-col gap-4">
          <Card className="gap-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-muted">AI questions this week</span>
              <Pill tone="teal">AI</Pill>
            </div>
            <span className="font-display text-[28px] font-bold tracking-[-0.02em]">{data.aiQuestions.value}</span>
            <span className="text-[13px] text-muted">{data.aiQuestions.note}</span>
          </Card>

          <Card as="section" className="gap-4">
            <CardHeader title="AI answer quality" subtitle="Last 30 days" />
            {data.aiQuality.map((row) => (
              <div key={row.label} className="flex flex-col gap-2">
                <div className="flex justify-between text-sm">
                  <span className="font-semibold">{row.label}</span>
                  <span className="font-bold">{row.pct == null ? '—' : `${row.pct}%`}</span>
                </div>
                <ProgressBar value={row.pct ?? 0} height="h-2.5" label={row.label} />
                <span className="text-xs text-muted">{row.note}</span>
              </div>
            ))}
          </Card>
        </div>
        <FlaggedAnswers />
      </div>
    </>
  )
}
