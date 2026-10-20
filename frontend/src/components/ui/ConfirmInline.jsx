import { useEffect, useRef, useState } from 'react'
import Button from './Button.jsx'
import Notice from './Notice.jsx'

// Two-step destructive confirm (never window.confirm): the first click reveals the warning with
// [confirmLabel] and Cancel, the second runs `onConfirm`. It disarms afterwards unless `onConfirm`
// resolves to false (e.g. the request failed and the user should be able to retry). Buttons are
// disabled while `onConfirm` is pending or `busy` is set.
// `children` render between the warning and the buttons (e.g. a password field).
export default function ConfirmInline({
  label, warning = 'Are you sure?', confirmLabel, busyLabel, onConfirm, busy = false, disabled = false,
  triggerVariant = 'danger', size = 'sm', children,
}) {
  const [armed, setArmed] = useState(false)
  const [pending, setPending] = useState(false)
  const trigger = useRef(null)
  const cancel = useRef(null)
  const wasArmed = useRef(false)

  // Focus Cancel when the confirm opens and the trigger again when it closes.
  useEffect(() => {
    if (armed) cancel.current?.focus()
    else if (wasArmed.current) trigger.current?.focus()
    wasArmed.current = armed
  }, [armed])

  const working = busy || pending
  const confirm = async () => {
    setPending(true)
    try {
      if ((await onConfirm()) !== false) setArmed(false)
    } finally {
      setPending(false)
    }
  }

  if (!armed) return <Button ref={trigger} variant={triggerVariant} size={size} onClick={() => setArmed(true)}>{label}</Button>
  return (
    <div className="flex w-full flex-col gap-2.5">
      <Notice tone="pink">{warning}</Notice>
      {children}
      <div className="flex flex-wrap gap-2">
        <Button variant="danger" size={size} disabled={working || disabled} onClick={confirm}>
          {working && busyLabel ? busyLabel : confirmLabel}
        </Button>
        <Button ref={cancel} variant="secondary" size={size} onClick={() => setArmed(false)} disabled={working}>Cancel</Button>
      </div>
    </div>
  )
}
