import type { EventType } from '../types/calendar'

interface CalendarEventIconProps {
  eventType: EventType
  className?: string
}

export default function CalendarEventIcon({
  eventType,
  className = 'size-4',
}: CalendarEventIconProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      data-event-type={eventType}
      fill="none"
      viewBox="0 0 24 24"
    >
      {eventType === 'practice' ? (
        <path
          d="M5 19h14M7 16l5-10 5 10M9 13h6"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      ) : null}
      {eventType === 'game' ? (
        <path
          d="M12 4 19 8v8l-7 4-7-4V8l7-4Zm0 0v16m-7-12 7 4 7-4"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      ) : null}
      {eventType === 'miscellaneous' ? (
        <path
          d="M6 5h12v14H6zM9 9h6M9 13h6M9 17h3"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      ) : null}
    </svg>
  )
}
