import { runOpenApiTypeGeneration } from './openapi-typescript-runner.mjs'

runOpenApiTypeGeneration({
  exporterScript: 'scripts/export_data_quality_openapi.py',
  generatedPath: 'src/features/data-quality/api/generated.ts',
  temporaryPrefix: 'vkca-data-quality-openapi-',
  contractLabel: 'Data Quality',
  generateCommand: 'npm run generate:data-quality-types',
})
