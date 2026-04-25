import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

function findVueFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  const vueFiles = []

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      vueFiles.push(...findVueFiles(fullPath))
      continue
    }
    if (entry.isFile() && entry.name.endsWith('.vue')) {
      vueFiles.push(fullPath)
    }
  }

  return vueFiles
}

function findSelectionTablesMissingRowKey(content) {
  const tableBlocks = [...content.matchAll(/<el-table\b[\s\S]*?<\/el-table>/g)]
  return tableBlocks.filter((tableBlock) => {
    const tableTemplate = tableBlock[0]
    if (!tableTemplate.includes('reserve-selection')) {
      return false
    }

    const openingTagMatch = tableTemplate.match(/<el-table\b([\s\S]*?)>/)
    const openingTag = openingTagMatch?.[1] || ''
    return !/row-key\s*=/.test(openingTag)
  }).length
}

describe('Element Plus selection table contract', () => {
  it('requires row-key for every table using reserve-selection', () => {
    const componentsRoot = path.resolve(__dirname, '../..')
    const vueFiles = findVueFiles(componentsRoot)
    const offenders = []

    for (const filePath of vueFiles) {
      const content = fs.readFileSync(filePath, 'utf8')
      const missingCount = findSelectionTablesMissingRowKey(content)
      if (missingCount > 0) {
        offenders.push(path.relative(componentsRoot, filePath))
      }
    }

    expect(offenders).toEqual([])
  })
})
