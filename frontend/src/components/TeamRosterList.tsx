import { useState, type DragEvent } from 'react'
import type { TeamRosterSelection } from '../types/team'
import TeamRosterRow from './TeamRosterRow'

interface TeamRosterListProps {
  players: (TeamRosterSelection | null)[]
  disabled: boolean
  onPlayersChange: (players: (TeamRosterSelection | null)[]) => void
  onPlayerInfo: (player: TeamRosterSelection) => void
}

function moveItem<T>(items: T[], fromIndex: number, toIndex: number) {
  const reordered = [...items]
  const [movedItem] = reordered.splice(fromIndex, 1)
  reordered.splice(toIndex, 0, movedItem)
  return reordered
}

export default function TeamRosterList({
  players,
  disabled,
  onPlayersChange,
  onPlayerInfo,
}: TeamRosterListProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)
  const selectedPlayerIds = players.flatMap((player) =>
    player === null ? [] : [player.player_id],
  )
  const lastSelectedIndex = players.reduce(
    (lastIndex, player, index) => (player === null ? lastIndex : index),
    -1,
  )

  function reorder(fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex) return
    onPlayersChange(moveItem(players, fromIndex, toIndex))
  }

  function handleDrop(event: DragEvent<HTMLLIElement>, targetIndex: number) {
    event.preventDefault()
    if (draggedIndex !== null) reorder(draggedIndex, targetIndex)
    setDraggedIndex(null)
  }

  return (
    <ol className="mt-3 border-y border-slate-200">
      {players.map((player, index) => (
        <TeamRosterRow
          key={`${player?.player_id ?? 'empty'}-${index}`}
          index={index}
          player={player}
          selectedPlayerIds={selectedPlayerIds}
          disabled={disabled}
          isDragging={draggedIndex === index}
          isDropTarget={draggedIndex !== null && draggedIndex !== index}
          canMoveUp={player !== null && index > 0}
          canMoveDown={player !== null && index < lastSelectedIndex}
          onChange={(nextPlayer) => {
            const nextPlayers = [...players]
            nextPlayers[index] = nextPlayer
            onPlayersChange(nextPlayers)
          }}
          onDragStart={() => setDraggedIndex(index)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => handleDrop(event, index)}
          onDragEnd={() => setDraggedIndex(null)}
          onMoveUp={() => reorder(index, index - 1)}
          onMoveDown={() => reorder(index, index + 1)}
          onPlayerInfo={onPlayerInfo}
        />
      ))}
    </ol>
  )
}
