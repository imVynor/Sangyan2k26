
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useGrievance } from '../../context/GrievanceContext'
import { EXAMPLES } from '../data/flow'
import Composer from '../Composer'

export default function HomePage() {
  const { user } = useAuth()
  const { start } = useGrievance()
  const nav = useNavigate()

  const submit = (text) => {
    start(text) // save the problem + begin the flow
    nav('/chat') // go to the chat page
  }

  return (
    <main className="main">
      <div className="home">
        <h1>Welcome, {user.name}</h1>
        <Composer placeholder="How do you want to explain your problem? Tell me what happened…" onSend={submit} />
        <div className="chips">
          {EXAMPLES.map((t) => (
            <button key={t} className="chip" onClick={() => submit(t)}>{t}</button>
          ))}
        </div>
      </div>
    </main>
  )
}