/** Request lifecycle state used only by the Data Quality interface. */
export type DataQualityRequestState =
  | 'idle'
  | 'loading'
  | 'refreshing'
  | 'success'
  | 'error'

/** Existing product workflow destinations used by review-only findings. */
export type DataQualityWorkflowPath =
  | '/players'
  | '/teams'
  | '/coaches'
  | '/calendar'
