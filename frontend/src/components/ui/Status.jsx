import Card from './Card.jsx'
import Button from './Button.jsx'

export function Loading({ label = 'Loading…' }) {
  return (
    <div role="status" className="flex min-h-[200px] items-center justify-center text-sm font-semibold text-muted">
      {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <Card className="gap-3" role="alert">
      <h2 className="m-0 text-lg font-bold">Something went wrong</h2>
      <p className="m-0 max-w-[60ch] text-sm leading-relaxed text-muted">{message}</p>
      {onRetry && <div><Button onClick={onRetry}>Try again</Button></div>}
    </Card>
  )
}

export function Empty({ children }) {
  return <span className="py-3 text-sm text-muted">{children}</span>
}
