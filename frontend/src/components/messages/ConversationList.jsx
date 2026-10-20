import Card from '../ui/Card.jsx'
import Avatar, { toneFor } from '../ui/Avatar.jsx'
import { ListRow } from '../layout/MasterDetail.jsx'

// Inbox list: avatar, name, role, last-message preview, time and unread count per conversation.
export default function ConversationList({ conversations, selectedId, onSelect }) {
  return (
    <Card as="nav" aria-label="Conversations" className="gap-1 p-3">
      {conversations.map((c) => {
        const unread = c.unread > 0
        return (
          <ListRow key={c.id} selected={c.id === selectedId} onSelect={() => onSelect(c.id)}>
            <Avatar initials={c.initials} tone={c.kind === 'system' ? 'teal' : toneFor(c.id)} />
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="flex items-baseline justify-between gap-2">
                <span className={`truncate text-sm ${unread ? 'font-extrabold' : 'font-semibold'}`}>{c.name}</span>
                <span className="shrink-0 text-[11px] text-muted">{c.time}</span>
              </span>
              <span className="truncate text-xs text-muted">{c.role}</span>
              <span className="flex items-center justify-between gap-2">
                <span className={`truncate text-[13px] ${unread ? 'text-navy' : 'text-muted'}`}>{c.preview || 'No messages yet'}</span>
                {unread && (
                  <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-accent px-1.5 text-[11px] font-bold text-surface">
                    {c.unread}<span className="sr-only"> unread</span>
                  </span>
                )}
              </span>
            </span>
          </ListRow>
        )
      })}
    </Card>
  )
}
