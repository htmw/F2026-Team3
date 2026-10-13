import Card, { CardHeader } from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import Pill from '../ui/Pill.jsx'
import { Empty, ErrorState, Loading } from '../ui/Status.jsx'
import { useToast } from '../ui/Toast.jsx'
import { api } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'

// Open flagged AI answers with Fix / Dismiss. Shared by Admin overview and Admin AI settings.
export default function FlaggedAnswers() {
  const toast = useToast()
  const { data, error, reload, setData } = useApi('/admin/ai/flags?status=Open')

  const resolve = async (flag, resolution) => {
    setData((current) => ({ flags: current.flags.filter((f) => f.id !== flag.id) }))
    try {
      await api(`/admin/ai/flags/${flag.id}/resolve`, { method: 'POST', body: { resolution } })
      toast.show({ message: resolution === 'Resolved' ? 'Marked as fixed' : 'Flag dismissed' })
    } catch (err) {
      toast.show({ message: err.message })
      reload()
    }
  }

  return (
    <Card as="section" className="gap-3">
      <CardHeader title="Flagged answers" subtitle="Reported by students, advisors or automatic checks"
        action={data && <Pill tone={data.flags.length ? 'amber' : 'teal'}>{data.flags.length} open</Pill>} />
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!data && !error && <Loading label="Loading flagged answers…" />}
      {data?.flags.length === 0 && <Empty>No open flags. Nice.</Empty>}
      {data?.flags.map((flag) => (
        <div key={flag.id} className="flex flex-col gap-2 border-t border-canvas pt-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <span className="text-sm font-bold">“{flag.q}”</span>
            <span className="text-xs text-muted">{flag.when} · {flag.student ?? flag.source}</span>
          </div>
          <span className="text-[13px] text-slate"><strong>Why flagged:</strong> {flag.why}</span>
          {flag.answer && <p className="m-0 whitespace-pre-wrap rounded-xl bg-surface-sunk px-3.5 py-2.5 text-[13px] leading-normal text-slate">{flag.answer}</p>}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => resolve(flag, 'Resolved')}>Mark fixed</Button>
            <Button size="sm" variant="secondary" onClick={() => resolve(flag, 'Dismissed')}>Dismiss</Button>
          </div>
        </div>
      ))}
    </Card>
  )
}
