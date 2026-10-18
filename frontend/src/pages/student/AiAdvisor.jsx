import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import AiMessage, { SparkleTile } from '../../components/ai/AiMessage.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import ChatBubble from '../../components/ui/ChatBubble.jsx'
import Dialog from '../../components/ui/Dialog.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api } from '../../lib/api.js'
import { clockTime, relativeDate, shortDay } from '../../lib/dates.js'
import { useApi } from '../../lib/useApi.js'

const PENDING_ID = 'pending'

function ThreadList({ threads, activeId, onSelect, onDelete }) {
  return (
    <Card as="nav" aria-label="Conversations" className="box-border min-w-0 flex-[1_1_220px] gap-1 self-start p-[18px]">
      <h2 className="m-0 mb-2 text-base font-bold">Conversations</h2>
      {threads.length === 0 && <Empty>No conversations yet.</Empty>}
      {threads.map((thread) => {
        const active = thread.id === activeId
        return (
          <div key={thread.id} className={`group flex items-center gap-1 rounded-xl ${active ? 'bg-teal-soft' : 'hover:bg-surface-sunk'}`}>
            <button type="button" onClick={() => onSelect(thread.id)} aria-current={active ? 'true' : undefined}
              className="flex min-w-0 flex-1 cursor-pointer flex-col gap-0.5 border-0 bg-transparent px-3 py-2.5 text-left text-navy">
              <span className="truncate text-sm font-semibold">{thread.title}</span>
              <span className="text-xs text-muted">{relativeDate(thread.updatedAt)}</span>
            </button>
            <button type="button" aria-label={`Delete conversation "${thread.title}"`} onClick={() => onDelete(thread)}
              className="hit-44 mr-1 flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-muted hover:bg-surface">
              <Icon name="x" size={15} />
            </button>
          </div>
        )
      })}
    </Card>
  )
}

function ContextPanel({ context }) {
  const rows = [
    ['Program', context.program],
    ['Progress', context.progress],
    ['Goal', context.goal],
    ['Preferences', context.preferences.join(' · ') || 'None set'],
    ['Data sources', context.sources.join(', ') || 'None — all turned off'],
    ['Answers', context.engine === 'Claude' ? 'Claude (AI), checked against your records' : 'Rule-based, from your records'],
  ]
  return (
    <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-4 self-start">
      <Card className="gap-3 p-5">
        <h2 className="m-0 text-base font-bold">What Acadmate is using</h2>
        <dl className="m-0 flex flex-col gap-2.5">
          {rows.map(([label, value]) => (
            <div key={label} className="flex flex-col gap-0.5">
              <dt className="text-xs font-semibold text-muted">{label}</dt>
              <dd className="m-0 text-sm">{value}</dd>
            </div>
          ))}
        </dl>
        <Link to="/student/settings" className="text-[13px] font-semibold">Change what Acadmate can use</Link>
      </Card>
      <Card dark className="gap-3 p-5">
        <h2 className="m-0 text-base font-bold text-white">Need a human advisor?</h2>
        <p className="m-0 text-sm leading-relaxed text-fog">
          {context.advisor ? `${context.advisor.name} can review your plan and sign off on it.` : 'Your advisor can review your plan and sign off on it.'}
        </p>
        {context.nextMeeting && (
          <span className="text-[13px] text-fog">
            Next meeting · <strong className="text-white">{shortDay(context.nextMeeting.date, { weekday: true })} · {context.nextMeeting.time}</strong>
          </span>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button to="/student/book-meeting" variant="sun" size="sm">Book a meeting</Button>
          <Link to="/student/messages" className="text-[13px] font-semibold text-teal-bright">Message advisor</Link>
        </div>
      </Card>
    </div>
  )
}

function Composer({ context, draft, setDraft, pending, onSend, inputRef }) {
  if (!context.enabled) {
    return (
      <Notice tone="amber">
        The AI advisor is currently turned off for your school. Book a meeting with your advisor instead.{' '}
        <Link to="/student/book-meeting" className="font-bold">Book a meeting</Link>
      </Notice>
    )
  }
  const submit = (event) => { event.preventDefault(); onSend(draft) }
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap gap-2">
        {context.prompts.map((prompt) => (
          <button key={prompt} type="button" onClick={() => { setDraft(prompt); inputRef.current?.focus() }}
            className="min-h-10 cursor-pointer rounded-full border border-line bg-surface px-3.5 text-[13px] font-semibold text-navy hover:bg-surface-sunk">
            {prompt}
          </button>
        ))}
      </div>
      <form className="flex items-end gap-2.5" onSubmit={submit}>
        <label htmlFor="ai-question" className="sr-only">Ask the AI advisor a question</label>
        <textarea id="ai-question" ref={inputRef} rows={1} maxLength={1000} value={draft} disabled={pending}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) submit(event) }}
          placeholder="Ask about courses, prerequisites, or your graduation date…"
          className="box-border max-h-40 min-h-12 min-w-0 flex-1 resize-y rounded-xl border border-line bg-surface-sunk px-4 py-3 text-sm leading-normal text-navy disabled:opacity-60" />
        <button type="submit" aria-label="Send question" disabled={pending || !draft.trim()}
          className="flex size-12 shrink-0 cursor-pointer items-center justify-center rounded-xl border-0 bg-ink disabled:cursor-not-allowed disabled:opacity-50">
          <Icon name="send" color="var(--color-surface)" strokeWidth={2.2} />
        </button>
      </form>
      <span className="text-xs text-muted">
        Acadmate can make mistakes. Plans stay suggestions until your advisor approves them. · {context.remainingToday} of {context.dailyLimit} questions left today
      </span>
    </div>
  )
}

