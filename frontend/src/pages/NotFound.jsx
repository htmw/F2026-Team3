import Button from '../components/ui/Button.jsx'

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas p-5">
      <div className="flex max-w-md flex-col gap-4 rounded-3xl bg-surface p-10">
        <h1 className="m-0 font-display text-[28px] font-bold">Page not found</h1>
        <p className="m-0 text-sm leading-relaxed text-muted">That address doesn't match any Acadmate screen. Head back to sign in and pick your view.</p>
        <Button to="/login" size="lg">Go to sign in</Button>
      </div>
    </div>
  )
}
