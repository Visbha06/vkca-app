import academyLogo from '../assets/placeholderLogo.png'

function AcademyIdentity({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-center ${compact ? 'gap-3' : 'gap-4'}`}>
      <img
        src={academyLogo}
        alt=""
        aria-hidden="true"
        className={`${compact ? 'size-12' : 'size-16'} rounded-lg bg-white object-cover`}
      />
      <div>
        <p className={`${compact ? '' : 'text-xl'} font-bold text-slate-900 lg:text-white`}>
          VK Cricket Academy
        </p>
        <p className={`mt-1 text-sm ${compact ? 'text-slate-600' : 'text-slate-300'}`}>
          Academy Portal
        </p>
      </div>
    </div>
  )
}

export function DesktopLoginBrand() {
  return (
    <div className="hidden bg-slate-900 p-12 text-white ring-2 ring-inset ring-academy lg:flex lg:flex-col lg:justify-between">
      <AcademyIdentity />
      <div className="max-w-sm">
        <h2 className="text-3xl font-bold tracking-tight text-white">
          Keep the academy moving.
        </h2>
        <p className="mt-4 leading-7 text-slate-300">
          Organize teams, support player development, and stay ready for the next session.
        </p>
      </div>
    </div>
  )
}

export function MobileLoginBrand() {
  return (
    <div className="mb-8 lg:hidden">
      <AcademyIdentity compact />
    </div>
  )
}
