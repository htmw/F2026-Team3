import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api.js'
import { applyAccent } from '../lib/theme.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [badges, setBadges] = useState({})
  const [config, setConfig] = useState({})

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
  // Public settings (Google sign-in, branding accent). Without them the app keeps its defaults.
  useEffect(() => {
    api('/auth/config').then((cfg) => { setConfig(cfg); applyAccent(cfg.accent) }).catch(() => {})
  }, [])
  useEffect(() => { if (user) refreshBadges() }, [user, refreshBadges])

  const logout = useCallback(async () => {
    // A failed request (offline, already-expired session) still signs the user out locally.
    try { await api('/auth/logout', { method: 'POST' }) } catch { /* ignore */ } finally {
      setUser(null)
      setBadges({})
    }
  }, [])

  const value = useMemo(() => ({ user, setUser, loading, refresh, logout, badges, refreshBadges, config }),
    [user, loading, refresh, logout, badges, refreshBadges, config])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
