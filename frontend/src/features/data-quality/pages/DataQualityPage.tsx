import { useState } from 'react'
import { useNavigate } from 'react-router'
import SuccessToast from '@shared/components/feedback/SuccessToast'
import Pagination from '@shared/components/navigation/Pagination'
import DataQualityFilters from '../components/DataQualityFilters'
import DataQualityFindingList from '../components/DataQualityFindingList'
import DataQualityRemediationDialog from '../components/DataQualityRemediationDialog'
import DataQualitySummary from '../components/DataQualitySummary'
import {
  DataQualityEmptyState,
  DataQualityErrorState,
  DataQualityLoadingState,
} from '../components/DataQualityStates'
import useDataQuality from '../hooks/useDataQuality'
import useSuccessToast from '@shared/hooks/useSuccessToast'
import type { DataQualityFinding } from '../api/dataQualityApi'
import type { DataQualityWorkflowPath } from '../types/dataQuality'

function resultStatus(totalFindings: number) {
  return `${totalFindings} ${totalFindings === 1 ? 'finding' : 'findings'} shown`
}

function liveStatus({
  errorMessage,
  navigationStatus,
  totalFindings,
  requestState,
}: {
  errorMessage: string | null
  navigationStatus: string
  totalFindings: number | null
  requestState: 'idle' | 'loading' | 'refreshing' | 'success' | 'error'
}) {
  if (navigationStatus !== '') return navigationStatus
  if (requestState === 'loading') return 'Loading current academy health'
  if (requestState === 'refreshing') {
    return 'Updating current academy health. Previous results remain available.'
  }
  if (errorMessage !== null) {
    return totalFindings === null
      ? 'Unable to load current academy health. Select Retry to try again.'
      : 'Unable to refresh current academy health. Previous results remain available.'
  }
  return totalFindings === null
    ? 'Loading current academy health'
    : resultStatus(totalFindings)
}

export default function DataQualityPage() {
  const navigate = useNavigate()
  const [navigationStatus, setNavigationStatus] = useState('')
  const [selectedFinding, setSelectedFinding] =
    useState<DataQualityFinding | null>(null)
  const { dismissSuccessToast, showSuccessToast, successToast } = useSuccessToast()
  const {
    clearFilters,
    errorMessage,
    filters,
    handleFilterChange,
    handlePageChange,
    isFetching,
    remediate,
    remediationMessage,
    remediationState,
    resetRemediation,
    result,
    requestState,
    retry,
  } = useDataQuality()
  const showLoading = result === null && isFetching
  const filtered = Object.values(filters).some((value) => value !== undefined)

  function handleNavigate(path: DataQualityWorkflowPath, label: string) {
    setNavigationStatus(`Opening ${label} in the current workflow.`)
    navigate(path)
  }

  function handleOpenRemediation(finding: DataQualityFinding) {
    resetRemediation()
    setSelectedFinding(finding)
  }

  function handleCloseRemediation() {
    if (remediationState === 'submitting') return
    resetRemediation()
    setSelectedFinding(null)
  }

  async function handleConfirmRemediation() {
    if (selectedFinding === null) return
    const attempt = await remediate(selectedFinding)
    if (attempt.outcome === 'applied' && attempt.result !== undefined) {
      showSuccessToast(attempt.result.message)
      setSelectedFinding(null)
    } else if (attempt.outcome === 'conflict') {
      setSelectedFinding(null)
    }
  }

  return (
    <section className="data-quality-page mx-auto min-w-0 w-full max-w-7xl">
      <header className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Data Quality
        </h1>
        <p className="mt-2 max-w-2xl text-base leading-6 text-slate-600">
          Review current academy records and take the next safe step in the
          relevant workflow.
        </p>
      </header>
      {successToast !== null ? (
        <SuccessToast
          key={successToast.id}
          message={successToast.message}
          onDismiss={dismissSuccessToast}
        />
      ) : null}
      {remediationState === 'conflict' && remediationMessage !== null ? (
        <div
          role="alert"
          className="mb-4 flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm font-semibold text-amber-950 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>{remediationMessage}</span>
          <button
            type="button"
            className="min-h-11 shrink-0 rounded-lg border border-amber-700 bg-white px-4 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
            onClick={resetRemediation}
          >
            Dismiss
          </button>
        </div>
      ) : null}
      {result !== null ? <DataQualitySummary summary={result.summary} /> : null}
      <DataQualityFilters
        filters={filters}
        onChange={handleFilterChange}
        onClear={clearFilters}
      />
      <p role="status" aria-atomic="true" aria-live="polite" className="sr-only">
        {liveStatus({
          errorMessage,
          navigationStatus,
          totalFindings: result?.total_findings ?? null,
          requestState,
        })}
      </p>
      <div
        aria-busy={isFetching}
        aria-label="Data quality results"
        className="mt-6 min-w-0"
      >
        {errorMessage ? (
          <DataQualityErrorState
            hasRetainedResults={result !== null}
            message={errorMessage}
            onRetry={retry}
          />
        ) : null}
        {showLoading ? <DataQualityLoadingState /> : null}
        {result !== null && result.findings.length === 0 ? (
          <DataQualityEmptyState filtered={filtered} />
        ) : null}
        {result !== null && result.findings.length > 0 ? (
          <DataQualityFindingList
            findings={result.findings}
            onNavigate={handleNavigate}
            onRemediate={handleOpenRemediation}
          />
        ) : null}
        {result !== null && result.total_pages > 1 ? (
          <div className="mt-6">
            <Pagination
              ariaLabel="Data Quality pages"
              page={result.page}
              totalPages={result.total_pages}
              isLoading={isFetching}
              onPageChange={handlePageChange}
            />
          </div>
        ) : null}
      </div>
      {selectedFinding !== null ? (
        <DataQualityRemediationDialog
          errorMessage={
            remediationState === 'error' ? remediationMessage : null
          }
          finding={selectedFinding}
          isSubmitting={remediationState === 'submitting'}
          onClose={handleCloseRemediation}
          onConfirm={() => void handleConfirmRemediation()}
        />
      ) : null}
    </section>
  )
}
