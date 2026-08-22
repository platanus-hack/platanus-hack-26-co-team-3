export function GridIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 20 20" fill="none">
      <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="11" y="2.5" width="6.5" height="6.5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="2.5" y="11" width="6.5" height="6.5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="11" y="11" width="6.5" height="6.5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

export function ListIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 20 20" fill="none">
      <rect x="2.5" y="4" width="15" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2.5" y="8.5" width="15" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2.5" y="13" width="15" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

export function CheckCircleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="7.5" stroke="var(--green)" strokeWidth="1.6" />
      <path d="M6.5 10L9 12.5L13.5 7.5" stroke="var(--green)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function AlertTriangleIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <path d="M10 2.5L18 16.5H2L10 2.5Z" stroke="var(--red)" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M10 8V11.3" stroke="var(--red)" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="10" cy="13.6" r="0.9" fill="var(--red)" />
    </svg>
  )
}

export function ChevronRightIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 20 20" fill="none">
      <path d="M7.5 4.5L13 10L7.5 15.5" stroke="var(--text-muted)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M3 3L13 13M13 3L3 13" stroke="var(--text)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}
