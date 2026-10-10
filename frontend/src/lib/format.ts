/** Human-friendly formatting. Times use the viewer's locale and time zone. */

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.max(0, Math.round(seconds / 60))
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes} min`
  return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`
}

export function formatMiles(miles: number): string {
  const rounded = miles >= 100 ? Math.round(miles) : Math.round(miles * 10) / 10
  return `${rounded.toLocaleString('en-US')} mi`
}

const timeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso))
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Value for an <input type="datetime-local"> in the viewer's local time. */
export function toDateTimeLocal(date: Date): string {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** Parses a datetime-local value (local time) into a Date, or null if invalid. */
export function fromDateTimeLocal(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** The next quarter hour at least `leadMinutes` from `now`. */
export function defaultDeparture(now: Date = new Date(), leadMinutes = 15): Date {
  const date = new Date(now.getTime() + leadMinutes * 60_000)
  date.setSeconds(0, 0)
  const remainder = date.getMinutes() % 15
  if (remainder) date.setMinutes(date.getMinutes() + 15 - remainder)
  return date
}
