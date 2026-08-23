import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Agent, AgentSession, SecurityLog } from '../types'
import { fetchSessionAgents, fetchSessions } from '../lib/api'
import { correlateDecisions, withCorrelatedOutcomes } from '../lib/correlateDecisions'
import { AgentGraph } from '../components/AgentGraph'
import { NodeDrawer } from '../components/NodeDrawer'
import { SessionList } from '../components/SessionList'

interface AgentsProps {
  /** Roxy's decisions, used to light up which agents it actually stopped. */
  logs: SecurityLog[]
}

// The demo runs the agent flow live on stage: the tree has to fill in while
// it happens, not after a manual refresh. Sessions are polled a little
// slower than the nodes inside the selected one -- a new session appears
// once, its nodes appear continuously.
const SESSIONS_POLL_MS = 4000
const AGENTS_POLL_MS = 1500

export function Agents({ logs }: AgentsProps) {
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [sessionsStatus, setSessionsStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsStatus, setAgentsStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  // While following, the newest session always wins -- so kicking off a run
  // on stage pulls the view to it with nobody touching the laptop. Clicking
  // any session turns it off, so exploring is never yanked away.
  const [following, setFollowing] = useState(true)
  const followingRef = useRef(following)
  followingRef.current = following

  const knownSessionIds = useRef<Set<string>>(new Set())

  const loadSessions = useCallback(async () => {
    const data = await fetchSessions()
    setSessions(data)
    setSessionsStatus('ready')

    const newest = data[0]
    if (!newest) return

    const isFirstLoad = knownSessionIds.current.size === 0
    const isNewSession = !knownSessionIds.current.has(newest.sessionId)
    data.forEach((s) => knownSessionIds.current.add(s.sessionId))

    if (isFirstLoad || (isNewSession && followingRef.current)) {
      setSelectedSessionId(newest.sessionId)
    }
  }, [])

  useEffect(() => {
    loadSessions().catch(() => setSessionsStatus('error'))
    const id = setInterval(() => {
      if (document.hidden) return
      loadSessions().catch(() => {
        /* transient: keep the last good list on screen */
      })
    }, SESSIONS_POLL_MS)
    return () => clearInterval(id)
  }, [loadSessions])

  useEffect(() => {
    if (!selectedSessionId) return
    let cancelled = false

    // Only the very first load blanks the canvas; refreshes patch in place so
    // the tree never flashes empty while a run is in progress.
    setAgentsStatus((s) => (s === 'idle' || s === 'error' ? 'loading' : s))
    setSelectedAgentId(null)

    async function load(sessionId: string) {
      const data = await fetchSessionAgents(sessionId)
      if (cancelled) return
      setAgents(data)
      setAgentsStatus('ready')
    }

    load(selectedSessionId).catch(() => {
      if (!cancelled) setAgentsStatus('error')
    })

    const id = setInterval(() => {
      if (document.hidden || cancelled) return
      load(selectedSessionId).catch(() => {
        /* transient: keep showing what we have */
      })
    }, AGENTS_POLL_MS)

    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [selectedSessionId])

  function handleSelectSession(sessionId: string) {
    setFollowing(false)
    setSelectedSessionId(sessionId)
  }

  // Nothing writes `outcome` onto an agent yet, so on real runs every node
  // would read as "no verdict". Roxy's own decisions are in the security log
  // -- correlate them in so the graph shows where it actually stepped in.
  const decoratedAgents = useMemo(() => withCorrelatedOutcomes(agents, logs), [agents, logs])
  const decisions = useMemo(() => correlateDecisions(agents, logs), [agents, logs])

  const selectedAgent = decoratedAgents.find((a) => a._id === selectedAgentId) ?? null
  const selectedSession = sessions.find((s) => s.sessionId === selectedSessionId) ?? null

  return (
    <div className="view-content agents-view">
      <div className="agents-head">
        <div>
          <h1>Agents</h1>
          <p className="subtitle">
            Every agent a run spawned, who spawned it, and where Roxy stepped in.
          </p>
        </div>
        <button
          type="button"
          className={`follow-toggle ${following ? 'active' : ''}`}
          onClick={() => setFollowing((f) => !f)}
          title={
            following
              ? 'Jumping to each new run as it starts'
              : 'Staying on the run you picked'
          }
        >
          <span className={`follow-dot ${following ? 'live' : ''}`} />
          {following ? 'Following live' : 'Paused'}
        </button>
      </div>

      {sessionsStatus === 'loading' && <div className="state-message">Loading runs&hellip;</div>}
      {sessionsStatus === 'error' && (
        <div className="state-message">Couldn't reach the dashboard API.</div>
      )}

      {sessionsStatus === 'ready' && (
        <div className="agents-body">
          <SessionList
            sessions={sessions}
            selectedSessionId={selectedSessionId}
            onSelect={handleSelectSession}
          />

          {agentsStatus === 'loading' && (
            <div className="agents-canvas state-message">Loading agents&hellip;</div>
          )}
          {agentsStatus === 'error' && (
            <div className="agents-canvas state-message">Couldn't load this run's agents.</div>
          )}
          {agentsStatus === 'ready' && (
            <AgentGraph
              agents={decoratedAgents}
              session={selectedSession}
              selectedAgentId={selectedAgentId}
              onSelectAgent={setSelectedAgentId}
            />
          )}
        </div>
      )}

      <NodeDrawer
        agent={selectedAgent}
        agents={decoratedAgents}
        decisions={selectedAgent ? decisions.logsFor(selectedAgent._id) : []}
        onClose={() => setSelectedAgentId(null)}
        onSelectAgent={setSelectedAgentId}
      />
    </div>
  )
}
