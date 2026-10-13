import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

const ToastContext = createContext(null)

// One toast at a time, e.g. show({ message: 'Approved', actionLabel: 'Undo', onAction: reopen }).
export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null)
  const timer = useRef(null)

  const dismiss = useCallback(() => {
    clearTimeout(timer.current)
    setToast(null)
  }, [])

  const show = useCallback(({ message, actionLabel, onAction, duration = 6000 }) => {
    clearTimeout(timer.current)
    setToast({ id: Date.now(), message, actionLabel, onAction })
    timer.current = setTimeout(() => setToast(null), duration)
  }, [])

  useEffect(() => () => clearTimeout(timer.current), [])

  const value = useMemo(() => ({ show, dismiss }), [show, dismiss])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-5 right-5 left-5 z-50 flex justify-end">
        {toast && (
          <div key={toast.id} className="pointer-events-auto flex max-w-[420px] items-center gap-4 rounded-xl bg-navy px-4 py-3 text-sm text-frost shadow-lg">
            <span>{toast.message}</span>
            {toast.actionLabel && (
              <button type="button" onClick={() => { dismiss(); toast.onAction?.() }}
                className="ml-auto min-h-9 cursor-pointer rounded-lg border-0 bg-transparent px-2 text-sm font-bold text-sun hover:bg-navy-raised">
                {toast.actionLabel}
              </button>
            )}
          </div>
        )}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
