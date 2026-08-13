import type {
  DashboardCalendarEvent,
  DashboardMatch,
} from '../types/dashboard'

export function formatDashboardDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    weekday: 'short',
  }).format(new Date(`${value}T12:00:00`))
}

function formatTime(value: string) {
  const [hours = 0, minutes = 0] = value.split(':').map(Number)
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(2000, 0, 1, hours, minutes))
}

export function formatDashboardTime(event: DashboardCalendarEvent) {
  if (event.start_time === null) return 'All day'
  const start = formatTime(event.start_time)
  return event.end_time === null
    ? start
    : `${start} – ${formatTime(event.end_time)}`
}

export function dashboardAudience(event: DashboardCalendarEvent) {
  return event.age_groups.length === 0
    ? 'All academy'
    : event.age_groups.join(', ')
}

export function dashboardParticipantLabel(match: DashboardMatch) {
  const participants = match.participants
  if (participants.kind === 'internal') {
    return `${participants.home_team.name} vs ${participants.away_team.name}`
  }
  return participants.academy_side === 'home'
    ? `${participants.academy_team.name} vs ${participants.opponent_name}`
    : `${participants.opponent_name} vs ${participants.academy_team.name}`
}

export function titleCase(value: string) {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`
}
