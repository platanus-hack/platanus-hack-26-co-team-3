import type { SecurityLog } from '../types'
import { formatTime } from '../lib/format'
import { statusTokens } from '../lib/status'
import { AlertTriangleIcon, CheckCircleIcon, ChevronRightIcon } from '../components/icons'

interface OverviewProps {
  logs: SecurityLog[]
  onSelect: (log: SecurityLog) => void
}

export function Overview({ logs, onSelect }: OverviewProps) {
  const denied = logs.filter((l) => l.status === 'denied')
  const approvedCount = logs.length - denied.length
  const alerts = denied.slice(0, 5)
  const activity = logs.slice(0, 6)

  return (
    <div className="view-content">
      <div>
        <h1>Panorama</h1>
        <p className="subtitle">Las decisiones de acceso de Roxy, en tiempo real.</p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Peticiones</div>
          <div className="stat-value">{logs.length}</div>
        </div>
        <div className="stat-card" style={{ borderColor: 'var(--green-border)' }}>
          <div className="stat-label">
            <CheckCircleIcon />
            Aprobadas
          </div>
          <div className="stat-value" style={{ color: 'var(--green)' }}>
            {approvedCount}
          </div>
        </div>
        <div className="stat-card" style={{ borderColor: 'var(--red-border)', background: 'var(--red-bg)' }}>
          <div className="stat-label">
            <AlertTriangleIcon />
            Bloqueadas
          </div>
          <div className="stat-value" style={{ color: 'var(--red)' }}>
            {denied.length}
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-header">
          <h2>Alertas activas</h2>
          <span className="count-pill">{denied.length}</span>
        </div>

        <div className="alert-list">
          {alerts.length === 0 && <div className="empty-state">Ninguna petición bloqueada.</div>}
          {alerts.map((log) => (
            <div key={log._id} className="alert-card" onClick={() => onSelect(log)}>
              <AlertTriangleIcon size={17} />
              <div className="alert-body">
                <div className="alert-title-row">
                  <span className="alert-mcp">{log.mcpName ?? 'MCP desconocido'}</span>
                  <span className="alert-status">Bloqueadas</span>
                </div>
                <div className="alert-description">{log.description}</div>
                <div className="alert-meta mono">
                  {log.accessedBy} &middot; {formatTime(log.time)}
                </div>
              </div>
              <ChevronRightIcon />
            </div>
          ))}
        </div>
      </div>

      <div className="section">
        <h2>Actividad reciente</h2>
        <div className="activity-list">
          {activity.map((log) => {
            const tokens = statusTokens(log.status)
            return (
              <div key={log._id} className="activity-row" onClick={() => onSelect(log)}>
                <span className="status-dot" style={{ background: tokens.color }} />
                <span className="activity-mcp">{log.mcpName ?? 'MCP desconocido'}</span>
                <span className="activity-description">{log.description}</span>
                <span className="activity-time mono">{formatTime(log.time)}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
