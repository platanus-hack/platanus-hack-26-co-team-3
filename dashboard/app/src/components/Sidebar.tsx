import { AgentsNavIcon, CompareIcon, GridIcon, ListIcon, LiveIcon } from './icons'

export type View = 'live' | 'compare' | 'overview' | 'logs' | 'agents'

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
          className={`nav-item ${view === 'live' ? 'active' : ''}`}
          onClick={() => onNavigate('live')}
        >
          <LiveIcon />
          Live
        </button>
        <button
          type="button"
          className={`nav-item ${view === 'compare' ? 'active' : ''}`}
          onClick={() => onNavigate('compare')}
        >
          <CompareIcon />
          Comparar
        </button>
        <button
          type="button"
          className={`nav-item ${view === 'overview' ? 'active' : ''}`}
          onClick={() => onNavigate('overview')}
        >
          <GridIcon />
          Panorama
        </button>
        <button
          type="button"
          className={`nav-item ${view === 'logs' ? 'active' : ''}`}
          onClick={() => onNavigate('logs')}
        >
          <ListIcon />
          Decisiones
        </button>
        <button
          type="button"
          className={`nav-item ${view === 'agents' ? 'active' : ''}`}
          onClick={() => onNavigate('agents')}
        >
          <AgentsNavIcon />
          Agentes
        </button>
      </div>

      <div style={{ flexGrow: 1 }} />

      <div className="live-pill">
        <span className="live-dot" />
        <span>En vivo</span>
      </div>
    </nav>
  )
}
