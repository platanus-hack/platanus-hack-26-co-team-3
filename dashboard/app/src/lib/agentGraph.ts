import type { Agent } from '../types'

export interface LaidOutAgent extends Agent {
  depth: number
  x: number
  // Position in the original (API insertion / chronological) order --
  // drives the reveal animation, independent of tree layout order.
  revealIndex: number
}

/** Assigns each agent a depth (distance from its session's root) and an x
 * slot (leaves get sequential slots, a parent's x is the midpoint of its
 * children's), for a simple top-down tree layout. */
export function layoutTree(agents: Agent[]): LaidOutAgent[] {
  const revealIndexById = new Map(agents.map((a, i) => [a._id, i]))
  const byParent = new Map<string | null, Agent[]>()
  for (const agent of agents) {
    const siblings = byParent.get(agent.parentId) ?? []
    siblings.push(agent)
    byParent.set(agent.parentId, siblings)
  }

  const result: LaidOutAgent[] = []
  let nextX = 0

  function visit(agent: Agent, depth: number): number {
    const children = byParent.get(agent._id) ?? []
    let x: number
    if (children.length === 0) {
      x = nextX
      nextX += 1
    } else {
      const childXs = children.map((child) => visit(child, depth + 1))
      x = (childXs[0] + childXs[childXs.length - 1]) / 2
    }
    result.push({ ...agent, depth, x, revealIndex: revealIndexById.get(agent._id) ?? 0 })
    return x
  }

  for (const root of byParent.get(null) ?? []) visit(root, 0)

  return result
}

/** Walks parentId up from `agentId` to its session's root. Returns ids
 * root-first (so callers can render it as a breadcrumb in causal order). */
export function ancestorChain(agents: Agent[], agentId: string): string[] {
  const byId = new Map(agents.map((agent) => [agent._id, agent]))
  const chain: string[] = []
  const seen = new Set<string>()
  let current: string | null = agentId

  while (current && byId.has(current) && !seen.has(current)) {
    seen.add(current)
    chain.push(current)
    current = byId.get(current)!.parentId
  }

  return chain.reverse()
}

const OUTCOME_RANK: Record<string, number> = { error: 2, denied: 1, ok: 0 }

/** Agents sharing the worst recorded outcome in the tree -- empty if
 * nothing worse than 'ok' (or nothing recorded at all) exists, so a clean
 * or not-yet-instrumented session doesn't get a false "something failed"
 * highlight. */
export function worstAgents(agents: Agent[]): Agent[] {
  let bestRank = -1
  let worst: Agent[] = []
  for (const agent of agents) {
    if (agent.outcome === null) continue
    const rank = OUTCOME_RANK[agent.outcome]
    if (rank > bestRank) {
      bestRank = rank
      worst = [agent]
    } else if (rank === bestRank) {
      worst.push(agent)
    }
  }
  return bestRank >= 1 ? worst : []
}
