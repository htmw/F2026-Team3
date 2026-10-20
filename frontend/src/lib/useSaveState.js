import { useCallback, useEffect, useRef, useState } from 'react'

// `flash()` sets `on` to true for `ms`, then back. Used for "Saved" / "Exported" button labels.
export function useFlash(ms = 2000) {
  const [on, setOn] = useState(false)
  const timer = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])
  const flash = useCallback(() => {
    clearTimeout(timer.current)
    setOn(true)
    timer.current = setTimeout(() => setOn(false), ms)
  }, [ms])
  return [on, flash]
}

// Save button label states: 'Save changes' → 'Saving…' while `run(fn)` is pending → 'Saved' for 2 s.
// `run` rethrows when `fn` fails, so the caller can show errorText(err).
//   const { label, saving, run } = useSaveState()
//   <Button onClick={() => run(save).catch(showError)} disabled={saving || !dirty}>{label}</Button>
export function useSaveState({ idle = 'Save changes', busy = 'Saving…', done = 'Saved' } = {}) {
  const [saving, setSaving] = useState(false)
  const [saved, flash] = useFlash()
  const run = useCallback(async (fn) => {
    setSaving(true)
    try {
      const result = await fn()
      flash()
      return result
    } finally {
      setSaving(false)
    }
  }, [flash])
  return { label: saving ? busy : saved ? done : idle, saving, saved, run }
}
