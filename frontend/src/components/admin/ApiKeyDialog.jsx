import { useId, useState } from 'react'
import Button from '../ui/Button.jsx'
import Dialog from '../ui/Dialog.jsx'
import { Field, Select, TextInput } from '../ui/Field.jsx'
import Notice from '../ui/Notice.jsx'
import { api, errorText } from '../../lib/api.js'

// Generate an API key (spec 35): name + scope, then the full key once with Copy. `onCreated` reloads the list.
export default function ApiKeyDialog({ open, onClose, onCreated }) {
  const id = useId()
  const [name, setName] = useState('')
  const [scope, setScope] = useState('reports:read')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState(null)
  const [copied, setCopied] = useState(false)

  const close = () => {
    setName('')
    setError(null)
    setCreated(null)
    setCopied(false)
    onClose()
  }

  const generate = async (event) => {
    event.preventDefault()
    if (!name.trim()) return setError('Give the key a name.')
    setBusy(true)
    setError(null)
    try {
      setCreated(await api('/admin/api-keys', { method: 'POST', body: { name: name.trim(), scope } }))
      onCreated()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(created.key)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Dialog open={open} onClose={close} title={created ? 'Your new API key' : 'Generate an API key'}>
      {created ? (
        <div className="flex flex-col gap-3">
          <code className="block break-all rounded-xl bg-surface-sunk px-3.5 py-3 font-mono text-sm">{created.key}</code>
          <Notice tone="amber">Copy this key now. You won&apos;t see it again.</Notice>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
            <Button onClick={close}>Done</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={generate} noValidate className="flex flex-col gap-3">
          <Field id={`${id}-name`} label="Name" error={error}>
            <TextInput id={`${id}-name`} value={name} onChange={(e) => setName(e.target.value)} maxLength={60}
              placeholder="e.g. Reporting export" autoComplete="off" />
          </Field>
          <Field id={`${id}-scope`} label="Scope">
            <Select id={`${id}-scope`} value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="reports:read">Read reports</option>
            </Select>
          </Field>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={close}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? 'Generating…' : 'Generate key'}</Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
