import { useState } from 'react'
import type { PlayerResponse } from '../types/player'

interface PlayerInformationSectionProps {
  bio: PlayerResponse['bio']
  metadata: PlayerResponse['player_metadata']
}

function formatMetadataValue(value: unknown): string {
  if (typeof value === 'string') return value
  return JSON.stringify(value) ?? String(value)
}

export default function PlayerInformationSection({
  bio,
  metadata,
}: PlayerInformationSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const metadataEntries = Object.entries(metadata)
  const hasBio = Boolean(bio?.trim())
  const hasInformation = hasBio || metadataEntries.length > 0

  return (
    <section className="mt-6 border-t border-slate-200 pt-3">
      <button
        type="button"
        id="player-information-toggle"
        aria-controls="player-information-panel"
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? 'Hide' : 'Show'} bio and metadata`}
        className="flex min-h-11 w-full items-center gap-3 rounded-lg px-2 text-left text-slate-900 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        onClick={() => setIsExpanded((expanded) => !expanded)}
      >
        <svg
          aria-hidden="true"
          className="size-5 shrink-0 text-academy"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
          <path
            d="M12 11v6m0-10h.01"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2"
          />
        </svg>
        <span className="flex-1 font-bold">Bio &amp; additional information</span>
        <svg
          aria-hidden="true"
          className={`size-5 shrink-0 text-slate-500 transition-transform motion-reduce:transition-none ${
            isExpanded ? 'rotate-180' : ''
          }`}
          fill="none"
          viewBox="0 0 24 24"
        >
          <path
            d="m6 9 6 6 6-6"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
          />
        </svg>
      </button>

      {isExpanded ? (
        <div
          id="player-information-panel"
          role="region"
          aria-labelledby="player-information-toggle"
          className="px-2 pb-2 pt-4"
        >
          {hasInformation ? (
            <div className="space-y-5">
              {hasBio ? (
                <div>
                  <h3 className="text-sm font-semibold text-slate-600">Biography</h3>
                  <p className="mt-2 max-w-prose whitespace-pre-wrap text-base leading-6 text-slate-900">
                    {bio}
                  </p>
                </div>
              ) : null}

              {metadataEntries.length > 0 ? (
                <div>
                  <h3 className="text-sm font-semibold text-slate-600">
                    Additional information
                  </h3>
                  <dl className="mt-2 divide-y divide-slate-200">
                    {metadataEntries.map(([key, value]) => (
                      <div
                        key={key}
                        className="grid gap-1 py-3 first:pt-0 sm:grid-cols-2 sm:gap-4"
                      >
                        <dt className="break-words text-sm font-semibold text-slate-700">
                          {key}
                        </dt>
                        <dd className="break-words text-sm leading-6 text-slate-900">
                          {formatMetadataValue(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="max-w-prose text-sm leading-6 text-slate-600">
              No bio or additional player information has been added.
            </p>
          )}
        </div>
      ) : null}
    </section>
  )
}
