import academyLogo from '@/assets/placeholderLogo.png'
import { useSidebar } from '../SidebarContext'

export default function SidebarBrand() {
  const { expanded } = useSidebar()

  return (
    <div
      className={`flex min-w-0 flex-1 items-center gap-3 ${
        expanded ? '' : 'md:justify-center md:gap-0'
      }`}
    >
      <img
        src={academyLogo}
        alt=""
        aria-hidden="true"
        className="size-11 shrink-0 rounded-lg bg-white object-cover"
        height="44"
        width="44"
      />
      <div className={`min-w-0 ${expanded ? '' : 'md:hidden'}`}>
        <p className="truncate text-sm font-bold leading-5 text-white">
          VK Cricket Academy
        </p>
        <p className="truncate text-xs leading-5 text-slate-300">
          Academy Portal
        </p>
      </div>
    </div>
  )
}
