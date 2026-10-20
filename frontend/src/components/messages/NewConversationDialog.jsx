import { useState } from 'react'
import Avatar from '../ui/Avatar.jsx'
import Button from '../ui/Button.jsx'
import Dialog from '../ui/Dialog.jsx'
import Notice from '../ui/Notice.jsx'
import SearchInput from '../ui/SearchInput.jsx'
import { Empty } from '../ui/Status.jsx'
import { Field, Textarea } from '../ui/Field.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useDebounced } from '../../lib/useDebounced.js'

// Pick one contact (the server decides who's allowed) and optionally send a first message.
// Starting a chat with someone you already have a thread with returns that thread; `onCreated(id)` gets its id.
export default function NewConversationDialog({ open, onClose, onCreated }) {
  const [search, setSearch] = useState('')
  const [picked, setPicked] = useState(null)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const q = useDebounced(search.trim())
  const contacts = useApi(open ? `/conversations/contacts${q ? `?q=${encodeURIComponent(q)}` : ''}` : null)

  const reset = () => { setSearch(''); setPicked(null); setText(''); setError(null) }
  const close = () => { if (!saving) { reset(); onClose() } }

  const submit = async (event) => {
    event.preventDefault()
    if (!picked) return
    setSaving(true)
    setError(null)
    try {
      const { id } = await api('/conversations', { method: 'POST', body: { recipientIds: [picked.id], text: text.trim() || undefined } })
      reset()
      onCreated(id)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setSaving(false)
    }
  }

  const list = contacts.data?.contacts ?? []
  return (
    <Dialog open={open} onClose={close} title="New message">
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <SearchInput label="Search people" placeholder="Search advisors and staff" value={search} onChange={setSearch} className="w-full" />
        <div role="group" aria-label="Contacts" className="flex max-h-[260px] flex-col gap-1 overflow-y-auto">
          {contacts.error && <Notice tone="pink">{contacts.error.message}</Notice>}
          {!contacts.data && !contacts.error && <span role="status" className="py-3 text-sm text-muted">Loading contacts…</span>}
          {contacts.data && list.length === 0 && <Empty>{q ? `No one matches “${q}”.` : 'No contacts available.'}</Empty>}
          {list.map((contact) => {
            const selected = picked?.id === contact.id
            return (
              <button key={contact.id} type="button" aria-pressed={selected} onClick={() => setPicked(contact)}
                className={`flex w-full cursor-pointer items-center gap-3 rounded-xl border-0 px-3 py-2.5 text-left text-navy ${
                  selected ? 'bg-surface-sunk shadow-[inset_4px_0_0_var(--color-accent)]' : 'bg-transparent hover:bg-surface-sunk'}`}>
                <Avatar name={contact.name} initials={contact.initials} size="sm" />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-sm font-semibold">{contact.name}</span>
                  <span className="truncate text-xs capitalize text-muted">{contact.title ?? contact.role}</span>
                </span>
              </button>
            )
          })}
        </div>
        <Field id="new-message-text" label="First message" aside={<span className="text-xs text-muted">Optional</span>}>
          <Textarea id="new-message-text" rows={3} maxLength={4000} value={text} onChange={(event) => setText(event.target.value)}
            placeholder={picked ? `Message ${picked.name}…` : 'Pick someone above first'} />
        </Field>
        {error && <Notice tone="pink" role="alert">{error}</Notice>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={close} disabled={saving}>Cancel</Button>
          <Button type="submit" disabled={saving || !picked}>{saving ? 'Starting…' : text.trim() ? 'Send' : 'Open conversation'}</Button>
        </div>
      </form>
    </Dialog>
  )
}
