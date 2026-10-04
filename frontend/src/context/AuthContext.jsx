import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import {
  beginGoogleLogin,
  getCurrentUser,
  loginWithPassword,
  logout as logoutRequest,
  registerAndLogin,
} from '../services/api'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [connectionError, setConnectionError] = useState('')

  useEffect(() => {
    let active = true
    getCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch((error) => {
        if (active) {
          setUser(null)
          setConnectionError(error.message)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  const login = useCallback(async (identifier, password) => {
    const signedInUser = await loginWithPassword(identifier, password)
    setConnectionError('')
    setUser(signedInUser)
    return signedInUser
  }, [])

  const register = useCallback(async (details) => {
    const signedInUser = await registerAndLogin(details)
    setConnectionError('')
    setUser(signedInUser)
    return signedInUser
  }, [])

  const logout = useCallback(async () => {
    await logoutRequest()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, loading, connectionError, login, register, loginWithGoogle: beginGoogleLogin, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}
