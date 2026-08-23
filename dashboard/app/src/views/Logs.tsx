import { useMemo, useState } from 'react'
import type { SecurityLog, LogStatus } from '../types'
import { formatRelativeTime, formatTime } from '../lib/format'
import { decisionFacts, logMatches } from '../lib/decision'
import { StatusBadge } from '../components/StatusBadge'

interface LogsProps {
  logs: SecurityLog[]
  onSelect: (log: SecurityLog) => void
}

type StatusFilter = 'all' | LogStatus

export function Logs({ logs, onSelect }: LogsProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [mcpFilter, setMcpFilter] = useState('all')
  const [query, setQuery] = useState('')

  const mcpNames = useMemo(() => {
    const names = new Set(logs.map((l) => l.mcpName).filter((n): n is string => !!n))
    return Array.from(names).sort()
  }, [logs])

  const deniedCount = useMemo(() => logs.filter((l) => l.status === 'denied').length, [logs])

  const rows = logs.filter(
    (l) =>
      (statusFilter === 'all' || l.status === statusFilter) &&
      (mcpFilter === 'all' || l.mcpName === mcpFilter) &&
      logMatches(l, query),
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
        <p className="subtitle">
          Cada decisión que tomó Roxy &mdash; {logs.length} en total, {deniedCount} bloqueadas.
        </p>
      </div>

      <div className="filter-bar">
        <div className="filter-pills">
          <button type="button" className="filter-pill" style={pillStyle('all')} onClick={() => setStatusFilter('all')}>
            Todas
          </button>
          <button
            type="button"
            className="filter-pill"
            style={pillStyle('approved')}
            onClick={() => setStatusFilter('approved')}
          >
            Aprobadas
          </button>
          <button
            type="button"
            className="filter-pill"
            style={pillStyle('denied')}
            onClick={() => setStatusFilter('denied')}
          >
            Bloqueadas
          </button>

          <select className="mcp-select" value={mcpFilter} onChange={(e) => setMcpFilter(e.target.value)}>
            <option value="all">Todos los MCPs</option>
            {mcpNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>

          <input
            className="log-search"
            type="search"
            placeholder="Buscar agente, acción, motivo…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="result-count">
          {rows.length} de {logs.length}
        </div>
      </div>

      <div className="decision-feed">
        {rows.map((log) => {
          const facts = decisionFacts(log)
          const denied = log.status === 'denied'
          return (
            <button
              key={log._id}
              type="button"
              className={`decision-item ${denied ? 'denied' : 'approved'}`}
              onClick={() => onSelect(log)}
            >
              <div className="decision-item-main">
                <div className="decision-item-top">
                  <StatusBadge status={log.status} />
                  <span className="decision-agent mono">{log.accessedBy}</span>
                  {log.action && <span className="decision-verb mono">{log.action}</span>}
                  {facts.rulePriority !== null && denied && (
                    <span className="decision-rule-chip">regla {facts.rulePriority}</span>
                  )}
                </div>
                <div className="decision-item-why">
                  {facts.operation ? (
                    <>
                      <span className="decision-op mono">{facts.operation}</span>
                      <span className="decision-sep">·</span>
                    </>
                  ) : null}
                  {log.description}
                </div>
              </div>
              <div className="decision-item-side">
                <span className="decision-mcp">{log.mcpName ?? '—'}</span>
                <span className="decision-when" title={formatTime(log.time)}>
                  {formatRelativeTime(log.time)}
                </span>
              </div>
            </button>
          )
        })}

        {rows.length === 0 && (
          <div className="empty-state">Ninguna decisión coincide con esos filtros.</div>
        )}
      </div>
    </div>
  )
}
