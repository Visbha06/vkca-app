import { runOpenApiTypeGeneration } from './openapi-typescript-runner.mjs'

runOpenApiTypeGeneration({
  exporterScript: 'scripts/export_business_audit_openapi.py',
  generatedPath: 'src/features/audit/api/generated.ts',
  temporaryPrefix: 'vkca-business-audit-openapi-',
  contractLabel: 'Business Audit',
  generateCommand: 'npm run generate:business-audit-types',
})
