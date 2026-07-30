import { useCallback, useRef, useState } from 'react'

interface SuccessToastState {
  id: number
  message: string
}

export default function useSuccessToast() {
  const nextToastId = useRef(0)
  const [successToast, setSuccessToast] =
    useState<SuccessToastState | null>(null)

  const showSuccessToast = useCallback((message: string) => {
    nextToastId.current += 1
    setSuccessToast({ id: nextToastId.current, message })
  }, [])

  const dismissSuccessToast = useCallback(() => {
    setSuccessToast(null)
  }, [])

  return {
    dismissSuccessToast,
    showSuccessToast,
    successToast,
  }
}
