export interface Session {
  key: string
  label: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  timestamp: Date
}

export interface ActivityEvent {
  type: string
  kind?: string
  stream?: string
  name?: string
  title?: string
  phase?: string
  status?: string
  text?: string
  toolCallId?: string
  itemId?: string
  raw?: unknown
}

export interface InlineActivity extends ActivityEvent {
  key: string
}

export type ConnectionStatus = 'idle' | 'connected' | 'streaming' | 'error'

export interface KnowledgeCategory {
  id: string
  label: string
  icon: string
}

export interface KnowledgeDocument {
  id: string
  name: string
  category: string
  datasetId: string
  size: number
  status: string
  chunkCount: number
  tokenCount: number
  createdAt: string
}

export interface UploadResult {
  documentId: string
  name: string
  datasetId: string
  status: string
}

export interface ReportVersion {
  id: string
  version: number
  createdAt: string
  wordCount: number
  status: 'draft' | 'reviewed' | 'final'
}

export interface StreamEvent {
  type: string
  runId?: string
  delta?: string
  text?: string
  [key: string]: unknown
}

export interface RetrievalRequest {
  question: string
  categories: string[]
  topK?: number
}

export interface ChunkResult {
  chunkId: string
  documentName: string
  content: string
  score: number
  datasetId: string
  documentId: string
}

export interface RetrievalResponse {
  chunks: ChunkResult[]
  total: number
}

export type ChatMode = 'smart' | 'report_gen' | 'report_rewrite'

export interface MentionedDoc {
  id: string
  name: string
  category: string
}

export interface ChatPayload {
  text: string
  mode: ChatMode
  mentionedDocs: MentionedDoc[]
}
