import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

// MOCK auth. Later replace the three functions with Firebase (see GUIDE.md, section 6).
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)

  const login = (email) => setUser({ name: email ? email.split('@')[0] : 'User', email })
  const loginWithGoogle = () => setUser({ name: 'User' })
  const logout = () => setUser(null)

  return (
    <AuthContext.Provider value={{ user, login, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
