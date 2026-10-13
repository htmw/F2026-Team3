// One chat message. `mine` puts it on the right in the dark style; `name` (group chats) is shown above, `time` underneath.
export default function ChatBubble({ mine = false, name, time, children }) {
  return (
    <div className={`flex max-w-[75%] flex-col gap-1 ${mine ? 'items-end self-end' : 'items-start self-start'}`}>
      {name && <span className="px-1 text-xs font-semibold text-muted">{name}</span>}
      <div className={`whitespace-pre-wrap break-words px-4 py-3 text-sm leading-[1.55] ${
        mine ? 'rounded-[16px_16px_4px_16px] bg-ink text-surface' : 'rounded-[16px_16px_16px_4px] bg-surface-sunk text-navy'}`}>
        {children}
      </div>
      {time && <span className="px-1 text-[11px] text-muted">{time}</span>}
    </div>
  )
}
