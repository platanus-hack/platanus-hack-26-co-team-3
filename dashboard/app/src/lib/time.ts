/**
 * The API hands back two different timestamp shapes:
 *   /log      -> "2026-08-23T06:17:22.809000"   (naive: no timezone marker)
 *   /sessions -> "2026-08-23T06:22:15Z"         (explicit UTC)
 *
 * Both are UTC in fact -- the naive one only looks naive because it comes
 * from Mongo through Pydantic without a tzinfo. `new Date()` reads a string
 * with no marker as LOCAL time, which silently shifted every log timestamp
 * by the viewer's UTC offset (5 hours here) and made any time-window
 * comparison against them wrong.
 *
 * Parse through here, never `new Date(raw)` directly.
 */
export function parseApiDate(raw: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw.trim())
  return new Date(hasZone ? raw : `${raw}Z`)
}

export function parseApiTime(raw: string): number {
  return parseApiDate(raw).getTime()
}
