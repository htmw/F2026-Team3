import { useEffect, useState } from 'react'
import PageHeader from '../layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty } from '../layout/MasterDetail.jsx'
import ConversationList from './ConversationList.jsx'
import MessageThread from './MessageThread.jsx'
import NewConversationDialog from './NewConversationDialog.jsx'
import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import { Empty, ErrorState, Loading } from '../ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { useApi } from '../../lib/useApi.js'
import { useDebounced } from '../../lib/useDebounced.js'

const unreadLabel = (unread) => (unread ? `${unread} unread` : 'All caught up')

// The Messages screen shared by students (spec 16) and advisors (spec 25): search, conversation list, thread,
// mark-read, reply previews and the New message dialog. Role-specific parts come in as props:
// `actions({ openNew })` header buttons, `headerActionFor(conversation)`, `readOnlyActionFor(conversation)`,
// `aboveComposerFor(conversation, send)` and `subtitle(unread)`. `select` ({ id }) selects a conversation the page
// opened itself (e.g. `?to=` or the advising team) and reloads the list; pass a new object to select again.
export default function MessagesPage({
  subtitle = unreadLabel, actions, headerActionFor, readOnlyActionFor, aboveComposerFor, select,
  searchLabel = 'Search messages', searchPlaceholder = 'Search messages',
}) {
  const { user, refreshBadges } = useAuth()
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [newOpen, setNewOpen] = useState(false)
  const q = useDebounced(search.trim())
  const list = useApi(q ? `/conversations?q=${encodeURIComponent(q)}` : '/conversations')
  const { reload } = list

  useEffect(() => {
    if (select?.id == null) return
    setSearch('')
    setSelectedId(select.id)
    reload()
  }, [select, reload])

  const openNew = () => setNewOpen(true)
  const dialog = (
    <NewConversationDialog open={newOpen} onClose={() => setNewOpen(false)}
      onCreated={(id) => { setNewOpen(false); setSearch(''); setSelectedId(id); list.reload() }} />
  )

  if (list.error && !list.data) {
    return (
      <>
        <PageHeader title="Messages" />
        <ErrorState message={list.error.message} onRetry={list.reload} />
      </>
    )
  }
  if (!list.data) return <Loading label="Loading your messages…" />

  const conversations = list.data.conversations
  // While the list reloads (e.g. right after starting a conversation) don't fall back to — and mark read — another thread.
  const selected = conversations.find((c) => c.id === selectedId) ?? (list.loading ? null : conversations[0])
  const unread = conversations.reduce((sum, c) => sum + c.unread, 0)

  const updateRow = (id, change) => list.setData((current) => current && {
    ...current, conversations: current.conversations.map((c) => (c.id === id ? change(c) : c)),
  })

  const markRead = (id) => {
    if (!conversations.find((c) => c.id === id)?.unread) return
    updateRow(id, (c) => ({ ...c, unread: 0 }))
    refreshBadges()
  }

  // Show the reply as the row's preview and move the conversation to the top, without refetching the list.
  const replied = (id, message) => list.setData((current) => {
    if (!current) return current
    const row = current.conversations.find((c) => c.id === id)
    if (!row) return current
    const updated = { ...row, preview: `You: ${message.text}`, time: message.time, lastAt: message.sentAt }
    return { ...current, conversations: [updated, ...current.conversations.filter((c) => c.id !== id)] }
  })

  const header = (
    <PageHeader title="Messages" initials={user?.initials} actions={actions?.({ openNew })}
      subtitle={subtitle(unread)}
      search={{ label: searchLabel, placeholder: searchPlaceholder, value: search, onChange: setSearch }} />
  )

  if (conversations.length === 0 && !q) {
    return (
      <>
        {header}
        <Card className="items-start gap-3">
          <Empty>No messages yet.</Empty>
          <Button variant="secondary" size="sm" onClick={openNew}>Start a conversation</Button>
        </Card>
        {dialog}
      </>
    )
  }

  return (
    <>
      {header}
      <MasterDetail
        list={conversations.length === 0 ? (
          <Card className="items-start gap-2">
            <Empty>No conversations match “{q}”.</Empty>
            <Button variant="secondary" size="sm" onClick={() => setSearch('')}>Clear search</Button>
          </Card>
        ) : (
          <ConversationList conversations={conversations} selectedId={selected?.id} onSelect={setSelectedId} />
        )}
        detail={selected
          ? <MessageThread key={selected.id} conversation={selected} onRead={markRead} onSent={replied}
              headerAction={headerActionFor?.(selected)}
              aboveComposer={aboveComposerFor ? (send) => aboveComposerFor(selected, send) : undefined}
              readOnlyAction={readOnlyActionFor?.(selected)} />
          : <Card><DetailEmpty>Select a conversation to read it.</DetailEmpty></Card>} />
      {dialog}
    </>
  )
}
