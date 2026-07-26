import academyLogo from '@/assets/placeholderLogo.png'

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
    <div className="hidden bg-slate-900 px-12 pb-8 pt-12 text-white ring-2 ring-inset ring-academy lg:flex lg:flex-col lg:justify-between">
      <AcademyIdentity />
      <div className="max-w-sm">
        <h2 className="max-w-xs text-4xl font-bold leading-tight tracking-tight text-white">
          One player. One continuous coaching record.
        </h2>
        <p className="mt-5 max-w-xs leading-7 text-slate-300">
          Keep session notes, match performances, and progress in view so every coach can pick up
          where the last session left off.
        </p>

        <div className="mt-8 border-t border-slate-700 pt-5">
          <p className="text-sm font-semibold text-white">Built around academy rhythm</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            U11 batting fundamentals in Lane 3, carried into the next match review.
          </p>
        </div>
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
