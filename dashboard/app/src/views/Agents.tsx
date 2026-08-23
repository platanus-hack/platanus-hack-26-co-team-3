import { useEffect, useState } from 'react'
import type { Agent, AgentSession } from '../types'
import { fetchSessionAgents, fetchSessions } from '../lib/api'
import { AgentGraph } from '../components/AgentGraph'
import { NodeDrawer } from '../components/NodeDrawer'
import { SessionList } from '../components/SessionList'

export function Agents() {
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [sessionsStatus, setSessionsStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsStatus, setAgentsStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  useEffect(() => {
    fetchSessions()
      .then((data) => {
        setSessions(data)
        setSessionsStatus('ready')
        if (data.length > 0) setSelectedSessionId(data[0].sessionId)
      })
      .catch(() => setSessionsStatus('error'))
  }, [])

  useEffect(() => {
    if (!selectedSessionId) return
    setAgentsStatus('loading')
    setSelectedAgentId(null)
    fetchSessionAgents(selectedSessionId)
      .then((data) => {
        setAgents(data)
        setAgentsStatus('ready')
      })
      .catch(() => setAgentsStatus('error'))
  }, [selectedSessionId])

  const selectedAgent = agents.find((a) => a._id === selectedAgentId) ?? null

  return (
    <div className="view-content">
      <div>
        <h1>Agents</h1>
        <p className="subtitle">The delegation tree behind each run &mdash; pick a session to see it.</p>
      </div>

      {sessionsStatus === 'loading' && <div className="state-message">Loading sessions&hellip;</div>}
      {sessionsStatus === 'error' && <div className="state-message">Couldn't reach the dashboard API.</div>}

      {sessionsStatus === 'ready' && (
        <div className="agents-body">
          <SessionList
            sessions={sessions}
            selectedSessionId={selectedSessionId}
            onSelect={setSelectedSessionId}
          />

          {agentsStatus === 'loading' && <div className="agents-canvas state-message">Loading agents&hellip;</div>}
          {agentsStatus === 'error' && (
            <div className="agents-canvas state-message">Couldn't load this session's agents.</div>
          )}
          {agentsStatus === 'ready' && (
            <AgentGraph agents={agents} selectedAgentId={selectedAgentId} onSelectAgent={setSelectedAgentId} />
          )}
        </div>
      )}

      <NodeDrawer
        agent={selectedAgent}
        agents={agents}
        onClose={() => setSelectedAgentId(null)}
        onSelectAgent={setSelectedAgentId}
      />
    </div>
  )
}
