import type { PlayerResponse } from '../../types/player'

interface PlayerInitialsAvatarProps {
  firstName: PlayerResponse['first_name']
  lastName: PlayerResponse['last_name']
  size?: 'card' | 'modal'
}

function firstUsableCharacter(value: string) {
  return Array.from(value.trim())[0]?.toLocaleUpperCase() ?? ''
}

export default function PlayerInitialsAvatar({
  firstName,
  lastName,
  size = 'card',
}: PlayerInitialsAvatarProps) {
  const initials =
    `${firstUsableCharacter(firstName)}${firstUsableCharacter(lastName)}` || '–'

  return (
    <span
      aria-hidden="true"
      className={`flex shrink-0 items-center justify-center rounded-full bg-academy/20 font-bold text-slate-900 ${
        size === 'modal' ? 'size-14 text-lg' : 'size-11 text-sm'
      }`}
    >
      {initials}
    </span>
  )
}
