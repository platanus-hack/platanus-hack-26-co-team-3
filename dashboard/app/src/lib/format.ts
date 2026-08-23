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
  return timeFormatter.format(new Date(iso))
}

export function formatFullTime(iso: string): string {
  return fullTimeFormatter.format(new Date(iso))
}
