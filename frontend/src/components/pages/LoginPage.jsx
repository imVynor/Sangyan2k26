import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export default function LoginPage() {
  const { login, register, loginWithGoogle, loading, connectionError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (mode === 'register') {
        await register({ name, username, email, password })
      } else {
        await login(identifier, password)
      }
      navigate(location.state?.from || '/', { replace: true })
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  const google = () => {
    setError('')
    loginWithGoogle()
  }

  return (
    <div className="auth">
      <form className="box" onSubmit={submit}>
        <div className="logo">₹</div>
        <h1>Financial Grievance Assistant</h1>
        <div className="mu" style={{ marginBottom: 16 }}>
          {mode === 'login' ? 'Sign in to work on your financial grievance.' : 'Create an account to save your reports.'}
        </div>

        {mode === 'register' && (
          <>
            <label className="mu" htmlFor="name">Full name</label>
            <input id="name" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
            <label className="mu" htmlFor="username">Username</label>
            <input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              minLength={2}
              pattern="[a-z0-9_]+"
              title="Use lowercase letters, numbers, and underscores."
            />
            <label className="mu" htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </>
        )}

        {mode === 'login' && (
          <>
            <label className="mu" htmlFor="identifier">Username or email</label>
            <input
              id="identifier"
              autoComplete="username"
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              required
            />
          </>
        )}

        <label className="mu" htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          minLength={8}
        />

        {(error || connectionError) && <p role="alert" className="error">{error || connectionError}</p>}
        <button className="btn wide" type="submit" disabled={submitting || loading}>
          {submitting ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>

        <div className="mu" style={{ textAlign: 'center', margin: '12px 0' }}>or</div>
        <button className="btn g wide" type="button" onClick={google} disabled={loading}>
          Continue with Google
        </button>
        <button
          className="text-button"
          type="button"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError('')
          }}
        >
          {mode === 'login' ? 'New here? Create an account' : 'Already have an account? Log in'}
        </button>
      </form>
    </div>
  )
}
