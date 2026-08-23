import { AgentsNavIcon, GridIcon, ListIcon } from './icons'

export type View = 'overview' | 'logs' | 'agents'

interface SidebarProps {
  view: View
  onNavigate: (view: View) => void
}

export function Sidebar({ view, onNavigate }: SidebarProps) {
  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <img src="/logo.png" alt="" className="brand-logo" />
        <span className="brand-name">Roxy</span>
      </div>

      <div className="sidebar-nav">
        <button
          type="button"
          className={`nav-item ${view === 'overview' ? 'active' : ''}`}
          onClick={() => onNavigate('overview')}
        >
          <GridIcon />
          Overview
        </button>
        <button
          type="button"
          className={`nav-item ${view === 'logs' ? 'active' : ''}`}
          onClick={() => onNavigate('logs')}
        >
          <ListIcon />
          Logs
        </button>
        <button
          type="button"
          className={`nav-item ${view === 'agents' ? 'active' : ''}`}
          onClick={() => onNavigate('agents')}
        >
          <AgentsNavIcon />
          Agents
        </button>
      </div>

      <div style={{ flexGrow: 1 }} />

      <div className="live-pill">
        <span className="live-dot" />
        <span>Monitoring live</span>
      </div>
    </nav>
  )
}
