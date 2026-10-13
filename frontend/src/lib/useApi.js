import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

// Loads `path` on mount and whenever it changes, aborting the previous request.
// Pass `null` to skip loading (e.g. a detail pane with nothing selected).
// `reload()` refetches; `setData` allows optimistic updates after a mutation.
export function useApi(path) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(path != null)
  const controllerRef = useRef(null)

  const load = useCallback(() => {
    controllerRef.current?.abort()
    if (path == null) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }
    const controller = new AbortController()
    controllerRef.current = controller
    setError(null)
    setLoading(true)
    api(path, { signal: controller.signal })
      .then((result) => { setData(result); setLoading(false) })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setError(err)
        setLoading(false)
      })
  }, [path])

  useEffect(() => {
    load()
    return () => controllerRef.current?.abort()
  }, [load])

  return { data, error, loading, reload: load, setData }
}
