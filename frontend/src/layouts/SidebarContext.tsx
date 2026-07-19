import {
  createContext,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'

interface SidebarContextValue {
  expanded: boolean
  mobileOpen: boolean
  toggleExpanded: () => void
  openMobile: () => void
  closeMobile: () => void
}

const SidebarContext = createContext<SidebarContextValue | undefined>(undefined)

export function SidebarProvider({ children }: PropsWithChildren) {
  const [expanded, setExpanded] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)

  const value = useMemo<SidebarContextValue>(
    () => ({
      expanded,
      mobileOpen,
      toggleExpanded: () => setExpanded((isExpanded) => !isExpanded),
      openMobile: () => setMobileOpen(true),
      closeMobile: () => setMobileOpen(false),
    }),
    [expanded, mobileOpen],
  )

  return (
    <SidebarContext.Provider value={value}>
      {children}
    </SidebarContext.Provider>
  )
}

// Context hooks are intentionally colocated with their provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useSidebar() {
  const context = useContext(SidebarContext)

  if (context === undefined) {
    throw new Error('useSidebar must be used within a SidebarProvider')
  }

  return context
}
