import { parseApiDate } from './time'

const timeFormatter = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
})

const fullTimeFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  second: '2-digit',
})

export function formatTime(iso: string): string {
  return timeFormatter.format(parseApiDate(iso))
}

export function formatFullTime(iso: string): string {
  return fullTimeFormatter.format(parseApiDate(iso))
}

const relativeFormatter = new Intl.RelativeTimeFormat('en-US', { numeric: 'auto' })

export function formatRelativeTime(iso: string): string {
  const diffMs = parseApiDate(iso).getTime() - Date.now()
  const diffMin = Math.round(diffMs / 60_000)
  if (Math.abs(diffMin) < 60) return relativeFormatter.format(diffMin, 'minute')
  const diffHour = Math.round(diffMin / 60)
  if (Math.abs(diffHour) < 24) return relativeFormatter.format(diffHour, 'hour')
  return relativeFormatter.format(Math.round(diffHour / 24), 'day')
}
