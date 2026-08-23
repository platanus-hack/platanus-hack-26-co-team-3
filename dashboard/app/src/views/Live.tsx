import { useCallback, useEffect, useRef, useState } from 'react'
import type { Agent, AgentSession, ConsistencyReport, SecurityLog } from '../types'
import { fetchConsistency, fetchSessionAgents, fetchSessions } from '../lib/api'
import { withCorrelatedOutcomes } from '../lib/correlateDecisions'
import { AgentGraph } from '../components/AgentGraph'

interface LiveProps {
  logs: SecurityLog[]
}

// Everything on this screen is polled: it is meant to be projected and left
// alone while a run happens in front of an audience.
const CONSISTENCY_POLL_MS = 2000
const SESSIONS_POLL_MS = 3000
const AGENTS_POLL_MS = 1500

export function Live({ logs }: LiveProps) {
  const [report, setReport] = useState<ConsistencyReport | null>(null)
  const [reportError, setReportError] = useState(false)
  const [session, setSession] = useState<AgentSession | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  const sessionIdRef = useRef<string | null>(null)

  useEffect(() => {
    function load() {
      return fetchConsistency().then((r) => {
        setReport(r)
        setReportError(false)
      })
    }
    load().catch(() => setReportError(true))
    const id = setInterval(() => {
      if (document.hidden) return
      load().catch(() => setReportError(true))
    }, CONSISTENCY_POLL_MS)
    return () => clearInterval(id)
  }, [])

  // Always follows the newest run: start the flow on stage and this screen
  // moves to it on its own.
  const loadSessions = useCallback(async () => {
    const data = await fetchSessions()
    const newest = data[0]
    if (!newest) return
    setSession(newest)
    if (sessionIdRef.current !== newest.sessionId) {
      sessionIdRef.current = newest.sessionId
      setAgents([])
      setSelectedAgentId(null)
    }
  }, [])

  useEffect(() => {
    loadSessions().catch(() => {})
    const id = setInterval(() => {
      if (document.hidden) return
      loadSessions().catch(() => {})
    }, SESSIONS_POLL_MS)
    return () => clearInterval(id)
  }, [loadSessions])

  useEffect(() => {
    if (!session) return
    const sid = session.sessionId
    function load() {
      return fetchSessionAgents(sid).then(setAgents)
    }
    load().catch(() => {})
    const id = setInterval(() => {
      if (document.hidden) return
      load().catch(() => {})
    }, AGENTS_POLL_MS)
    return () => clearInterval(id)
  }, [session])

  const decorated = withCorrelatedOutcomes(agents, logs)
  const blocked = decorated.filter((a) => a.outcome === 'denied').length
  const violated = report && !report.consistent

  return (
    <div className="live-view">
      <aside className={`live-data ${violated ? 'is-violated' : ''}`}>
        <div className="live-label">Los datos de facturación</div>

        {reportError && <div className="live-verdict unknown">Sin conexión</div>}

        {!reportError && report && (
          <>
            <div className={`live-verdict ${violated ? 'bad' : 'good'}`}>
              {violated ? 'Corrompido' : 'Íntegro'}
            </div>
            <div className="live-checked">
              {report.checked} facturas verificadas
              {!violated && <span className="live-checkmark"> · sin violaciones</span>}
            </div>

            {violated && (
              <div className="live-violations">
                {report.violations.slice(0, 3).map((v, i) => (
                  <div key={`${v.invoice_id}-${i}`} className="live-violation">
                    <div className="live-violation-id mono">{v.invoice_id}</div>
                    <div className="live-violation-rule">{v.rule}</div>
                    <div className="live-violation-nums mono">
                      <span className="expected">{String(v.expected)}</span>
                      <span className="arrow">→</span>
                      <span className="found">{String(v.found)}</span>
                    </div>
                  </div>
                ))}
                {report.violations.length > 3 && (
                  <div className="live-violation-more">
                    +{report.violations.length - 3} más
                  </div>
                )}
              </div>
            )}
          </>
        )}

        <div className="live-foot">
          {violated ? 'Nadie lo evaluó. Nadie lo registró.' : 'Cada escritura pasó por Roxy.'}
        </div>
      </aside>

      <section className="live-agents">
        <div className="live-agents-head">
          <div className="live-label">Los agentes</div>
          <div className="live-agents-stats">
            <span className="live-stat">
              <strong>{agents.length}</strong> agentes
            </span>
            {blocked > 0 && (
              <span className="live-stat blocked">
                <strong>{blocked}</strong> bloqueados por Roxy
              </span>
            )}
          </div>
        </div>

        {agents.length === 0 ? (
          <div className="live-waiting">
            <span className="live-waiting-dot" />
            Esperando una corrida&hellip;
          </div>
        ) : (
          <AgentGraph
            agents={decorated}
            session={session}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
          />
        )}
      </section>
    </div>
  )
}
