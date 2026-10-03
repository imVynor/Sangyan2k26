import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useGrievance } from '../context/GrievanceContext'
import { SAMPLE_REPORTS } from './data/flow'
import ProgressList from './ProgressList'
import { checkBackendHealth } from '../services/api' // your existing file, unchanged

function Item({ icon, label, onClick, active, extra }) {
  return (
    <button className={`nav ${active ? 'on' : ''}`} onClick={onClick}>
      <i>{icon}</i>
      <span className="t">{label}{extra}</span>
    </button>
  )
}

// One sidebar, three modes depending on the URL: home, reports, chat
export default function Sidebar() {
  const { user } = useAuth()
  const g = useGrievance()
  const nav = useNavigate()
  const { pathname } = useLocation()
  const [min, setMin] = useState(window.innerWidth < 820) // minimised by default on phones
  const [q, setQ] = useState('')
  const [online, setOnline] = useState(false)

  // small backend status dot at the bottom of the sidebar (re-uses your health check)
  useEffect(() => {
    checkBackendHealth().then((h) => setOnline(!!h?.connected)).catch(() => setOnline(false))
  }, [])

  const mode = pathname.startsWith('/chat') ? 'chat' : pathname.startsWith('/reports') ? 'reports' : 'home'
  const openId = pathname.split('/')[2]
  const recent = SAMPLE_REPORTS.slice(0, 3).filter((r) => r.title.toLowerCase().includes(q.toLowerCase()))

  return (
    <aside className={`rail ${min ? 'min' : ''}`}>
      <div className="hd">
        <div className="av">{user.name[0].toUpperCase()}</div>
        <b className="t">{user.name}</b>
        <button className="mz" onClick={() => setMin(!min)} title="Minimise sidebar">{min ? '»' : '«'}</button>
      </div>

      {mode === 'home' && (
        <>
          <input className="t" placeholder="🔍 Search grievances" value={q} onChange={(e) => setQ(e.target.value)} style={{ margin: '0 0 8px' }} />
          <Item icon="＋" label="New Grievance" active onClick={() => nav('/')} />
          <Item icon="📄" label="Reports" onClick={() => nav('/reports')} />
          <div className="lbl t">Recent</div>
          <div className="t">
            {recent.map((r) => (
              <div key={r.id} className="rc" onClick={() => nav('/reports/' + r.id)}>
                {r.title}<small>{r.status}</small>
              </div>
            ))}
          </div>
        </>
      )}

      {mode === 'reports' && (
        <>
          <Item icon="🏠" label="Home" onClick={() => nav('/')} />
          <Item icon="＋" label="New Grievance" onClick={() => nav('/')} />
          <div className="lbl t">Reports</div>
          <div className="t">
            {SAMPLE_REPORTS.map((r) => (
              <div key={r.id} className={`rc ${r.id === openId ? 'on' : ''}`} onClick={() => nav('/reports/' + r.id)}>
                {r.title}<small>{r.date} · {r.status}</small>
              </div>
            ))}
          </div>
        </>
      )}

      {mode === 'chat' && (
        <>
          <Item icon="🏠" label="Home" onClick={() => nav('/')} />
          <Item icon="＋" label="New Grievance" onClick={() => nav('/')} />
          <Item icon="↩" label="Back to Query" active={!g.reportOpen} onClick={() => g.setReportOpen(false)} />
          <Item icon="📄" label="Current Report" active={g.reportOpen} onClick={() => g.setReportOpen(true)}
            extra={<span className="mu"> {g.progress.percent}%</span>} />
          <div className="lbl t">Report progress</div>
          <ProgressList entries={g.entries} progress={g.progress} />
        </>
      )}
      <div className="sbfoot t">
        <span className={`dot ${online ? 'on' : ''}`} /> Backend {online ? 'connected' : 'offline (demo mode)'}
      </div>
    </aside>
  )
}
