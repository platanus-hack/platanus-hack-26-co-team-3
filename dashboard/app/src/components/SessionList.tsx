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
      {sessions.length === 0 && <div className="empty-state">No agent sessions yet.</div>}
      {sessions.map((session) => {
        const tokens = outcomeTokens(session.outcome)
        const active = session.sessionId === selectedSessionId
        return (
          <div
            key={session.sessionId}
            className={`session-card ${active ? 'active' : ''}`}
            onClick={() => onSelect(session.sessionId)}
          >
            <span className="status-dot" style={{ background: tokens.color }} />
            <div className="session-card-body">
              <div className="session-card-title">{session.rootPurpose}</div>
              <div className="session-card-meta mono">
                {session.agentCount} agents &middot; {formatRelativeTime(session.startedAt)}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
