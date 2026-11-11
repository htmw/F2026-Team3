import { useId, useState } from 'react'
import Button from '../ui/Button.jsx'
import Card, { CardHeader } from '../ui/Card.jsx'
import { Field, Select, TextInput } from '../ui/Field.jsx'
import Notice from '../ui/Notice.jsx'
import SegmentedTabs from '../ui/Tabs.jsx'
import TempPasswordNotice from './TempPasswordNotice.jsx'
import { api, errorText } from '../../lib/api.js'

const ROLES = [{ value: 'student', label: 'Student' }, { value: 'advisor', label: 'Advisor' }, { value: 'admin', label: 'Admin' }]
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const EMPTY = { name: '', email: '', role: 'student', programId: '', advisorId: '' }

// Admin users: Add user (spec 31 revision 2). The account is Active right away; the temporary password is emailed
// and shown here once. `onCreated(row)` reloads the list and selects the new user.
export default function CreateUserPanel({ programs = [], advisors = [], onCreated, onCancel }) {
  const id = useId()
  const [form, setForm] = useState({ ...EMPTY, programId: programs[0]?.id ?? '' })
  const [busy, setBusy] = useState(false)
  const [hint, setHint] = useState('')
  const [created, setCreated] = useState(null)

  const set = (key) => (value) => {
    setForm((current) => ({ ...current, [key]: value }))
    setHint('')
  }
  const student = form.role === 'student'
  const valid = form.name.trim() && EMAIL_RE.test(form.email.trim())

  const submit = async (event) => {
    event.preventDefault()
    if (!form.name.trim()) return setHint('Enter a name.')
    if (!EMAIL_RE.test(form.email.trim())) return setHint('Enter a valid email address.')
    setBusy(true)
    setHint('')
    try {
      const body = { name: form.name.trim(), email: form.email.trim(), role: form.role }
      if (student) {
        body.programId = form.programId ? Number(form.programId) : null
        body.advisorId = form.advisorId ? Number(form.advisorId) : null
      }
      const data = await api('/admin/users', { method: 'POST', body })
      setCreated(data)
      onCreated(data.user)
    } catch (err) {
      setHint(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const another = () => {
    setCreated(null)
    setForm({ ...EMPTY, programId: programs[0]?.id ?? '' })
  }

  if (created) {
    const { user, temporaryPassword } = created
    return (
      <Card as="section" aria-label="Add user" className="gap-4">
        <CardHeader title="Add user" />
        <Notice tone="teal" role="status">Created {user.name}. Login details were emailed to {user.email}.</Notice>
        <TempPasswordNotice password={temporaryPassword} firstName={user.name.split(' ')[0]} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={another}>Add another</Button>
          <Button variant="secondary" onClick={onCancel}>Done</Button>
        </div>
      </Card>
    )
  }

  return (
    <Card as="section" aria-label="Add user" className="gap-4">
      <CardHeader title="Add user"
        subtitle="The account is ready right away. Acadmate emails the sign-in details with a temporary password." />
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id={`${id}-name`} label="Full name">
            <TextInput id={`${id}-name`} value={form.name} maxLength={100} autoComplete="off" placeholder="First Last"
              onChange={(e) => set('name')(e.target.value)} />
          </Field>
          <Field id={`${id}-email`} label="Email">
            <TextInput id={`${id}-email`} type="email" value={form.email} maxLength={254} autoComplete="off"
              placeholder="name@school.edu" onChange={(e) => set('email')(e.target.value)} />
          </Field>
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-bold">Role</span>
          <SegmentedTabs label="Role" options={ROLES} value={form.role} onChange={set('role')} />
        </div>
        {student && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id={`${id}-program`} label="Program">
              <Select id={`${id}-program`} value={form.programId} onChange={(e) => set('programId')(e.target.value)}>
                {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </Select>
            </Field>
            <Field id={`${id}-advisor`} label="Assigned advisor">
              <Select id={`${id}-advisor`} value={form.advisorId} onChange={(e) => set('advisorId')(e.target.value)}>
                <option value="">No advisor yet</option>
                {advisors.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} · {a.advisees} {a.advisees === 1 ? 'advisee' : 'advisees'}</option>
                ))}
              </Select>
            </Field>
          </div>
        )}
        <span role="status" className="min-h-[18px] text-[13px] font-semibold text-warn">{hint}</span>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy || !valid}>{busy ? 'Creating…' : 'Create user'}</Button>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}
