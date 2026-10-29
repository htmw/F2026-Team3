// Chips above the composer that send a canned reply at once (advisor messages, spec 25).
export default function QuickReplies({ replies, onPick, disabled = false }) {
  return (
    <div role="group" aria-label="Quick replies" className="flex flex-wrap gap-2">
      {replies.map((reply) => (
        <button key={reply} type="button" disabled={disabled} onClick={() => onPick(reply)}
          className="min-h-9 cursor-pointer rounded-full border border-line bg-surface px-3.5 text-[13px] font-semibold text-navy hover:bg-surface-sunk disabled:cursor-not-allowed disabled:opacity-50">
          {reply}
        </button>
      ))}
    </div>
  )
}
