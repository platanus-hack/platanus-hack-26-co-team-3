import { useMemo, useState } from 'react'
import type { SecurityLog, LogStatus } from '../types'
import { formatTime } from '../lib/format'
import { StatusBadge } from '../components/StatusBadge'

interface LogsProps {
  logs: SecurityLog[]
  onSelect: (log: SecurityLog) => void
}

type StatusFilter = 'all' | LogStatus

export function Logs({ logs, onSelect }: LogsProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [mcpFilter, setMcpFilter] = useState('all')

  const mcpNames = useMemo(() => {
    const names = new Set(logs.map((l) => l.mcpName).filter((n): n is string => !!n))
    return Array.from(names).sort()
  }, [logs])

  const rows = logs.filter(
    (l) =>
      (statusFilter === 'all' || l.status === statusFilter) &&
      (mcpFilter === 'all' || l.mcpName === mcpFilter),
  )

  function pillStyle(value: StatusFilter) {
    return value === statusFilter
      ? { background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' }
      : { background: 'transparent', color: 'var(--text)', borderColor: 'var(--border)' }
  }

  return (
    <div className="view-content">
      <div>
        <h1>Logs</h1>
        <p className="subtitle">All access decisions Roxy has logged.</p>
      </div>

      <div className="filter-bar">
        <div className="filter-pills">
          <button type="button" className="filter-pill" style={pillStyle('all')} onClick={() => setStatusFilter('all')}>
            All
          </button>
          <button
            type="button"
            className="filter-pill"
            style={pillStyle('approved')}
            onClick={() => setStatusFilter('approved')}
          >
            Approved
          </button>
          <button
            type="button"
            className="filter-pill"
            style={pillStyle('denied')}
            onClick={() => setStatusFilter('denied')}
          >
            Denied
          </button>

          <select className="mcp-select" value={mcpFilter} onChange={(e) => setMcpFilter(e.target.value)}>
            <option value="all">All MCPs</option>
            {mcpNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        <div className="result-count">
          {rows.length} of {logs.length} logs
        </div>
      </div>

      <div className="logs-table">
        <div className="logs-table-header">
          <div>Status</div>
          <div>MCP</div>
          <div>Accessed by</div>
          <div>Time</div>
          <div>Description</div>
        </div>

        {rows.map((log) => (
          <div key={log._id} className="log-row" onClick={() => onSelect(log)}>
            <StatusBadge status={log.status} />
            <span className="log-mcp">{log.mcpName ?? 'Unknown MCP'}</span>
            <span className="log-accessed-by mono">{log.accessedBy}</span>
            <span className="log-time mono">{formatTime(log.time)}</span>
            <span className="log-description">{log.description}</span>
          </div>
        ))}

        {rows.length === 0 && <div className="empty-state">No logs match these filters.</div>}
      </div>
    </div>
  )
}
