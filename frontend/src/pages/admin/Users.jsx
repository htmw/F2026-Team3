import { useEffect, useId, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty, ListRow } from '../../components/layout/MasterDetail.jsx'
import InvitePanel from '../../components/admin/InvitePanel.jsx'
import ImportPanel from '../../components/admin/ImportPanel.jsx'
import Avatar from '../../components/ui/Avatar.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import ConfirmInline from '../../components/ui/ConfirmInline.jsx'
import { Field, Select } from '../../components/ui/Field.jsx'
import Pill from '../../components/ui/Pill.jsx'
import SearchInput from '../../components/ui/SearchInput.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useDebounced } from '../../lib/useDebounced.js'
import { useFlash } from '../../lib/useSaveState.js'
import { ROLE_TONE, USER_STATUS_TONE } from '../../lib/status.js'

const PAGE_SIZE = 50
const TABS = [
  { value: 'all', label: 'All', key: 'All' },
  { value: 'student', label: 'Students', key: 'Students' },
  { value: 'advisor', label: 'Advisors', key: 'Advisors' },
  { value: 'admin', label: 'Admins', key: 'Admins' },
]
const ROLE_VALUE = { Student: 'student', Advisor: 'advisor', Admin: 'admin' }
const SELF_HINT = "You can't change your own account here."

