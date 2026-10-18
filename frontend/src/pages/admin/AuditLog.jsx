import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty, ListRow } from '../../components/layout/MasterDetail.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import ExportButton from '../../components/ui/ExportButton.jsx'
import Pill from '../../components/ui/Pill.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, apiUrl, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useDebounced } from '../../lib/useDebounced.js'

const ROLES = ['All', 'Admin', 'Advisor', 'Student', 'System']
const RANGES = [
  { value: 'today', label: 'Today' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
]
const STACKED = '(max-width: 1023px)' // MasterDetail stacks below lg

// Audit log (spec 36): every change by admins, advisors, students and the system. Filters live in the URL;
// Load more pages by the last event id, so pages never overlap.
export default function AdminAuditLog() {
  const { user: me } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [role, setRole] = useState(ROLES.includes(params.get('role')) ? params.get('role') : 'All')
  const [range, setRange] = useState(RANGES.some((r) => r.value === params.get('range')) ? params.get('range') : '30d')
  const [search, setSearch] = useState(params.get('q') ?? '')
  const [selectedId, setSelectedId] = useState(() => Number(params.get('id')) || null)
  const [more, setMore] = useState({ events: [], cursor: undefined })
  const [loadingMore, setLoadingMore] = useState(false)
  const detailRef = useRef(null)
  const q = useDebounced(search.trim())

  const filters = useMemo(() => {
    const query = new URLSearchParams({ role, range })
    if (q) query.set('q', q)
    return query.toString()
  }, [role, range, q])
  const path = `/admin/audit?${filters}`
  const { data, error, reload } = useApi(path)

  // New filters start from the first page again.
  useEffect(() => setMore({ events: [], cursor: undefined }), [path])

  const events = useMemo(() => [...(data?.events ?? []), ...more.events], [data, more.events])
  const cursor = more.cursor === undefined ? data?.nextCursor : more.cursor
  const selected = events.find((e) => e.id === selectedId) ?? events[0] ?? null

  // Keep the filters and the selection in the URL so a view can be shared or reloaded.
  useEffect(() => {
    const next = new URLSearchParams()
    if (role !== 'All') next.set('role', role)
    if (range !== '30d') next.set('range', range)
    if (q) next.set('q', q)
    if (selected) next.set('id', String(selected.id))
    setParams(next, { replace: true })
  }, [role, range, q, selected?.id, setParams])

  const loadMore = async () => {
    setLoadingMore(true)
    try {
      const page = await api(`${path}&cursor=${cursor}`)
      setMore((current) => ({ events: [...current.events, ...page.events], cursor: page.nextCursor }))
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setLoadingMore(false)
    }
  }

  const pick = (event) => {
    setSelectedId(event.id)
    if (window.matchMedia?.(STACKED).matches) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }

  const header = (
    <PageHeader title="Audit log" subtitle="Every change made by admins, advisors, students and the system"
      initials={me?.initials}
      search={{ label: 'Search the audit log', placeholder: 'Search actions or people…', value: search, onChange: setSearch }}
      actions={<ExportButton href={apiUrl(`/admin/audit.csv?${filters}`)} />} />
  )

  return (
    <>
      {header}
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedTabs label="Filter by role" value={role} onChange={setRole} options={ROLES} />
        <SegmentedTabs label="Date range" value={range} onChange={setRange} options={RANGES} />
      </div>
      {error && !data ? <ErrorState message={error.message} onRetry={reload} /> : !data ? <Loading label="Loading events…" /> : (
        <MasterDetail wideList
          list={(
            <Card as="section" aria-label="Events" className="gap-2 p-4 sm:p-6">
              {events.length === 0 ? <Empty>No events match.</Empty> : (
                <EventList events={events} selectedId={selected?.id} onSelect={pick} />
              )}
              {cursor && (
                <div className="pt-2">
                  <Button variant="secondary" size="sm" onClick={loadMore} disabled={loadingMore}>
                    {loadingMore ? 'Loading…' : 'Load more'}
                  </Button>
                </div>
              )}
            </Card>
          )}
          detail={(
            <div ref={detailRef} className="scroll-mt-4">
              {selected ? <EventDetail event={selected} /> : <Card><DetailEmpty>Select an event to see its details.</DetailEmpty></Card>}
            </div>
          )} />
      )}
    </>
  )
}

function FailedPill({ event }) {
  return event.result === 'Failed' ? <Pill tone="pink">Failed</Pill> : null
}

function EventList({ events, selectedId, onSelect }) {
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-[0.06em] text-muted">
              <th scope="col" className="py-2.5 pl-3 pr-4 font-bold">When</th>
              <th scope="col" className="py-2.5 pr-4 font-bold">Who</th>
              <th scope="col" className="py-2.5 font-bold">Action</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => {
              const active = event.id === selectedId
              return (
                <tr key={event.id} className={`border-t border-canvas ${active ? 'bg-surface-sunk shadow-[inset_4px_0_0_var(--color-accent)]' : ''}`}>
                  <td className="whitespace-nowrap py-2 pl-3 pr-4 align-top text-muted">
                    <button type="button" aria-pressed={active} onClick={() => onSelect(event)}
                      className="cursor-pointer border-0 bg-transparent p-1 text-left text-muted">
                      {event.when}<span className="sr-only">, {event.who}: {event.action}</span>
                    </button>
                  </td>
                  <td className="py-2 pr-4 align-top">
                    <span className="flex flex-col">
                      <span className="font-semibold text-navy">{event.who}</span>
                      <span className="text-xs text-muted">{event.role}</span>
                    </span>
                  </td>
                  <td className="py-2 align-top text-slate">
                    <span className="flex flex-wrap items-center gap-2">{event.action}<FailedPill event={event} /></span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col md:hidden">
        {events.map((event) => (
          <ListRow key={event.id} selected={event.id === selectedId} onSelect={() => onSelect(event)}>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="truncate text-sm">{event.action}</span>
              <span className="truncate text-xs text-muted">{event.when} · {event.who} ({event.role})</span>
            </span>
            <FailedPill event={event} />
          </ListRow>
        ))}
      </div>
    </>
  )
}

const shown = (value) => (value === null || value === undefined ? '—' : typeof value === 'string' ? value : JSON.stringify(value))

function EventDetail({ event }) {
  const rows = [
    ['Time', `${event.when} · ${new Date(event.at).toLocaleString()}`],
    ['Actor', `${event.who} (${event.role})`],
    ['Action', event.action],
    ['Event ID', <code key="id" className="font-mono text-[13px]">{event.eventId}</code>],
    ['IP address', event.role === 'System' ? 'Internal service' : event.ip ?? '—'],
    ['Result', event.result === 'Failed' ? `Failed: ${event.error ?? 'unknown reason'}` : 'Success'],
  ]
  return (
    <Card as="aside" aria-label="Event details" className="gap-4">
      <h2 className="m-0 text-xl font-bold">Event details</h2>
      <dl className="m-0 flex flex-col">
        {rows.map(([label, value]) => (
          <div key={label} className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 border-t border-canvas py-2.5 first:border-t-0">
            <dt className="text-[13px] font-bold">{label}</dt>
            <dd className={`m-0 break-words text-sm ${label === 'Result' && event.result === 'Failed' ? 'font-semibold text-pink-ink' : 'text-slate'}`}>{value}</dd>
          </div>
        ))}
      </dl>
      {event.changes.length > 0 && (
        <section aria-label="Changes" className="flex flex-col gap-2 border-t border-canvas pt-3">
          <h3 className="m-0 text-base font-bold">Changes</h3>
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {event.changes.map((change) => (
              <li key={change.field} className="text-[13px] text-slate">
                <span className="font-semibold text-navy">{change.field}:</span> {shown(change.from)} → {shown(change.to)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {event.link && (
        <div className="border-t border-canvas pt-3">
          <Link to={event.link.to} className="text-[13px] font-bold">{event.link.label}</Link>
        </div>
      )}
    </Card>
  )
}
