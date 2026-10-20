import { useId, useState } from 'react'
import Button from '../ui/Button.jsx'
import { Field, TextInput } from '../ui/Field.jsx'
import Notice from '../ui/Notice.jsx'
import { SwitchRow } from '../ui/Switch.jsx'
import { api, errorText } from '../../lib/api.js'

// SMTP settings (spec 35). Connecting sends a test email to the signed-in admin first; a failure shows the
// server's message and nothing is saved. `config` pre-fills the form (the password is never returned).
export default function SmtpForm({ config, onConnected, onCancel }) {
  const id = useId()
  const [form, setForm] = useState({
    host: config?.host ?? '', port: String(config?.port ?? 587), username: config?.username ?? '', password: '',
    from: config?.from ?? '', tls: config?.tls ?? true,
  })
  const [errors, setErrors] = useState({})
  const [failure, setFailure] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    const port = Number(form.port)
    const found = {}
    if (!form.host.trim()) found.host = 'Enter the SMTP server.'
    if (!Number.isInteger(port) || port < 1 || port > 65535) found.port = 'Port must be between 1 and 65535.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.from.trim())) found.from = 'Enter the address emails come from.'
    setErrors(found)
    setFailure(null)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const row = await api('/admin/integrations/mail/connect', {
        method: 'POST',
        body: { host: form.host.trim(), port, username: form.username.trim(), password: form.password, from: form.from.trim(), tls: form.tls },
      })
      onConnected(row)
    } catch (err) {
      if (err.status === 422 && err.details?.length) setErrors(Object.fromEntries(err.details.map((d) => [d.field, d.message])))
      else setFailure(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_110px]">
        <Field id={`${id}-host`} label="SMTP server" error={errors.host}>
          <TextInput id={`${id}-host`} value={form.host} onChange={set('host')} placeholder="smtp.school.edu" autoComplete="off" />
        </Field>
        <Field id={`${id}-port`} label="Port" error={errors.port}>
          <TextInput id={`${id}-port`} type="number" inputMode="numeric" min={1} max={65535} value={form.port} onChange={set('port')} />
        </Field>
      </div>
      <Field id={`${id}-user`} label="Username" error={errors.username}>
        <TextInput id={`${id}-user`} value={form.username} onChange={set('username')} autoComplete="off" />
      </Field>
      <Field id={`${id}-pass`} label="Password" error={errors.password}
        hint={config?.host ? 'Enter the password again to reconnect.' : undefined}>
        <TextInput id={`${id}-pass`} type="password" value={form.password} onChange={set('password')} autoComplete="new-password" />
      </Field>
      <Field id={`${id}-from`} label="From address" error={errors.from}>
        <TextInput id={`${id}-from`} type="email" value={form.from} onChange={set('from')} placeholder="acadmate@school.edu" />
      </Field>
      <SwitchRow id={`${id}-tls`} label="Use TLS (STARTTLS)" checked={form.tls} onChange={(tls) => setForm((f) => ({ ...f, tls }))} />
      {failure && <Notice tone="pink" role="status">{failure}</Notice>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>{busy ? 'Sending test email…' : 'Send test email'}</Button>
        {onCancel && <Button variant="secondary" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  )
}
