import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const frontendDirectory = path.resolve(scriptDirectory, '..')
const backendDirectory = path.resolve(frontendDirectory, '../backend')

class ChildProcessFailure extends Error {
  constructor(exitCode) {
    super(`Child process exited with status ${exitCode}.`)
    this.exitCode = exitCode
  }
}

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) throw new ChildProcessFailure(result.status ?? 1)
}

export function runOpenApiTypeGeneration({
  exporterScript,
  generatedPath: generatedRelativePath,
  temporaryPrefix,
  contractLabel,
  generateCommand,
}) {
  const generatedPath = path.join(frontendDirectory, generatedRelativePath)
  const checkOnly = process.argv.includes('--check')
  const temporaryDirectory = mkdtempSync(
    path.join(tmpdir(), temporaryPrefix),
  )
  const openapiPath = path.join(temporaryDirectory, 'openapi.json')
  const candidatePath = checkOnly
    ? path.join(temporaryDirectory, 'generated.ts')
    : generatedPath

  try {
    run(
      'uv',
      ['run', 'python', exporterScript, '--output', openapiPath],
      backendDirectory,
    )
    run(
      process.execPath,
      [
        path.join(frontendDirectory, 'node_modules/openapi-typescript/bin/cli.js'),
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
          `${contractLabel} API types have drifted. Run ${generateCommand}.`,
        )
        process.exitCode = 1
      } else {
        console.log(`${contractLabel} API types are current.`)
      }
    }
  } catch (error) {
    if (error instanceof ChildProcessFailure) {
      process.exitCode = error.exitCode
      return
    }
    throw error
  } finally {
    rmSync(temporaryDirectory, { recursive: true, force: true })
  }
}
