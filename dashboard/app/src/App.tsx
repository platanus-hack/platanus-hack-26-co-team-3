import { useEffect, useState } from 'react'
import type { SecurityLog } from './types'
import { fetchSecurityLogs } from './lib/api'
import { Sidebar, type View } from './components/Sidebar'
import { LogDrawer } from './components/LogDrawer'
import { Overview } from './views/Overview'
import { Logs } from './views/Logs'

function App() {
  const [view, setView] = useState<View>('overview')
  const [logs, setLogs] = useState<SecurityLog[]>([])
  const [selected, setSelected] = useState<SecurityLog | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    fetchSecurityLogs()
      .then((data) => {
        setLogs(data)
        setStatus('ready')
      })
      .catch(() => setStatus('error'))
  }, [])

  return (
    <div className="app-shell">
      <Sidebar view={view} onNavigate={setView} />

      {status === 'loading' && <div className="state-message">Loading logs…</div>}
      {status === 'error' && <div className="state-message">Couldn't reach the dashboard API.</div>}
      {status === 'ready' && view === 'overview' && <Overview logs={logs} onSelect={setSelected} />}
      {status === 'ready' && view === 'logs' && <Logs logs={logs} onSelect={setSelected} />}

      <LogDrawer log={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default App
