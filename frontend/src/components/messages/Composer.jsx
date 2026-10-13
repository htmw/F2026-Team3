import Icon from '../ui/Icon.jsx'

// Message box + send button. Enter sends, Shift+Enter adds a new line.
export default function Composer({ value, onChange, onSend, sending = false, placeholder = 'Write a message…', inputRef }) {
  const submit = (event) => {
    event.preventDefault()
    if (!sending && value.trim()) onSend(value)
  }
  return (
    <form className="flex items-end gap-2.5" onSubmit={submit}>
      <label htmlFor="message-text" className="sr-only">Message</label>
      <textarea id="message-text" ref={inputRef} rows={1} maxLength={4000} value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) submit(event) }}
        placeholder={placeholder}
        className="box-border max-h-40 min-h-12 min-w-0 flex-1 resize-y rounded-xl border border-line bg-surface-sunk px-4 py-3 text-sm leading-normal text-navy" />
      <button type="submit" aria-label="Send message" disabled={sending || !value.trim()}
        className="flex size-12 shrink-0 cursor-pointer items-center justify-center rounded-xl border-0 bg-ink disabled:cursor-not-allowed disabled:opacity-50">
        <Icon name="send" color="var(--color-surface)" strokeWidth={2.2} />
      </button>
    </form>
  )
}
