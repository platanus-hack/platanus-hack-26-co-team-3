export type LogStatus = 'approved' | 'denied'

export interface SecurityLog {
  _id: string
  status: LogStatus
  mcpId: string | null
  mcpName: string | null
  time: string
  accessedBy: string
  description: string
}
