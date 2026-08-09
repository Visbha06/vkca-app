// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import useDataQuality from './useDataQuality'
import { fetchDataQuality } from '../api/dataQualityApi'

vi.mock('../api/dataQualityApi', () => ({ fetchDataQuality: vi.fn() }))

const response = {
  findings: [],
  summary: { total_findings: 2, critical_count: 0, warning_count: 2, info_count: 0, domain_counts: { players: 2, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
  page: 1, page_size: 20, total_findings: 0, total_pages: 0, has_previous: false, has_next: false,
}

describe('useDataQuality', () => {
  it('serializes filters, resets to the first page, and retains global summary data', async () => {
    vi.mocked(fetchDataQuality).mockResolvedValue(response)
    const { result } = renderHook(() => useDataQuality())
    await waitFor(() => expect(result.current.result).not.toBeNull())

    act(() => result.current.handlePageChange(2))
    await waitFor(() => expect(fetchDataQuality).toHaveBeenLastCalledWith({ page: 2, pageSize: 20 }, expect.any(AbortSignal)))
    act(() => result.current.handleFilterChange('severity', 'warning'))

    await waitFor(() => expect(fetchDataQuality).toHaveBeenLastCalledWith({ page: 1, pageSize: 20, severity: 'warning' }, expect.any(AbortSignal)))
    expect(result.current.result?.summary.total_findings).toBe(2)
  })
})
