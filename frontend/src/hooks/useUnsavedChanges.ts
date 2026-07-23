import { useCallback, useEffect } from 'react'

export const UNSAVED_CHANGES_MESSAGE =
  'You have unsaved changes. Discard them?'

export function useUnsavedChanges(isDirty: boolean, onClose: () => void) {
  useEffect(() => {
    if (!isDirty) return

    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault()
      event.returnValue = ''
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isDirty])

  return useCallback(() => {
    if (isDirty && !window.confirm(UNSAVED_CHANGES_MESSAGE)) return false

    onClose()
    return true
  }, [isDirty, onClose])
}
