import type { DocumentItem } from '../types'

const textFilePattern = /\.(md|markdown|txt)$/i

function readBlobAsUtf8(source: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
    reader.readAsText(source, 'utf-8')
  })
}

export async function createOriginalPreviewBlob(
  document: Pick<DocumentItem, 'mime_type' | 'original_name'>,
  source: Blob,
): Promise<Blob> {
  const isText = document.mime_type.startsWith('text/') || textFilePattern.test(document.original_name)
  if (!isText) return source
  return new Blob([await readBlobAsUtf8(source)], { type: 'text/plain;charset=utf-8' })
}
