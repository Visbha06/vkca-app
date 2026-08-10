// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DataQualityPage from './DataQualityPage'
import { fetchDataQuality } from '../api/dataQualityApi'

vi.mock('../api/dataQualityApi', () => ({ fetchDataQuality: vi.fn() }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('DataQualityPage', () => {
  it('preserves the summary and findings footprints during initial loading', async () => {
    let resolveInitial!: (value: Awaited<ReturnType<typeof fetchDataQuality>>) => void
    const initial = new Promise<Awaited<ReturnType<typeof fetchDataQuality>>>(
      (resolve) => {
        resolveInitial = resolve
      },
    )
    vi.mocked(fetchDataQuality).mockReturnValue(initial)

    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)

    expect(screen.getByTestId('data-quality-summary-skeleton')).toBeVisible()
    expect(screen.getAllByTestId('data-quality-finding-skeleton')).toHaveLength(2)
    expect(screen.getByLabelText('Finding filters')).toBeVisible()

    resolveInitial({
      findings: [],
      summary: { total_findings: 0, critical_count: 0, warning_count: 0, info_count: 0, domain_counts: { players: 0, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
      page: 1, page_size: 20, total_findings: 0, total_pages: 0, has_previous: false, has_next: false,
    })

    expect(await screen.findByText('No data quality issues found')).toBeVisible()
    expect(screen.queryByTestId('data-quality-summary-skeleton')).not.toBeInTheDocument()
  })

  it('shows the unfiltered summary and a finding explanation', async () => {
    vi.mocked(fetchDataQuality).mockResolvedValue({
      findings: [{ finding_id: 'player.active_unassigned:1', rule_id: 'player.active_unassigned', severity: 'warning', domain: 'players', entity_type: 'player', entity_id: '1', entity_label: 'Asha Patel', title: 'Active player is not assigned to a team', explanation: 'Asha is active but has no roster.', recommended_action: 'Review the player in Teams.', direct_remediation: null, related_entities: [] }],
      summary: { total_findings: 1, critical_count: 0, warning_count: 1, info_count: 0, domain_counts: { players: 1, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
      page: 1, page_size: 20, total_findings: 1, total_pages: 1, has_previous: false, has_next: false,
    })

    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)

    const heading = await screen.findByRole('heading', { name: 'Data Quality' })
    expect(heading).toBeVisible()
    expect(heading).toHaveAttribute('tabindex', '-1')
    expect(screen.getByText('Asha is active but has no roster.')).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('1 finding shown')
  })

  it('shows the explicit healthy state after an empty response', async () => {
    vi.mocked(fetchDataQuality).mockResolvedValue({
      findings: [],
      summary: { total_findings: 0, critical_count: 0, warning_count: 0, info_count: 0, domain_counts: { players: 0, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
      page: 1, page_size: 20, total_findings: 0, total_pages: 0, has_previous: false, has_next: false,
    })

    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)

    expect(await screen.findByText('No data quality issues found')).toBeVisible()
  })

  it('recovers from an initial error through the keyboard-operable retry action', async () => {
    vi.mocked(fetchDataQuality)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({
        findings: [],
        summary: { total_findings: 0, critical_count: 0, warning_count: 0, info_count: 0, domain_counts: { players: 0, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
        page: 1, page_size: 20, total_findings: 0, total_pages: 0, has_previous: false, has_next: false,
      })

    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)

    const retry = await screen.findByRole('button', { name: 'Retry' })
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Unable to load data quality. Please try again.',
    )
    expect(screen.getByRole('alert')).not.toHaveTextContent(
      'Unable to refresh data quality',
    )
    expect(retry).toHaveClass('min-h-11', 'focus:ring-2')

    fireEvent.click(retry)

    expect(await screen.findByText('No data quality issues found')).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('0 findings shown')
  })

  it('retains findings and announces an updating state when a refresh fails', async () => {
    let rejectRefresh!: (reason?: unknown) => void
    const refresh = new Promise<never>((_, reject) => {
      rejectRefresh = reject
    })
    vi.mocked(fetchDataQuality)
      .mockResolvedValueOnce({
        findings: [{ finding_id: 'player.active_unassigned:1', rule_id: 'player.active_unassigned', severity: 'warning', domain: 'players', entity_type: 'player', entity_id: '1', entity_label: 'Asha Patel', title: 'Active player is not assigned to a team', explanation: 'Asha is active but has no roster.', recommended_action: 'Review the player in Teams.', direct_remediation: null, related_entities: [] }],
        summary: { total_findings: 1, critical_count: 0, warning_count: 1, info_count: 0, domain_counts: { players: 1, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
        page: 1, page_size: 20, total_findings: 1, total_pages: 1, has_previous: false, has_next: false,
      })
      .mockReturnValueOnce(refresh)

    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)
    await screen.findByText('Asha is active but has no roster.')

    fireEvent.change(screen.getByRole('combobox', { name: 'Severity' }), {
      target: { value: 'warning' },
    })

    expect(screen.getByLabelText('Data quality results')).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getByRole('status')).toHaveTextContent('Updating current academy health')
    expect(screen.getByText('Asha is active but has no roster.')).toBeVisible()
    expect(screen.queryByTestId('data-quality-summary-skeleton')).not.toBeInTheDocument()
    expect(
      screen.queryByLabelText('Loading current academy health'),
    ).not.toBeInTheDocument()

    rejectRefresh(new Error('offline'))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to refresh data quality. Please try again. Previous results are still shown.',
    )
    expect(screen.getByRole('alert')).not.toHaveTextContent(
      'Unable to load data quality',
    )
    expect(screen.getByText('Asha is active but has no roster.')).toBeVisible()
  })

  it.each([320, 768, 1440])(
    'keeps filter controls focus-safe at %ipx',
    async (viewportWidth) => {
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        value: viewportWidth,
      })
      vi.mocked(fetchDataQuality).mockResolvedValue({
        findings: [],
        summary: { total_findings: 0, critical_count: 0, warning_count: 0, info_count: 0, domain_counts: { players: 0, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
        page: 1, page_size: 20, total_findings: 0, total_pages: 0, has_previous: false, has_next: false,
      })

      render(<MemoryRouter><DataQualityPage /></MemoryRouter>)
      const severity = await screen.findByRole('combobox', { name: 'Severity' })
      severity.focus()

      expect(severity).toHaveFocus()
      expect(severity).toHaveClass('min-h-11', 'focus:ring-2')
      expect(screen.getByLabelText('Finding filters')).toHaveClass('overflow-hidden')
    },
  )
})
