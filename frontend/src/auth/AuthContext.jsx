import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [badges, setBadges] = useState({})

  const refresh = useCallback(async () => {
    try {
      const data = await api('/auth/me')
      setUser(data.user)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshBadges = useCallback(async () => {
    try {
      setBadges((await api('/users/me/badges')).badges)
    } catch {
      setBadges({})
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => { if (user) refreshBadges() }, [user, refreshBadges])

  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }) } finally { setUser(null) }
  }, [])

  const value = useMemo(() => ({ user, setUser, loading, refresh, logout, badges, refreshBadges }), [user, loading, refresh, logout, badges, refreshBadges])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
