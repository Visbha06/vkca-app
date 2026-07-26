interface TeamConflictReloadButtonProps {
  isReloading: boolean
  onReload: () => void
}

export default function TeamConflictReloadButton({
  isReloading,
  onReload,
}: TeamConflictReloadButtonProps) {
  return (
    <button
      type="button"
      disabled={isReloading}
      className="mt-3 min-h-11 rounded-lg border border-red-800 bg-white px-4 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-red-400"
      onClick={onReload}
    >
      {isReloading ? 'Reloading team…' : 'Reload latest team'}
    </button>
  )
}
