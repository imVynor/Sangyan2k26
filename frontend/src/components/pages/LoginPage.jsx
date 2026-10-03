import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export default function LoginPage() {
  const { login, loginWithGoogle } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const submit = (e) => {
    e.preventDefault() // stop the browser from reloading the page
    login(email, password)
    nav('/')
  }
  const google = () => {
    loginWithGoogle()
    nav('/')
  }

  return (
    <div className="auth">
      <form className="box" onSubmit={submit}>
        <div className="logo">₹</div>
        <h1>Financial Grievance Assistant</h1>
        <div className="mu" style={{ marginBottom: 16 }}>Sign in to resolve your financial issue, step by step.</div>
        <label className="mu">Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
        <label className="mu">Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        <button className="btn wide" type="submit">Log in</button>
        <div className="mu" style={{ textAlign: 'center', margin: '12px 0' }}>or</div>
        <button className="btn g wide" type="button" onClick={google}>Continue with Google</button>
      </form>
    </div>
  )
}