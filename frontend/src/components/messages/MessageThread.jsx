import { useEffect, useRef, useState } from 'react'
import Card from '../ui/Card.jsx'
import Avatar, { toneFor } from '../ui/Avatar.jsx'
import Button from '../ui/Button.jsx'
import ChatBubble from '../ui/ChatBubble.jsx'
import Notice from '../ui/Notice.jsx'
import { Loading } from '../ui/Status.jsx'
import Composer from './Composer.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'

// One conversation: header, messages and reply box. Render with `key={conversation.id}` so its state resets per thread.
// Loading the messages marks the conversation read on the server; `onRead(id)` fires once they arrive.
// `onSent(id, message)` fires after a reply is saved. `headerAction`, `aboveComposer(send)` and `readOnlyAction`
// (shown next to the read-only note of system conversations) are role-specific slots.
export default function MessageThread({ conversation, onRead, onSent, headerAction, aboveComposer, readOnlyAction }) {
  const thread = useApi(`/conversations/${conversation.id}/messages`)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState(null)
  const logRef = useRef(null)
  const inputRef = useRef(null)
  const pendingCount = useRef(0)

  useEffect(() => {
    if (!thread.data) return
    setMessages(thread.data.messages)
    onRead?.(conversation.id)
    // onRead is a fresh closure each render; only a newly loaded thread should trigger it.
  }, [thread.data, conversation.id])

  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [messages])

  const canReply = thread.data?.canReply ?? conversation.canReply

  const send = async (raw) => {
    const text = raw.trim()
    if (!text || sending) return
    const pendingId = `pending-${++pendingCount.current}`
    setSending(true)
    setSendError(null)
    setDraft('')
    setMessages((current) => [...current, { id: pendingId, mine: true, text, time: 'Sending…', pending: true }])
    try {
      const saved = await api(`/conversations/${conversation.id}/messages`, { method: 'POST', body: { text } })
      setMessages((current) => current.map((m) => (m.id === pendingId ? saved : m)))
      onSent?.(conversation.id, saved)
    } catch (err) {
      setMessages((current) => current.filter((m) => m.id !== pendingId))
      setDraft(text)
      setSendError(errorText(err))
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  return (
    <Card as="section" aria-label={`Conversation with ${conversation.name}`} className="box-border min-h-[520px] gap-0 p-0">
      <div className="flex items-center gap-3 border-b border-canvas px-6 py-4">
        <Avatar initials={conversation.initials} tone={conversation.kind === 'system' ? 'teal' : toneFor(conversation.id)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <h2 className="m-0 truncate text-[15px] font-bold">{conversation.name}</h2>
          {conversation.role && <span className="truncate text-xs text-muted">{conversation.role}</span>}
        </div>
        {headerAction}
      </div>

      <div ref={logRef} aria-live="polite" className="flex max-h-[60vh] min-h-[280px] flex-1 flex-col gap-3.5 overflow-y-auto p-6">
        {thread.error && (
          <Notice tone="pink" role="alert">
            <div className="flex flex-wrap items-center gap-3">
              <span>{thread.error.message}</span>
              <Button variant="secondary" size="sm" onClick={thread.reload}>Try again</Button>
            </div>
          </Notice>
        )}
        {!thread.data && !thread.error && <Loading label="Loading messages…" />}
        {thread.data && messages.length === 0 && (
          <p className="m-auto max-w-[360px] text-center text-sm leading-relaxed text-muted">
            {canReply ? `No messages yet — say hello to ${conversation.name}.` : 'No notifications yet.'}
          </p>
        )}
        {messages.map((m) => (
          <ChatBubble key={m.id} mine={m.mine} name={m.showName ? m.from : undefined} time={m.time}>{m.text}</ChatBubble>
        ))}
      </div>

      <div className="flex flex-col gap-3 border-t border-canvas px-6 py-4">
        {canReply ? (
          <>
            {sendError && <Notice tone="pink" role="alert">{sendError}</Notice>}
            {aboveComposer?.(send)}
            <Composer value={draft} onChange={setDraft} onSend={send} sending={sending} inputRef={inputRef}
              placeholder={`Message ${conversation.name}…`} />
          </>
        ) : (
          <Notice tone="indigo">
            <div className="flex flex-wrap items-center gap-3">
              <span>Automated notifications can't be replied to.</span>
              {readOnlyAction}
            </div>
          </Notice>
        )}
      </div>
    </Card>
  )
}
