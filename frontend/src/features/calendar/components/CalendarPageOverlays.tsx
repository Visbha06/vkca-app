import SuccessToast from '@shared/components/feedback/SuccessToast'
import type useCalendarData from '../hooks/useCalendarData'
import type { CalendarDate } from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'
import CalendarDeleteDialog from './CalendarDeleteDialog'
import DayEventsModal from './DayEventsModal'
import EventDetailsModal from './EventDetailsModal'
import EventFormModal from './EventFormModal'

interface CalendarPageOverlaysProps {
  calendar: ReturnType<typeof useCalendarData>
  canManage: boolean
  openedEvent: CalendarEventInstance | null
  formEvent: CalendarEventInstance | 'create' | null
  deleteEvent: CalendarEventInstance | null
  overflow: { date: CalendarDate; events: CalendarEventInstance[] } | null
  successToast: { id: number; message: string } | null
  onCloseDetails: () => void
  onEdit: (event: CalendarEventInstance) => void
  onDelete: (event: CalendarEventInstance) => void
  onCloseForm: () => void
  onCloseDelete: () => void
  onCloseOverflow: () => void
  onSelectEvent: (event: CalendarEventInstance) => void
  onMutationComplete: (message: string) => void
  onEventReloaded: (event: CalendarEventInstance) => void
  onDismissToast: () => void
}

export default function CalendarPageOverlays(props: CalendarPageOverlaysProps) {
  const { calendar } = props
  return (
    <>
      {calendar.selectedInstance !== null || props.openedEvent !== null ? (
        <EventDetailsModal
          event={calendar.selectedInstance ?? props.openedEvent!}
          isLoading={calendar.isDetailLoading}
          errorMessage={calendar.detailError}
          onRetry={calendar.retryDetail}
          onClose={props.onCloseDetails}
          canManage={props.canManage}
          onEdit={props.onEdit}
          onDelete={props.onDelete}
        />
      ) : null}
      {props.formEvent !== null && calendar.academyToday !== null ? (
        <EventFormModal
          academyToday={calendar.academyToday}
          event={props.formEvent === 'create' ? undefined : props.formEvent}
          onClose={props.onCloseForm}
          onSaved={props.onMutationComplete}
          onEventReloaded={props.onEventReloaded}
        />
      ) : null}
      {props.deleteEvent !== null ? (
        <CalendarDeleteDialog event={props.deleteEvent} onClose={props.onCloseDelete} onDeleted={props.onMutationComplete} onEventReloaded={props.onEventReloaded} />
      ) : null}
      {props.overflow !== null ? (
        <DayEventsModal date={props.overflow.date} events={props.overflow.events} onSelectEvent={props.onSelectEvent} onClose={props.onCloseOverflow} />
      ) : null}
      {props.successToast !== null ? (
        <SuccessToast key={props.successToast.id} message={props.successToast.message} onDismiss={props.onDismissToast} />
      ) : null}
    </>
  )
}
