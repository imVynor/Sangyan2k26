import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { GrievanceProvider } from './context/GrievanceContext'
import Sidebar from './components/Sidebar'
import LoginPage from './components/pages/LoginPage'
import ReportsPage from './components/pages/ReportsPage'
import ChatPage from './components/pages/ChatPage'
import HomePage from './components/pages/HomePage'

// Layout = sidebar on the left + whichever page matches the URL on the right (<Outlet />)
function Layout() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace /> // route protection
  return (
    <div className="shell">
      <Sidebar />
      <Outlet />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <GrievanceProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/reports/:id" element={<ReportsPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Route>
        </Routes>
      </GrievanceProvider>
    </AuthProvider>
  )
}
