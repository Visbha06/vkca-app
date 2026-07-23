import { useState } from 'react'
import type { PlayerResponse } from '../types/player'
import AddPlayerModal from './AddPlayerModal'
import EditPlayerModal from './EditPlayerModal'
import PlayerDetailsModal from './PlayerDetailsModal'

interface PlayersPageModalsProps {
  canManagePlayers: boolean
  isAddPlayerOpen: boolean
  selectedPlayer: PlayerResponse | null
  onAddPlayerClose: () => void
  onPlayerMutation: (
    player: PlayerResponse,
    action: 'added' | 'updated',
  ) => void
  onSelectPlayer: (player: PlayerResponse | null) => void
}

export default function PlayersPageModals({
  canManagePlayers,
  isAddPlayerOpen,
  selectedPlayer,
  onAddPlayerClose,
  onPlayerMutation,
  onSelectPlayer,
}: PlayersPageModalsProps) {
  const [editingPlayer, setEditingPlayer] =
    useState<PlayerResponse | null>(null)

  function handleEdit() {
    if (selectedPlayer === null) return
    setEditingPlayer(selectedPlayer)
    onSelectPlayer(null)
  }

  function handlePlayerUpdated(player: PlayerResponse) {
    onPlayerMutation(player, 'updated')
    onSelectPlayer(player)
  }

  return (
    <>
      {selectedPlayer !== null ? (
        <PlayerDetailsModal
          player={selectedPlayer}
          onClose={() => onSelectPlayer(null)}
          onEdit={canManagePlayers ? handleEdit : undefined}
        />
      ) : null}

      {isAddPlayerOpen ? (
        <AddPlayerModal
          onClose={onAddPlayerClose}
          onCreated={(player) => onPlayerMutation(player, 'added')}
        />
      ) : null}

      {editingPlayer !== null ? (
        <EditPlayerModal
          player={editingPlayer}
          onClose={() => setEditingPlayer(null)}
          onUpdated={handlePlayerUpdated}
        />
      ) : null}
    </>
  )
}
