import { createContext, useContext, useEffect, useState } from 'react'

import { getAuthSession, logout } from '../services/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  const refreshSession = async () => {
    const next = await getAuthSession()
    setSession(next)
    return next
  }

  useEffect(() => {
    refreshSession().catch(() => setSession({ authenticated: false })).finally(() => setLoading(false))
  }, [])

  const signOut = async () => {
    await logout()
    setSession({ authenticated: false })
  }

  return <AuthContext.Provider value={{ session, loading, refreshSession, signOut }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider.')
  return context
}
