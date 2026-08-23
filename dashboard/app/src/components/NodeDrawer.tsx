import type { MouseEvent } from 'react'
import type { Agent, SecurityLog } from '../types'
import { ancestorChain } from '../lib/agentGraph'
import { outcomeTokens } from '../lib/nodeStatus'
import { explainDecision } from '../lib/decision'
import { formatFullTime } from '../lib/format'
import { CloseIcon } from './icons'

interface NodeDrawerProps {
  agent: Agent | null
  agents: Agent[]
  /** Roxy decisions correlated to this agent, newest first. */
  decisions: SecurityLog[]
  onClose: () => void
  onSelectAgent: (agentId: string) => void
}

export function NodeDrawer({ agent, agents, decisions, onClose, onSelectAgent }: NodeDrawerProps) {
  if (!agent) return null
  const tokens = outcomeTokens(agent.outcome)
  const chain = ancestorChain(agents, agent._id)
  const byId = new Map(agents.map((a) => [a._id, a]))
  const launcher = chain.length > 1 ? byId.get(chain[chain.length - 2]) : null

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
          <button type="button" className="close-btn" aria-label="Cerrar" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        {/* The three questions someone actually has when they click a node,
            in the order they ask them: what is this, what did it try, who
            sent it. Raw ids come last -- they answer none of the three. */}
        <div className="drawer-eyebrow">La tarea de este agente</div>
        <div className="drawer-title">{agent.purpose}</div>
        {launcher && (
          <div className="drawer-launcher">
            Lo lanzó{' '}
            <button
              type="button"
              className="drawer-launcher-link"
              onClick={() => onSelectAgent(launcher._id)}
            >
              {launcher.purpose}
            </button>
          </div>
        )}

        <div className="drawer-fields">
          <div className="drawer-field">
            <div className="drawer-field-label">Qué intentó hacer &middot; y qué dijo Roxy</div>

            {decisions.length === 0 && (
              <div className="decision-none">
                Este agente no intentó ninguna operación que Roxy tuviera que evaluar.
              </div>
            )}

            <div className="decision-list">
              {decisions.map((log) => {
                const denied = log.status === 'denied'
                const { attempt, verdict } = explainDecision(log)
                return (
                  <div key={log._id} className={`decision-card ${denied ? 'denied' : 'approved'}`}>
                    <div className="decision-attempt">{attempt ?? 'Operación sin detalle'}</div>
                    <div className="decision-target mono">
                      {[log.action, log.mcpName].filter(Boolean).join(' · ')}
                    </div>
                    <div className="decision-outcome">
                      <span className="decision-outcome-dot" />
                      {verdict}
                    </div>
                    <div className="decision-foot">
                      <span className="mono">{formatFullTime(log.time)}</span>
                      <span className="decision-raw mono" title={log.description}>
                        {log.description}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {chain.length > 1 && (
            <div className="drawer-field">
              <div className="drawer-field-label">La cadena completa, desde la tarea original</div>
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

          <div className="drawer-ids mono">
            <span>agente {agent._id}</span>
            <span>corrida {agent.sessionId}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
