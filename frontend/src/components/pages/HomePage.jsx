
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useGrievance } from '../../context/GrievanceContext'
import { EXAMPLES } from '../data/flow'
import Composer from '../Composer'

export default function HomePage() {
  const { user } = useAuth()
  const { start, saving } = useGrievance()
  const nav = useNavigate()
  const [error, setError] = useState('')

  const submit = async (text) => {
    setError('')
    try {
      await start(text)
      nav('/chat')
      return true
    } catch (requestError) {
      setError(requestError.message)
      return false
    }
  }

  return (
    <main className="main">
      <div className="home">
        <h1>Welcome, {user.name}</h1>
        <Composer
          placeholder="How do you want to explain your problem? Tell me what happened…"
          onSend={submit}
          disabled={saving}
          maxLength={10000}
        />
        {error && <p role="alert" className="error">{error}</p>}
        <div className="chips">
          {EXAMPLES.map((example) => (
            <button key={example} className="chip" disabled={saving} onClick={() => submit(example)}>{example}</button>
          ))}
        </div>
      </div>
    </main>
  )
}