export default function StudentAiAdvisor() {
  const { user } = useAuth()
  const toast = useToast()
  const location = useLocation()
  const context = useApi('/students/me/ai/context')
  const threads = useApi('/students/me/ai/threads')
  const [activeId, setActiveId] = useState(null)
  const thread = useApi(activeId ? `/students/me/ai/threads/${activeId}` : null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState(() => location.state?.question ?? '')
  const [pending, setPending] = useState(false)
  const [sendError, setSendError] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const logRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { if (thread.data) setMessages(thread.data.messages) }, [thread.data])
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [messages, pending])

  const error = context.error ?? threads.error
  if (error) {
    return (
      <>
        <PageHeader title="AI advisor" />
        <ErrorState message={error.message} onRetry={() => { context.reload(); threads.reload() }} />
      </>
    )
  }
  if (!context.data || !threads.data) return <Loading label="Loading the AI advisor…" />

  const startNew = () => {
    setActiveId(null)
    setMessages([])
    setSendError(null)
    inputRef.current?.focus()
  }

  const send = async (raw) => {
    const text = raw.trim()
    if (!text || pending) return
    setPending(true)
    setSendError(null)
    setDraft('')
    setMessages((current) => [...current, { id: PENDING_ID, role: 'user', text, createdAt: new Date().toISOString() }])
    try {
      if (activeId) {
        const result = await api(`/students/me/ai/threads/${activeId}/messages`, { method: 'POST', body: { text } })
        setMessages((current) => [...current.filter((m) => m.id !== PENDING_ID), result.userMessage, result.reply])
      } else {
        const result = await api('/students/me/ai/threads', { method: 'POST', body: { text } })
        setMessages(result.messages)
        setActiveId(result.thread.id)
      }
      threads.reload()
    } catch (err) {
      setMessages((current) => current.filter((m) => m.id !== PENDING_ID))
      setDraft(text)
      setSendError(err.message)
    } finally {
      setPending(false)
      context.reload()
    }
  }

  const rate = async (message, helpful) => {
    const rating = helpful == null ? null : helpful ? 1 : -1
    setMessages((current) => current.map((m) => (m.id === message.id ? { ...m, rating } : m)))
    try {
      await api(`/students/me/ai/messages/${message.id}/rating`, { method: 'POST', body: { helpful } })
    } catch (err) {
      toast.show({ message: err.message })
    }
  }

  const report = async (message, issue) => {
    await api(`/students/me/ai/messages/${message.id}/flag`, { method: 'POST', body: { issue } })
    toast.show({ message: 'Thanks — an administrator will review this answer.' })
  }

  const confirmDelete = async () => {
    const target = deleting
    setDeleting(null)
    try {
      await api(`/students/me/ai/threads/${target.id}`, { method: 'DELETE' })
      if (target.id === activeId) startNew()
      threads.reload()
      toast.show({ message: 'Conversation deleted' })
    } catch (err) {
      toast.show({ message: err.message })
    }
  }

  const active = threads.data.threads.find((t) => t.id === activeId)

  return (
    <>
      <PageHeader title="AI advisor" subtitle="Answers use your degree audit and the course catalog. Your advisor approves final plans."
        initials={user?.initials} actions={<Button onClick={startNew}><Icon name="plus" size={18} />New conversation</Button>} />

      <div className="flex flex-wrap items-start gap-5">
        <ThreadList threads={threads.data.threads} activeId={activeId} onSelect={(id) => { if (id !== activeId) { setMessages([]); setActiveId(id) } setSendError(null) }} onDelete={setDeleting} />

        <Card as="section" aria-label="Conversation" className="box-border min-h-[560px] min-w-0 flex-[3_1_460px] gap-0 p-0">
          <div className="flex items-center gap-3 border-b border-canvas px-6 py-4">
            <SparkleTile />
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-[15px] font-bold">{active?.title ?? 'New conversation'}</span>
              <span className="text-xs text-muted">{active ? `Updated ${relativeDate(active.updatedAt).toLowerCase()}` : 'Ask anything about your degree, plan or schedule'}</span>
            </div>
          </div>

          <div ref={logRef} aria-live="polite" className="flex max-h-[60vh] min-h-[280px] flex-1 flex-col gap-[18px] overflow-y-auto p-6">
            {thread.loading && messages.length === 0 && <Loading label="Loading conversation…" />}
            {thread.error && <Notice tone="pink">{thread.error.message}</Notice>}
            {!activeId && messages.length === 0 && (
              <div className="m-auto flex max-w-[420px] flex-col items-center gap-3 text-center">
                <SparkleTile size="size-11" />
                <p className="m-0 text-sm leading-relaxed text-muted">
                  Ask about your progress, next semester's plan, electives, prerequisites or your schedule. Pick a starter question below or type your own.
                </p>
              </div>
            )}
            {messages.map((message) => (message.role === 'user'
              ? <ChatBubble key={message.id} mine time={message.id === PENDING_ID ? 'Sending…' : clockTime(message.createdAt)}>{message.text}</ChatBubble>
              : <AiMessage key={message.id} message={message} time={clockTime(message.createdAt)}
                  onRate={(helpful) => rate(message, helpful)} onReport={(issue) => report(message, issue)} />))}
            {pending && (
              <div className="flex items-center gap-3" role="status">
                <SparkleTile />
                <span className="rounded-[16px_16px_16px_4px] bg-surface-sunk px-4 py-3 text-sm text-muted">Thinking…</span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 border-t border-canvas px-6 py-4">
            {sendError && <Notice tone="pink">{sendError}</Notice>}
            <Composer context={context.data} draft={draft} setDraft={setDraft} pending={pending} onSend={send} inputRef={inputRef} />
          </div>
        </Card>

        <ContextPanel context={context.data} />
      </div>

      <Dialog open={Boolean(deleting)} onClose={() => setDeleting(null)} title="Delete this conversation?"
        actions={<>
          <Button variant="secondary" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button variant="danger" onClick={confirmDelete}>Delete</Button>
        </>}>
        <p className="m-0 text-sm text-muted">“{deleting?.title}” will be removed for good.</p>
      </Dialog>
    </>
  )
}
