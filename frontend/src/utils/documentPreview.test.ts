import { describe, expect, it } from 'vitest'
import { createOriginalPreviewBlob } from './documentPreview'

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
    reader.readAsText(blob, 'utf-8')
  })
}

describe('createOriginalPreviewBlob', () => {
  it('normalizes text files to an explicit UTF-8 preview', async () => {
    const source = new Blob([new TextEncoder().encode('中文文档')], { type: 'text/markdown' })

    const preview = await createOriginalPreviewBlob(
      { mime_type: 'text/markdown', original_name: '指南.md' },
      source,
    )

    expect(preview.type).toBe('text/plain;charset=utf-8')
    expect(await readBlob(preview)).toBe('中文文档')
  })

  it('preserves binary files', async () => {
    const source = new Blob(['pdf'], { type: 'application/pdf' })

    const preview = await createOriginalPreviewBlob(
      { mime_type: 'application/pdf', original_name: 'guide.pdf' },
      source,
    )

    expect(preview).toBe(source)
  })
})
