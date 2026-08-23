import { useMemo, useState } from 'react'
import type { Agent } from '../types'
import { ancestorChain, layoutTree, worstAgents } from '../lib/agentGraph'
import { outcomeTokens } from '../lib/nodeStatus'
import { ReplayIcon } from './icons'

interface AgentGraphProps {
  agents: Agent[]
  selectedAgentId: string | null
  onSelectAgent: (agentId: string) => void
}

const NODE_WIDTH = 208
const NODE_HEIGHT = 68
const X_GAP = 36
const Y_GAP = 64
const REVEAL_STEP_MS = 220

export function AgentGraph({ agents, selectedAgentId, onSelectAgent }: AgentGraphProps) {
  const laidOut = useMemo(() => layoutTree(agents), [agents])
  const [replayKey, setReplayKey] = useState(0)

  // No explicit selection yet: default to pre-highlighting the causal chain
  // of whatever failed, so the story reads before anyone clicks anything.
  const highlighted = useMemo(() => {
    if (selectedAgentId) return new Set(ancestorChain(agents, selectedAgentId))
    const worst = worstAgents(agents)
    return worst.length > 0 ? new Set(ancestorChain(agents, worst[0]._id)) : new Set<string>()
  }, [agents, selectedAgentId])

  const hasHighlight = highlighted.size > 0
  const byId = useMemo(() => new Map(laidOut.map((a) => [a._id, a])), [laidOut])

  const maxDepth = laidOut.reduce((m, a) => Math.max(m, a.depth), 0)
  const maxX = laidOut.reduce((m, a) => Math.max(m, a.x), 0)
  const width = (maxX + 1) * (NODE_WIDTH + X_GAP)
  const height = (maxDepth + 1) * (NODE_HEIGHT + Y_GAP)

  function nodeCenter(a: { x: number; depth: number }) {
    return {
      cx: a.x * (NODE_WIDTH + X_GAP) + NODE_WIDTH / 2,
      cy: a.depth * (NODE_HEIGHT + Y_GAP) + NODE_HEIGHT / 2,
    }
  }

  if (agents.length === 0) {
    return (
      <div className="agents-canvas">
        <div className="empty-state">Select a session to see its agent tree.</div>
      </div>
    )
  }

  return (
    <div className="agents-canvas">
      <div className="graph-toolbar">
        <button type="button" className="replay-btn" onClick={() => setReplayKey((k) => k + 1)}>
          <ReplayIcon />
          Replay
        </button>
      </div>

      <div className="graph-scroll">
        <div className="graph-surface" style={{ width, height }} key={replayKey}>
          <svg className="graph-edges" width={width} height={height}>
            {laidOut.map((agent) => {
              if (agent.parentId === null) return null
              const parent = byId.get(agent.parentId)
              if (!parent) return null
              const from = nodeCenter(parent)
              const to = nodeCenter(agent)
              const midY = (from.cy + to.cy) / 2
              const isAncestorEdge = highlighted.has(agent._id) && highlighted.has(parent._id)
              return (
                <path
                  key={agent._id}
                  className={`graph-edge ${isAncestorEdge ? 'is-ancestor' : ''} ${
                    hasHighlight && !isAncestorEdge ? 'is-dimmed' : ''
                  }`}
                  d={`M${from.cx},${from.cy + NODE_HEIGHT / 2} C${from.cx},${midY} ${to.cx},${midY} ${to.cx},${
                    to.cy - NODE_HEIGHT / 2
                  }`}
                  pathLength={1}
                  style={{ animationDelay: `${agent.revealIndex * REVEAL_STEP_MS}ms` }}
                />
              )
            })}
          </svg>

          {laidOut.map((agent) => {
            const tokens = outcomeTokens(agent.outcome)
            const isFlagged = agent.outcome === 'denied' || agent.outcome === 'error'
            const isAncestor = highlighted.has(agent._id)
            const isDimmed = hasHighlight && !isAncestor
            const { cx, cy } = nodeCenter(agent)
            return (
              <button
                key={agent._id}
                type="button"
                className={[
                  'graph-node-card',
                  agent.outcome && `outcome-${agent.outcome}`,
                  isFlagged && 'is-flagged',
                  isAncestor && 'is-ancestor',
                  isDimmed && 'is-dimmed',
                  agent._id === selectedAgentId && 'is-selected',
                ]
                  .filter(Boolean)
                  .join(' ')}
                style={{
                  left: cx - NODE_WIDTH / 2,
                  top: cy - NODE_HEIGHT / 2,
                  width: NODE_WIDTH,
                  height: NODE_HEIGHT,
                  borderColor: tokens.border,
                  background: tokens.bg,
                  animationDelay: `${agent.revealIndex * REVEAL_STEP_MS}ms`,
                }}
                onClick={() => onSelectAgent(agent._id)}
              >
                <span className="graph-node-purpose">{agent.purpose}</span>
                <span className="node-type-pill" style={{ color: tokens.color }}>
                  {tokens.label}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
