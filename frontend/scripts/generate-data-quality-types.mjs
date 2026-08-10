import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const frontendDirectory = path.resolve(scriptDirectory, '..')
const backendDirectory = path.resolve(frontendDirectory, '../backend')
const generatedPath = path.join(
  frontendDirectory,
  'src/features/data-quality/api/generated.ts',
)
const checkOnly = process.argv.includes('--check')
const temporaryDirectory = mkdtempSync(
  path.join(tmpdir(), 'vkca-data-quality-openapi-'),
)
const openapiPath = path.join(temporaryDirectory, 'openapi.json')
const candidatePath = checkOnly
  ? path.join(temporaryDirectory, 'generated.ts')
  : generatedPath

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

try {
  run(
    'uv',
    [
      'run',
      'python',
      'scripts/export_data_quality_openapi.py',
      '--output',
      openapiPath,
    ],
    backendDirectory,
  )
  run(
    process.execPath,
    [
      path.join(
        frontendDirectory,
        'node_modules/openapi-typescript/bin/cli.js',
      ),
      openapiPath,
      '--output',
      candidatePath,
    ],
    frontendDirectory,
  )

  if (checkOnly) {
    const committed = readFileSync(generatedPath, 'utf8')
    const candidate = readFileSync(candidatePath, 'utf8')
    if (committed !== candidate) {
      console.error(
        'Data Quality API types have drifted. Run npm run generate:data-quality-types.',
      )
      process.exitCode = 1
    } else {
      console.log('Data Quality API types are current.')
    }
  }
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true })
}