// Admin users (spec 31): list with role tabs, search and paging; invite and CSV import panels; details aside.
export default function AdminUsers() {
  const { user: me } = useAuth()
  const [params, setParams] = useSearchParams()
  const [role, setRole] = useState(TABS.some((t) => t.value === params.get('role')) ? params.get('role') : 'all')
  const [search, setSearch] = useState(params.get('q') ?? '')
  const [page, setPage] = useState(1)
  const [panel, setPanel] = useState(params.get('invite') === '1' ? 'invite' : null)
  const [selected, setSelected] = useState(null)
  const [wantedId, setWantedId] = useState(() => Number(params.get('id')) || null) // from a shared ?id= link
  const q = useDebounced(search.trim())

  const path = `/admin/users?role=${role}&q=${encodeURIComponent(q)}&page=${page}&pageSize=${PAGE_SIZE}`
  const { data, error, loading, reload, setData } = useApi(path)

  // Keep role / q / id in the URL so a view can be shared or reloaded; the invite flag is one-shot.
  useEffect(() => {
    const next = new URLSearchParams()
    if (role !== 'all') next.set('role', role)
    if (q) next.set('q', q)
    const id = selected?.id ?? wantedId
    if (id) next.set('id', String(id))
    setParams(next, { replace: true })
  }, [role, q, selected, wantedId, setParams])

  // A shared ?id= link selects that user once the first page loads (if they're on it).
  useEffect(() => {
    if (!wantedId || !data) return
    setSelected(data.rows.find((r) => r.id === wantedId) ?? null)
    setWantedId(null)
  }, [data, wantedId])

  useEffect(() => { setPage(1) }, [role, q])

  const changed = (row) => {
    setSelected(row)
    setData((current) => current && { ...current, rows: current.rows.map((r) => (r.id === row.id ? row : r)) })
    reload() // counts, tabs and advisor loads may have moved
  }

  if (error && !data) {
    return (
      <>
        <PageHeader title="Users" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading users…" />

  const togglePanel = (name) => setPanel((current) => (current === name ? null : name))
  const from = data.total === 0 ? 0 : (data.page - 1) * data.pageSize + 1
  const to = Math.min(data.page * data.pageSize, data.total)

  return (
    <>
      <PageHeader title="Users" subtitle="Students, advisors and admins on Acadmate" initials={me?.initials}
        actions={(
          <>
            <Button variant="secondary" onClick={() => togglePanel('import')} aria-expanded={panel === 'import'}>Import CSV</Button>
            <Button onClick={() => togglePanel('invite')} aria-expanded={panel === 'invite'}>Invite users</Button>
          </>
        )} />

      {panel === 'invite' && <InvitePanel onDone={reload} onCancel={() => setPanel(null)} />}
      {panel === 'import' && <ImportPanel onDone={reload} onCancel={() => setPanel(null)} />}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedTabs label="Filter by role" value={role} onChange={setRole}
          options={TABS.map((t) => ({ value: t.value, label: t.label, count: (data.counts[t.key] ?? 0).toLocaleString() }))} />
        <SearchInput label="Search users by name" placeholder="Search by name…" value={search} onChange={setSearch} />
      </div>

      <MasterDetail wideList
        list={(
          <Card as="section" aria-label="Users" aria-busy={loading} className="gap-2 p-4 sm:p-6">
            {data.rows.length === 0 ? <Empty>No users match.</Empty> : (
              <UserList rows={data.rows} selectedId={selected?.id} onSelect={setSelected} />
            )}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-canvas pt-3">
              <span className="text-[13px] text-muted" aria-live="polite">
                Showing {from.toLocaleString()}–{to.toLocaleString()} of {data.total.toLocaleString()}
              </span>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button size="sm" variant="secondary" disabled={to >= data.total || loading} onClick={() => setPage((p) => p + 1)}>Next</Button>
              </div>
            </div>
          </Card>
        )}
        detail={selected ? (
          <UserDetail key={selected.id} user={selected} advisors={data.advisors} programs={data.programs}
            self={selected.id === me?.id} onChanged={changed} />
        ) : <Card><DetailEmpty>Select a user to see their details.</DetailEmpty></Card>} />
    </>
  )
}

function UserList({ rows, selectedId, onSelect }) {
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-[0.06em] text-muted">
              <th scope="col" className="py-2.5 pr-4 font-bold">Name</th>
              <th scope="col" className="py-2.5 pr-4 font-bold">Role</th>
              <th scope="col" className="py-2.5 pr-4 font-bold">Program or department</th>
              <th scope="col" className="py-2.5 pr-4 font-bold">Status</th>
              <th scope="col" className="py-2.5 font-bold">Last active</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const active = row.id === selectedId
              return (
                <tr key={row.id} className={`border-t border-canvas ${active ? 'bg-surface-sunk shadow-[inset_4px_0_0_var(--color-accent)]' : ''}`}>
                  <td className="py-2 pr-4">
                    <button type="button" aria-pressed={active} onClick={() => onSelect(row)}
                      className="flex cursor-pointer items-center gap-2.5 border-0 bg-transparent p-1 text-left font-semibold text-navy">
                      <Avatar initials={row.initials} tone={ROLE_TONE[row.role]} size="sm" />
                      <span className="flex flex-col">
                        <span>{row.name}</span>
                        <span className="text-xs font-normal text-muted">{row.email}</span>
                      </span>
                    </button>
                  </td>
                  <td className="py-2 pr-4"><Pill tone={ROLE_TONE[row.role]}>{row.role}</Pill></td>
                  <td className="py-2 pr-4 text-muted">{row.dept}</td>
                  <td className="py-2 pr-4"><Pill tone={USER_STATUS_TONE[row.status]}>{row.status}</Pill></td>
                  <td className="py-2 text-muted">{row.lastActive}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col md:hidden">
        {rows.map((row) => (
          <ListRow key={row.id} selected={row.id === selectedId} onSelect={() => onSelect(row)}>
            <Avatar initials={row.initials} tone={ROLE_TONE[row.role]} size="sm" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm font-semibold">{row.name}</span>
              <span className="truncate text-xs text-muted">{row.dept} · {row.lastActive}</span>
            </span>
            <Pill tone={USER_STATUS_TONE[row.status]}>{row.status}</Pill>
          </ListRow>
        ))}
      </div>
    </>
  )
}

function UserDetail({ user, advisors, programs, self, onChanged }) {
  const id = useId()
  const toast = useToast()
  const [saving, setSaving] = useState(false)
  const [resetSent, flashReset] = useFlash()
  const invited = user.status === 'Invited'
  const isStudent = user.role === 'Student'

  const patch = async (body, message) => {
    setSaving(true)
    try {
      onChanged(await api(`/admin/users/${user.id}`, { method: 'PATCH', body }))
      if (message) toast.show({ message })
      return true
    } catch (err) {
      toast.show({ message: errorText(err) })
      return false
    } finally {
      setSaving(false)
    }
  }

  const sendReset = async () => {
    try {
      await api(`/admin/users/${user.id}/reset`, { method: 'POST' })
      flashReset()
    } catch (err) {
      toast.show({ message: errorText(err) })
    }
  }

  const changeAdvisor = (value) => {
    const advisorId = value ? Number(value) : null
    const name = advisors.find((a) => a.id === advisorId)?.name
    patch({ advisorId }, advisorId ? `Advisor changed to ${name}` : 'Advisor removed')
  }

  return (
    <Card as="aside" aria-label="User details" className="gap-5">
      <div className="flex items-center gap-4">
        <Avatar initials={user.initials} tone={ROLE_TONE[user.role]} size="lg" />
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="m-0 text-xl font-bold">{user.name}</h2>
          <span className="truncate text-[13px] text-muted">{user.email}</span>
          <div className="flex flex-wrap gap-1.5">
            <Pill tone={ROLE_TONE[user.role]}>{user.role}</Pill>
            <Pill tone={USER_STATUS_TONE[user.status]}>{user.status}</Pill>
          </div>
        </div>
      </div>

      <Field id={`${id}-role`} label="Role" hint={self ? SELF_HINT : undefined}>
        <Select id={`${id}-role`} value={ROLE_VALUE[user.role]} disabled={self || saving}
          onChange={(e) => patch({ role: e.target.value }, 'Role updated')}>
          <option value="student">Student</option>
          <option value="advisor">Advisor</option>
          <option value="admin">Admin</option>
        </Select>
      </Field>

      {isStudent ? (
        <>
          <Field id={`${id}-advisor`} label="Assigned advisor">
            <Select id={`${id}-advisor`} value={user.advisorId ?? ''} disabled={saving} onChange={(e) => changeAdvisor(e.target.value)}>
              <option value="">No advisor</option>
              {advisors.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.advisees} {a.advisees === 1 ? 'advisee' : 'advisees'}</option>)}
            </Select>
          </Field>
          <Field id={`${id}-program`} label="Program">
            <Select id={`${id}-program`} value={user.programId ?? ''} disabled={saving}
              onChange={(e) => patch({ programId: Number(e.target.value) }, 'Program updated')}>
              {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
          </Field>
        </>
      ) : (
        <Fact label="Department" value={user.dept} />
      )}
      <Fact label="Last active" value={user.lastActive} />

      <div className="flex flex-col items-start gap-3 border-t border-canvas pt-4">
        {user.status !== 'Deactivated' && (
          <Button variant="secondary" size="sm" onClick={sendReset} aria-live="polite">
            {resetSent ? (invited ? 'Invite sent' : 'Reset link sent') : (invited ? 'Re-send invite' : 'Send password reset')}
          </Button>
        )}
        {self ? (
          <span className="text-[13px] text-muted">{SELF_HINT}</span>
        ) : user.status === 'Deactivated' ? (
          <Button variant="secondary" size="sm" disabled={saving}
            onClick={() => patch({ status: 'Active' }, 'Account reactivated')}>Reactivate account</Button>
        ) : !invited && (
          <ConfirmInline label="Deactivate account" confirmLabel="Deactivate" busyLabel="Deactivating…"
            warning={`${user.name} is signed out right away and can't sign in until the account is reactivated.`}
            onConfirm={() => patch({ status: 'Deactivated' }, 'Account deactivated')} />
        )}
      </div>
    </Card>
  )
}

function Fact({ label, value }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[13px] font-bold">{label}</span>
      <span className="text-sm text-slate">{value}</span>
    </div>
  )
}
