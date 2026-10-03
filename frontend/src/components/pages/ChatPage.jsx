import { useEffect, useRef } from 'react'
import { Navigate } from 'react-router-dom'
import { useGrievance } from '../../context/GrievanceContext'
import { STAGES } from '../data/flow'
import Composer from '../Composer'
import ReportPanel from '../ReportPanel'

export default function ChatPage() {
  const g = useGrievance()
  const bottom = useRef(null)

  // scroll to the newest message whenever messages change
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [g.messages])

  if (!g.started) return <Navigate to="/" replace /> // nothing to show without a query

  return (
    <>
      <main className="main">
        <div className="vc">
          <div className="ph">
            <span>
              <b>{g.title.length > 34 ? g.title.slice(0, 34) + '…' : g.title}</b>
              <span className="mu"> · {STAGES[g.stage]}</span>
            </span>
            <button className="btn g mob" onClick={() => g.setReportOpen(true)}>📄 Report</button>
          </div>

          <div className="chat">
            {g.messages.map((m, i) => (
              <div key={i} className={`m ${m.from === 'user' ? 'u' : ''}`}>{m.text}</div>
            ))}
            <div ref={bottom} />
          </div>

          <div className="opts">
            {g.options.map((o) => (
              <button key={o} className="opt" onClick={() => g.pick(o)}>{o}</button>
            ))}
          </div>
          <div className="comp">
            <Composer placeholder="Ask a doubt or add details…" onSend={g.ask} />
          </div>
        </div>
      </main>

      {g.reportOpen && (
        <ReportPanel title="Current Report" subtitle="Updating live as you answer" entries={g.entries}
          complete={g.progress.percent === 100} onClose={() => g.setReportOpen(false)} />
      )}
    </>
  )
}