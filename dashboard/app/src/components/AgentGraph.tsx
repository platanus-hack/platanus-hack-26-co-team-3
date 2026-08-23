import { useEffect, useMemo, useRef, useState } from 'react'
import type { Agent, AgentSession } from '../types'
import { ancestorChain, layoutTree, worstAgents } from '../lib/agentGraph'
import { outcomeTokens } from '../lib/nodeStatus'
import { ReplayIcon } from './icons'

interface AgentGraphProps {
  agents: Agent[]
  session: AgentSession | null
  selectedAgentId: string | null
  onSelectAgent: (agentId: string) => void
}

const NODE_WIDTH = 190
const NODE_HEIGHT = 66
const X_GAP = 24
const Y_GAP = 56
const REVEAL_STEP_MS = 200

export function AgentGraph({ agents, session, selectedAgentId, onSelectAgent }: AgentGraphProps) {
  const laidOut = useMemo(() => layoutTree(agents), [agents])
  const [replayKey, setReplayKey] = useState(0)

  // A wide tree used to overflow its pane and sit off to one side. Measure the
  // pane and shrink the whole thing until it fits, so the shape of the run is
  // visible at a glance instead of needing to be scrolled into view.
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [scale, setScale] = useState(1)

  // Nodes that arrive while a run is in flight should pop in on their own,
  // not wait behind the stagger of everything already on screen. Only the
  // batch present at first paint is staggered.
  const seenIds = useRef<Set<string>>(new Set())
  const sessionKey = session?.sessionId ?? null
  const lastSessionKey = useRef<string | null>(null)
  if (lastSessionKey.current !== sessionKey) {
    lastSessionKey.current = sessionKey
    seenIds.current = new Set()
  }
  const firstPaint = seenIds.current.size === 0

  useEffect(() => {
    agents.forEach((a) => seenIds.current.add(a._id))
  }, [agents])

  // With nothing selected, pre-highlight the chain that led to whatever went
  // wrong. The story should be readable before anyone clicks -- on stage
  // there is no time to go hunting for the bad node.
  const highlighted = useMemo(() => {
    if (selectedAgentId) return new Set(ancestorChain(agents, selectedAgentId))
    const worst = worstAgents(agents)
    return worst.length > 0 ? new Set(ancestorChain(agents, worst[0]._id)) : new Set<string>()
  }, [agents, selectedAgentId])

  const hasHighlight = highlighted.size > 0
  const byId = useMemo(() => new Map(laidOut.map((a) => [a._id, a])), [laidOut])

  const counts = useMemo(() => {
    let denied = 0
    let errored = 0
    for (const a of agents) {
      if (a.outcome === 'denied') denied += 1
      if (a.outcome === 'error') errored += 1
    }
    return { denied, errored }
  }, [agents])

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

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    function fit() {
      const node = scrollRef.current
      if (!node || width === 0 || height === 0) return
      const padding = 56
      const availableW = node.clientWidth - padding
      const availableH = node.clientHeight - padding
      if (availableW <= 0 || availableH <= 0) return
      // Only ever shrink: blowing a small tree up to fill the pane looks wrong.
      setScale(Math.min(1, availableW / width, availableH / height))
    }
    fit()
    const observer = new ResizeObserver(fit)
    observer.observe(el)
    return () => observer.disconnect()
  }, [width, height])

  if (agents.length === 0) {
    return (
      <div className="agents-canvas">
        <div className="empty-state">No agents recorded for this run yet.</div>
      </div>
    )
  }

  return (
    <div className="agents-canvas">
      <div className="graph-toolbar">
        <div className="graph-summary">
          <span className="graph-summary-main">{agents.length} agents</span>
          {counts.denied > 0 && (
            <span className="graph-chip denied">{counts.denied} blocked by Roxy</span>
          )}
          {counts.errored > 0 && <span className="graph-chip error">{counts.errored} failed</span>}
          {counts.denied === 0 && counts.errored === 0 && (
            <span className="graph-chip clean">nothing blocked</span>
          )}
        </div>
        <button
          type="button"
          className="replay-btn"
          onClick={() => setReplayKey((k) => k + 1)}
          title="Replay the reveal in the order the agents actually ran"
        >
          <ReplayIcon />
          Replay
        </button>
      </div>

      <div className="graph-scroll" ref={scrollRef}>
        <div
          className="graph-surface"
          style={{ width, height, transform: `scale(${scale})` }}
          key={`${sessionKey}-${replayKey}`}
        >
          <svg className="graph-edges" width={width} height={height}>
            {laidOut.map((agent) => {
              if (agent.parentId === null) return null
              const parent = byId.get(agent.parentId)
              if (!parent) return null
              const from = nodeCenter(parent)
              const to = nodeCenter(agent)
              const midY = (from.cy + to.cy) / 2
              const isAncestorEdge = highlighted.has(agent._id) && highlighted.has(parent._id)
              const delay = firstPaint ? agent.revealIndex * REVEAL_STEP_MS : 0
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
                  style={{ animationDelay: `${delay}ms` }}
                />
              )
            })}
          </svg>

          {laidOut.map((agent) => {
            const tokens = outcomeTokens(agent.outcome)
            const isFlagged = agent.outcome === 'denied' || agent.outcome === 'error'
            const isAncestor = highlighted.has(agent._id)
            const isDimmed = hasHighlight && !isAncestor
            const isRoot = agent.parentId === null
            const { cx, cy } = nodeCenter(agent)
            const delay = firstPaint ? agent.revealIndex * REVEAL_STEP_MS : 0
            return (
              <button
                key={agent._id}
                type="button"
                className={[
                  'graph-node-card',
                  agent.outcome && `outcome-${agent.outcome}`,
                  isRoot && 'is-root',
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
                  minHeight: NODE_HEIGHT,
                  animationDelay: `${delay}ms`,
                }}
                onClick={() => onSelectAgent(agent._id)}
              >
                <span className="graph-node-role">
                  {isRoot ? 'Orchestrator' : `Depth ${agent.depth}`}
                </span>
                <span className="graph-node-purpose">{agent.purpose}</span>
                {agent.outcome && (
                  <span className="node-outcome-pill" style={{ color: tokens.color }}>
                    <span className="node-outcome-dot" style={{ background: tokens.color }} />
                    {tokens.label}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
