import { runOpenApiTypeGeneration } from './openapi-typescript-runner.mjs'

runOpenApiTypeGeneration({
  exporterScript: 'scripts/export_role_aware_dashboard_openapi.py',
  generatedPath: 'src/features/dashboard/api/generated.ts',
  temporaryPrefix: 'vkca-role-aware-dashboard-openapi-',
  contractLabel: 'Role-aware dashboard',
  generateCommand: 'npm run generate:role-aware-dashboard-types',
})
