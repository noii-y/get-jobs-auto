import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import BatchDashboard from './pages/BatchDashboard'
import History from './pages/History'
import Results from './pages/Results'
import Schedules from './pages/Schedules'
import Blacklist from './pages/Blacklist'
import Settings from './pages/Settings'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/batch" element={<BatchDashboard />} />
        <Route path="/history" element={<History />} />
        <Route path="/results" element={<Results />} />
        <Route path="/schedules" element={<Schedules />} />
        <Route path="/blacklist" element={<Blacklist />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
