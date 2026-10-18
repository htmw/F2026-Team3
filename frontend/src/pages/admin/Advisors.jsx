import { useEffect, useId, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty, ListRow } from '../../components/layout/MasterDetail.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import { Field, TextInput } from '../../components/ui/Field.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useSaveState } from '../../lib/useSaveState.js'
import { CAPACITY_TONE, USER_STATUS_TONE } from '../../lib/status.js'

const MIN_CAP = 1
const MAX_CAP = 200 // matches services/admin_advisors.MAX_CAPACITY
const STACKED = '(max-width: 1023px)' // MasterDetail stacks below lg
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const pct = (load, cap) => (cap ? Math.round((load / cap) * 100) : 0)
// Caseload bar: accent, amber above 90% of capacity, pink when over it (same rule as the status pill).
const barColor = (load, cap) => (load > cap ? 'var(--color-pink-ink)' : load > 0.9 * cap ? 'var(--color-amber)' : undefined)
const validCap = (n) => Number.isInteger(n) && n >= MIN_CAP && n <= MAX_CAP
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

// Admin advisors (spec 32): caseloads against capacity, adding advisors, capacity edits and reassignment.
export default function AdminAdvisors() {
  const { user: me } = useAuth()
  const [params, setParams] = useSearchParams()
  const [selectedId, setSelectedId] = useState(() => Number(params.get('id')) || null)
  const [adding, setAdding] = useState(false)
  const detailRef = useRef(null)
  const { data, error, reload, setData } = useApi('/admin/advisors')

  const rows = data?.advisors ?? []
  const selected = rows.find((r) => r.id === selectedId) ?? rows[0] ?? null

  // Keep the selection in the URL (?id=) so a view can be shared or reloaded.
  useEffect(() => {
    if (selected) setParams({ id: String(selected.id) }, { replace: true })
  }, [selected?.id, setParams])

  const pick = (row) => {
    setSelectedId(row.id)
    if (window.matchMedia?.(STACKED).matches) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }

  const changed = (updated) => {
    const byId = new Map(updated.map((r) => [r.id, r]))
    setData((current) => current && { ...current, advisors: current.advisors.map((r) => byId.get(r.id) ?? r) })
    reload()
  }

  const added = (row) => {
    setSelectedId(row.id)
    reload()
  }

  if (error && !data) {
    return (
      <>
        <PageHeader title="Advisors" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading advisors…" />

  return (
    <>
      <PageHeader title="Advisors" subtitle="Caseloads, capacity and reassignment" initials={me?.initials}
        actions={<Button onClick={() => setAdding((on) => !on)} aria-expanded={adding}>Add advisor</Button>} />

      {adding && <AddAdvisorPanel onAdded={added} onCancel={() => setAdding(false)} />}

      <MasterDetail wideList
        list={(
          <Card as="section" aria-label="Advisors" className="gap-2 p-4 sm:p-6">
            {rows.length === 0 ? <Empty>No advisors yet.</Empty> : (
              <AdvisorList rows={rows} selectedId={selected?.id} onSelect={pick} />
            )}
          </Card>
        )}
        detail={(
          <div ref={detailRef} className="scroll-mt-4">
            {selected ? (
              <AdvisorDetail key={selected.id} advisor={selected}
                others={rows.filter((r) => r.id !== selected.id && r.active)} onChanged={changed} />
            ) : <Card><DetailEmpty>Select an advisor to see their caseload.</DetailEmpty></Card>}
          </div>
        )} />
    </>
  )
}

function Caseload({ row, height }) {
  return (
    <ProgressBar value={pct(row.load, row.cap)} color={barColor(row.load, row.cap)} height={height}
      label={`${row.name} caseload ${row.load} of ${row.cap}`} />
  )
}

function InvitedPill({ row }) {
  return row.active ? null : <Pill tone={USER_STATUS_TONE.Invited}>Invited</Pill>
}

function AdvisorList({ rows, selectedId, onSelect }) {
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-[0.06em] text-muted">
              <th scope="col" className="py-2.5 pl-3 pr-4 font-bold">Advisor</th>
              <th scope="col" className="py-2.5 pr-4 font-bold">Caseload</th>
              <th scope="col" className="py-2.5 pr-4 font-bold">Pending</th>
              <th scope="col" className="py-2.5 font-bold">Avg. response</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const active = row.id === selectedId
              return (
                <tr key={row.id} className={`border-t border-canvas ${active ? 'bg-surface-sunk shadow-[inset_4px_0_0_var(--color-accent)]' : ''}`}>
                  <td className="py-2 pl-2 pr-4">
                    <button type="button" aria-pressed={active} onClick={() => onSelect(row)}
                      className="flex cursor-pointer flex-col border-0 bg-transparent p-1 text-left font-semibold text-navy">
                      <span className="flex flex-wrap items-center gap-2">{row.name}<InvitedPill row={row} /></span>
                      <span className="text-xs font-normal text-muted">{row.dept}</span>
                    </button>
                  </td>
                  <td className="w-[34%] py-2 pr-4">
                    <div className="flex flex-col gap-1.5">
                      <span className={row.load > row.cap ? 'font-bold text-pink-ink' : 'text-slate'}>{row.load} / {row.cap}</span>
                      <Caseload row={row} />
                    </div>
                  </td>
                  <td className="py-2 pr-4 text-slate">{row.pending}</td>
                  <td className="py-2 text-muted">{row.resp}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col md:hidden">
        {rows.map((row) => (
          <ListRow key={row.id} selected={row.id === selectedId} onSelect={() => onSelect(row)}>
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="truncate text-sm font-semibold">{row.name}</span>
              <span className="truncate text-xs text-muted">{row.dept} · {row.load} / {row.cap}</span>
              <Caseload row={row} height="h-1" />
            </span>
            {row.active ? <Pill tone={CAPACITY_TONE[row.status]}>{row.status}</Pill> : <InvitedPill row={row} />}
          </ListRow>
        ))}
      </div>
    </>
  )
}

function AddAdvisorPanel({ onAdded, onCancel }) {
  const id = useId()
  const empty = { name: '', email: '', department: '', capacity: '40' }
  const [form, setForm] = useState(empty)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    const capacity = Number(form.capacity)
    const found = {}
    if (!form.name.trim()) found.name = 'Enter their name.'
    if (!EMAIL.test(form.email.trim())) found.email = 'Enter a valid email address.'
    if (!form.department.trim()) found.department = 'Enter a department.'
    if (!validCap(capacity)) found.capacity = `Capacity must be between ${MIN_CAP} and ${MAX_CAP}.`
    setErrors(found)
    setResult(null)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const row = await api('/admin/advisors', {
        method: 'POST',
        body: { name: form.name.trim(), email: form.email.trim(), department: form.department.trim(), capacity },
      })
      setForm(empty)
      setResult({ tone: 'teal', text: 'Advisor added. An invite email is on its way.' })
      onAdded(row)
    } catch (err) {
      if (err.status === 409) setErrors({ email: err.message })
      else if (err.status === 422 && err.details?.length) {
        setErrors(Object.fromEntries(err.details.map((d) => [d.field, d.message])))
      } else setResult({ tone: 'pink', text: errorText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" aria-label="Add an advisor" className="gap-4">
      <CardHeader title="Add an advisor" subtitle="They get an email with a link to set up their account." />
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id={`${id}-name`} label="Full name" error={errors.name}>
            <TextInput id={`${id}-name`} value={form.name} onChange={set('name')} autoComplete="off" maxLength={100} />
          </Field>
          <Field id={`${id}-email`} label="Email" error={errors.email}>
            <TextInput id={`${id}-email`} type="email" value={form.email} onChange={set('email')} autoComplete="off"
              placeholder="name@school.edu" />
          </Field>
          <Field id={`${id}-dept`} label="Department" error={errors.department}>
            <TextInput id={`${id}-dept`} value={form.department} onChange={set('department')} maxLength={80} />
          </Field>
          <Field id={`${id}-cap`} label="Advisee capacity" error={errors.capacity}>
            <TextInput id={`${id}-cap`} type="number" inputMode="numeric" min={MIN_CAP} max={MAX_CAP}
              value={form.capacity} onChange={set('capacity')} />
          </Field>
        </div>
        {result && <Notice tone={result.tone} role="status">{result.text}</Notice>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>{busy ? 'Adding…' : 'Add advisor'}</Button>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}

const defaultCount = (a) => (a.load > a.cap ? a.load - a.cap : Math.min(5, a.load))

function AdvisorDetail({ advisor, others, onChanged }) {
  const id = useId()
  const [cap, setCap] = useState(String(advisor.cap))
  const [capError, setCapError] = useState(null)
  const { label: saveLabel, saving, run } = useSaveState({ idle: 'Save' })
  const [count, setCount] = useState(String(Math.max(1, defaultCount(advisor))))
  const [target, setTarget] = useState(null)
  const [moving, setMoving] = useState(false)
  const [result, setResult] = useState(null)

  const capNumber = Number(cap)
  const clamp = (n) => Math.min(advisor.load, Math.max(1, Number.isFinite(n) ? Math.round(n) : 1))
  const n = clamp(Number(count))

  const saveCap = async () => {
    setCapError(null)
    try {
      const row = await run(() => api(`/admin/advisors/${advisor.id}`, { method: 'PATCH', body: { capacity: capNumber } }))
      onChanged([row])
    } catch (err) {
      setCapError(errorText(err))
    }
  }

  const reassign = async () => {
    setMoving(true)
    setResult(null)
    try {
      const data = await api(`/admin/advisors/${advisor.id}/reassign`, { method: 'POST', body: { toAdvisorId: target, count: n } })
      setResult({ tone: 'teal', text: data.message })
      setTarget(null)
      setCount(String(Math.max(1, defaultCount(data.from))))
      onChanged([data.from, data.to])
    } catch (err) {
      setResult({ tone: 'pink', text: errorText(err) })
    } finally {
      setMoving(false)
    }
  }

  return (
    <Card as="aside" aria-label="Advisor details" className="gap-5">
      <div className="flex flex-col gap-1.5">
        <h2 className="m-0 text-xl font-bold">{advisor.name}</h2>
        <span className="text-[13px] text-muted">{advisor.dept}</span>
        <div className="flex flex-wrap gap-1.5">
          <Pill tone={CAPACITY_TONE[advisor.status]}>{advisor.status}</Pill>
          <InvitedPill row={advisor} />
        </div>
      </div>

      <dl className="m-0 grid grid-cols-3 gap-3">
        <Fact label="Advisees" value={`${advisor.load} of ${advisor.cap}`} alert={advisor.load > advisor.cap} />
        <Fact label="Pending approvals" value={advisor.pending} />
        <Fact label="Avg. response" value={advisor.resp} />
      </dl>
      <Caseload row={advisor} />

      <div className="flex flex-col gap-1.5">
        <Field id={`${id}-cap`} label="Capacity" error={capError}
          hint={capError ? undefined : `Up to ${MAX_CAP} advisees. Reassignment can go 20% over.`}>
          <div className="flex gap-2">
            <TextInput id={`${id}-cap`} type="number" inputMode="numeric" min={MIN_CAP} max={MAX_CAP} className="max-w-[120px]"
              value={cap} onChange={(e) => setCap(e.target.value)} />
            <Button variant="secondary" onClick={saveCap}
              disabled={saving || !validCap(capNumber) || capNumber === advisor.cap}>{saveLabel}</Button>
          </div>
        </Field>
      </div>

      <section aria-labelledby={`${id}-move`} className="flex flex-col gap-3 border-t border-canvas pt-4">
        <h3 id={`${id}-move`} className="m-0 text-base font-bold">
          Move {advisor.load > 0 ? plural(n, 'advisee') : 'advisees'} to
        </h3>
        {advisor.load === 0 ? (
          <span className="text-sm text-muted">No advisees to move.</span>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" aria-label="Fewer" disabled={n <= 1}
                onClick={() => setCount(String(n - 1))}>−</Button>
              <TextInput type="number" inputMode="numeric" min={1} max={advisor.load} aria-label="Number of advisees to move"
                className="h-10 max-w-[80px] text-center" value={count} onChange={(e) => setCount(e.target.value)}
                onBlur={() => setCount(String(n))} />
              <Button variant="secondary" size="sm" aria-label="More" disabled={n >= advisor.load}
                onClick={() => setCount(String(n + 1))}>+</Button>
              <span className="text-[13px] text-muted">of {advisor.load}</span>
            </div>
            {others.length === 0 ? (
              <span className="text-sm text-muted">No other active advisors.</span>
            ) : (
              <SegmentedTabs label="Move to" value={target} onChange={setTarget}
                options={others.map((o) => ({ value: o.id, label: `${o.name} (${o.load}/${o.cap})` }))} />
            )}
            <p className="m-0 text-[13px] text-muted">
              Students with the fewest pending requests and no meeting this week move first. Their pending requests
              move with them.
            </p>
            <div>
              <Button onClick={reassign} disabled={!target || moving}>{moving ? 'Reassigning…' : 'Reassign'}</Button>
            </div>
          </>
        )}
        {result && <Notice tone={result.tone} role="status">{result.text}</Notice>}
      </section>

      <div className="border-t border-canvas pt-4">
        <Link to={`/admin/users?role=advisor&id=${advisor.userId}`} className="text-[13px] font-bold">View account</Link>
      </div>
    </Card>
  )
}

function Fact({ label, value, alert = false }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-[13px] font-bold">{label}</dt>
      <dd className={`m-0 text-sm ${alert ? 'font-bold text-pink-ink' : 'text-slate'}`}>{value}</dd>
    </div>
  )
}
