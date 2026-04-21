import type { KnowledgeDocument, UploadResult } from '../types'

export async function fetchSessions() {
  const res = await fetch('/api/sessions')
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`)
  return res.json()
}

export async function streamChat(message: string, sessionKey: string) {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, sessionKey }),
  })
  if (!res.ok || !res.body) throw new Error(`Chat stream failed: ${res.status}`)
  return res.body.getReader()
}

export async function fetchDocuments(category: string): Promise<KnowledgeDocument[]> {
  const res = await fetch(`/api/kb/documents?category=${encodeURIComponent(category)}`)
  if (!res.ok) throw new Error(`Failed to fetch documents: ${res.status}`)
  return res.json()
}

export async function uploadDocument(category: string, file: File): Promise<UploadResult> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`/api/kb/upload?category=${encodeURIComponent(category)}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
  return res.json()
}

export async function deleteDocument(category: string, documentId: string): Promise<void> {
  const res = await fetch(`/api/kb/documents/${documentId}?category=${encodeURIComponent(category)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
}

export async function initDatasets(): Promise<Record<string, string>> {
  const res = await fetch('/api/kb/datasets/init', { method: 'POST' })
  if (!res.ok) throw new Error(`Init datasets failed: ${res.status}`)
  return res.json()
}
