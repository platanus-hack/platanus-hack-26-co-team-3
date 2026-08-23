import { useEffect, useState } from 'react'
import type { SecurityLog } from './types'
import { fetchSecurityLogs } from './lib/api'
import { dedupeLogs } from './lib/dedupeLogs'
import { Sidebar, type View } from './components/Sidebar'
import { LogDrawer } from './components/LogDrawer'
import { Overview } from './views/Overview'
import { Logs } from './views/Logs'
import { Agents } from './views/Agents'

function App() {
  const [view, setView] = useState<View>('overview')
  const [logs, setLogs] = useState<SecurityLog[]>([])
  const [selected, setSelected] = useState<SecurityLog | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    function load() {
      return fetchSecurityLogs().then((data) => {
        // The gateway records each decision twice today (see
        // research/ISSUES.md); collapse them so one decision reads as one row.
        setLogs(dedupeLogs(data))
        setStatus('ready')
      })
    }

    load().catch(() => setStatus('error'))

    // Decisions land while the demo is running -- keep the table live instead
    // of showing whatever was true when the tab was opened.
    const id = setInterval(() => {
      if (document.hidden) return
      load().catch(() => {
        /* transient: keep the last good list on screen */
      })
    }, 4000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="app-shell">
      <Sidebar view={view} onNavigate={setView} />

      {status === 'loading' && <div className="state-message">Loading logs…</div>}
      {status === 'error' && <div className="state-message">Couldn't reach the dashboard API.</div>}
      {status === 'ready' && view === 'overview' && <Overview logs={logs} onSelect={setSelected} />}
      {status === 'ready' && view === 'logs' && <Logs logs={logs} onSelect={setSelected} />}
      {view === 'agents' && <Agents logs={logs} />}

      <LogDrawer log={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default App
