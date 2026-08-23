export type LogStatus = 'approved' | 'denied'

export interface ViolatedRule {
  priority: number
  instruction: string
}

export interface SecurityLog {
  _id: string
  status: LogStatus
  mcpId: string | null
  mcpName: string | null
  time: string
  accessedBy: string
  action: string | null
  violatedRule: ViolatedRule | null
  description: string
}
