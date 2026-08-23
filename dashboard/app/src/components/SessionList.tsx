import type { AgentSession } from '../types'
import { formatRelativeTime } from '../lib/format'
import { outcomeTokens } from '../lib/nodeStatus'

interface SessionListProps {
  sessions: AgentSession[]
  selectedSessionId: string | null
  onSelect: (sessionId: string) => void
}

export function SessionList({ sessions, selectedSessionId, onSelect }: SessionListProps) {
  return (
    <div className="agents-sessions">
      {sessions.length === 0 && <div className="empty-state">Todavía no hay corridas.</div>}
      {sessions.map((session) => {
        const tokens = outcomeTokens(session.outcome)
        const active = session.sessionId === selectedSessionId
        return (
          <button
            key={session.sessionId}
            type="button"
            className={`session-card ${active ? 'active' : ''}`}
            onClick={() => onSelect(session.sessionId)}
          >
            <span className="status-dot" style={{ background: tokens.color }} />
            <span className="session-card-body">
              <span className="session-card-title">{session.rootPurpose}</span>
              <span className="session-card-meta mono">
                {session.agentCount} agentes &middot; {formatRelativeTime(session.startedAt)}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
