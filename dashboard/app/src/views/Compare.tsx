import { useCallback, useEffect, useState } from 'react'
import type { Agent, AgentSession, SecurityLog } from '../types'
import { fetchSessionAgents, fetchSessions } from '../lib/api'
import { withCorrelatedOutcomes } from '../lib/correlateDecisions'
import { AgentGraph } from '../components/AgentGraph'
import { NodeDrawer } from '../components/NodeDrawer'
import { correlateDecisions } from '../lib/correlateDecisions'
import { formatRelativeTime } from '../lib/format'

interface CompareProps {
  logs: SecurityLog[]
}

const POLL_MS = 4000
/** How many recent runs to inspect when looking for one of each kind. */
const SCAN = 8

interface Side {
  session: AgentSession
  agents: Agent[]
  blocked: number
}

export function Compare({ logs }: CompareProps) {
  const [unguarded, setUnguarded] = useState<Side | null>(null)
  const [guarded, setGuarded] = useState<Side | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  const load = useCallback(
    async (currentLogs: SecurityLog[]) => {
      const sessions = await fetchSessions()
      let foundGuarded: Side | null = null
      let foundUnguarded: Side | null = null

      // Newest first: the first run of each kind we meet is the one to show.
      for (const session of sessions.slice(0, SCAN)) {
        if (foundGuarded && foundUnguarded) break
        const raw = await fetchSessionAgents(session.sessionId)
        const agents = withCorrelatedOutcomes(raw, currentLogs)
        const blocked = agents.filter((a) => a.outcome === 'denied').length
        const side: Side = { session, agents, blocked }
        if (blocked > 0 && !foundGuarded) foundGuarded = side
        if (blocked === 0 && !foundUnguarded) foundUnguarded = side
      }

      setGuarded(foundGuarded)
      setUnguarded(foundUnguarded)
      setStatus('ready')
    },
    [],
  )

  useEffect(() => {
    load(logs).catch(() => setStatus('error'))
    const id = setInterval(() => {
      if (document.hidden) return
      load(logs).catch(() => {
        /* transient: keep what's on screen */
      })
    }, POLL_MS)
    return () => clearInterval(id)
  }, [load, logs])

  const allAgents = [...(unguarded?.agents ?? []), ...(guarded?.agents ?? [])]
  const selectedAgent = allAgents.find((a) => a._id === selectedAgentId) ?? null
  const decisions = correlateDecisions(allAgents, logs)

  return (
    <div className="view-content compare-view">
      <div className="compare-head">
        <div>
          <h1>La misma tarea, dos veces</h1>
          <p className="subtitle">
            Mismo flujo de agentes, misma nota maliciosa. La única variable es si Roxy estaba
            en el camino.
          </p>
        </div>
      </div>

      {status === 'loading' && <div className="state-message">Buscando corridas&hellip;</div>}
      {status === 'error' && <div className="state-message">No se pudo alcanzar la API.</div>}

      {status === 'ready' && (
        <div className="compare-body">
          <CompareSide
            side={unguarded}
            tone="bad"
            label="Nadie evaluó nada"
            verdict={unguarded ? '0 bloqueadas' : '—'}
            foot="Ninguna operación pasó por Roxy. Lo que el agente decidió, se ejecutó."
            emptyMsg="Todavía no hay una corrida sin bloqueos."
            onSelectAgent={setSelectedAgentId}
            selectedAgentId={selectedAgentId}
          />
          <CompareSide
            side={guarded}
            tone="good"
            label="Roxy intervino"
            verdict={guarded ? `${guarded.blocked} bloqueadas` : '—'}
            foot="Cada escritura se sometió antes de ejecutarse. Las indebidas nunca ocurrieron."
            emptyMsg="Todavía no hay una corrida con bloqueos."
            onSelectAgent={setSelectedAgentId}
            selectedAgentId={selectedAgentId}
          />
        </div>
      )}

      <NodeDrawer
        agent={selectedAgent}
        agents={allAgents}
        decisions={selectedAgent ? decisions.logsFor(selectedAgent._id) : []}
        onClose={() => setSelectedAgentId(null)}
        onSelectAgent={setSelectedAgentId}
      />
    </div>
  )
}

interface CompareSideProps {
  side: Side | null
  tone: 'bad' | 'good'
  label: string
  verdict: string
  foot: string
  emptyMsg: string
  selectedAgentId: string | null
  onSelectAgent: (id: string) => void
}

function CompareSide({
  side,
  tone,
  label,
  verdict,
  foot,
  emptyMsg,
  selectedAgentId,
  onSelectAgent,
}: CompareSideProps) {
  return (
    <section className={`compare-col ${tone}`}>
      <header className="compare-col-head">
        <div className="compare-label">{label}</div>
        <div className="compare-verdict">{verdict}</div>
        {side && (
          <div className="compare-meta mono">
            {side.agents.length} agentes &middot; {formatRelativeTime(side.session.startedAt)}
          </div>
        )}
      </header>

      {side ? (
        <AgentGraph
          agents={side.agents}
          session={side.session}
          selectedAgentId={selectedAgentId}
          onSelectAgent={onSelectAgent}
        />
      ) : (
        <div className="agents-canvas state-message">{emptyMsg}</div>
      )}

      <footer className="compare-foot">{foot}</footer>
    </section>
  )
}
