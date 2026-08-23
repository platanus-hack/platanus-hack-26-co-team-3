import type { MouseEvent } from 'react'
import type { Agent } from '../types'
import { ancestorChain } from '../lib/agentGraph'
import { outcomeTokens } from '../lib/nodeStatus'
import { CloseIcon } from './icons'

interface NodeDrawerProps {
  agent: Agent | null
  agents: Agent[]
  onClose: () => void
  onSelectAgent: (agentId: string) => void
}

export function NodeDrawer({ agent, agents, onClose, onSelectAgent }: NodeDrawerProps) {
  if (!agent) return null
  const tokens = outcomeTokens(agent.outcome)
  const chain = ancestorChain(agents, agent._id)
  const byId = new Map(agents.map((a) => [a._id, a]))

  function stopClick(e: MouseEvent) {
    e.stopPropagation()
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={stopClick}>
        <div className="drawer-header">
          <span
            className="status-badge"
            style={{ background: tokens.bg, color: tokens.color, borderColor: tokens.border }}
          >
            {tokens.label}
          </span>
          <button type="button" className="close-btn" aria-label="Close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        <div className="drawer-title">{agent.purpose}</div>

        <div className="drawer-fields">
          <div className="drawer-field">
            <div className="drawer-field-label">Agent ID</div>
            <div className="drawer-field-value mono muted">{agent._id}</div>
          </div>
          <div className="drawer-field">
            <div className="drawer-field-label">Session</div>
            <div className="drawer-field-value mono muted">{agent.sessionId}</div>
          </div>
          {chain.length > 1 && (
            <div className="drawer-field">
              <div className="drawer-field-label">Causal chain</div>
              <div className="breadcrumb-list">
                {chain.map((id, i) => {
                  const node = byId.get(id)
                  if (!node) return null
                  return (
                    <span key={id} className="breadcrumb-item">
                      <button
                        type="button"
                        className={`breadcrumb-chip ${id === agent._id ? 'current' : ''}`}
                        onClick={() => onSelectAgent(id)}
                      >
                        {node.purpose}
                      </button>
                      {i < chain.length - 1 && <span className="breadcrumb-sep">&rarr;</span>}
                    </span>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
