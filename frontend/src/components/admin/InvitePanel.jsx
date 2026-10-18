import { useId, useState } from 'react'
import Button from '../ui/Button.jsx'
import Card, { CardHeader } from '../ui/Card.jsx'
import { Field, Textarea } from '../ui/Field.jsx'
import Notice from '../ui/Notice.jsx'
import SegmentedTabs from '../ui/Tabs.jsx'
import { api, errorText } from '../../lib/api.js'

const ROLES = [{ value: 'student', label: 'Student' }, { value: 'advisor', label: 'Advisor' }, { value: 'admin', label: 'Admin' }]

// "a@x.edu, b@x.edu\nc@x.edu" → unique addresses (case-insensitive), in the order typed.
export function parseEmails(text) {
  const seen = new Set()
  return text.split(/[\s,;]+/).map((e) => e.trim()).filter((e) => {
    const key = e.toLowerCase()
    if (!e || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

// Admin users: invite people by email (spec 31). `onDone()` reloads the list after invites go out.
export default function InvitePanel({ onDone, onCancel }) {
  const id = useId()
  const [text, setText] = useState('')
  const [role, setRole] = useState('student')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState(null)

  const send = async (event) => {
    event.preventDefault()
    const emails = parseEmails(text)
    if (emails.length === 0) {
      setResult({ tone: 'amber', text: 'Add at least one email address.' })
      return
    }
    setSending(true)
    setResult(null)
    try {
      const data = await api('/admin/users/invite', { method: 'POST', body: { emails, role } })
      const label = ROLES.find((r) => r.value === role).label.toLowerCase()
      setResult({
        tone: data.sent ? 'teal' : 'amber',
        text: data.sent ? `Sent ${plural(data.sent, `${label} invite`)}.` : 'No invites were sent.',
        skipped: data.skipped,
      })
      if (data.sent) {
        setText(data.skipped.map((s) => s.email).join(', '))
        onDone()
      }
    } catch (err) {
      setResult({ tone: 'pink', text: errorText(err) })
    } finally {
      setSending(false)
    }
  }

  return (
    <Card as="section" aria-label="Invite users" className="gap-4">
      <CardHeader title="Invite users" subtitle="Each person gets an email with a link to set up their account." />
      <form onSubmit={send} className="flex flex-col gap-4">
        <Field id={`${id}-emails`} label="Email addresses (comma separated)">
          <Textarea id={`${id}-emails`} rows={3} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="name@school.edu, name2@school.edu" />
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-bold">Invite as</span>
          <SegmentedTabs label="Invite as" options={ROLES} value={role} onChange={setRole} />
        </div>
        {result && (
          <Notice tone={result.tone} role="status">
            {result.text}
            {result.skipped?.length > 0 && (
              <ul className="m-0 mt-1.5 pl-4">
                {result.skipped.map((s) => <li key={s.email}><strong>{s.email}</strong>: {s.reason}</li>)}
              </ul>
            )}
          </Notice>
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={sending}>{sending ? 'Sending…' : 'Send invites'}</Button>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}
