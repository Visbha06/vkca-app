import { Outlet } from 'react-router-dom'
import { SidebarProvider, useSidebar } from './SidebarContext'

function AppLayoutShell() {
  const { expanded } = useSidebar()

  return (
    <div className="flex min-h-screen bg-white text-slate-900">
      <aside
        aria-label="Application sidebar"
        className={`shrink-0 bg-academy transition-[width] duration-200 ${
          expanded ? 'w-sidebar-expanded' : 'w-sidebar-collapsed'
        }`}
      />
      <main className="min-w-0 flex-1 bg-slate-50 p-6">
        <Outlet />
      </main>
    </div>
  )
}

export default function AppLayout() {
  return (
    <SidebarProvider>
      <AppLayoutShell />
    </SidebarProvider>
  )
}
