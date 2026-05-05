import { useState, useEffect, useCallback } from 'react'
import styles from './App.module.css'
import { KnowledgePanel } from './components/KnowledgePanel/KnowledgePanel'
import { ChatPanel } from './components/ChatPanel/ChatPanel'
import { DeliveryPanel } from './components/DeliveryPanel/DeliveryPanel'
import { ChunkDrawer } from './components/KnowledgePanel/ChunkDrawer'
import { useChat } from './hooks/useChat'
import { clearTasks } from './services/api'
import type { KnowledgeDocument, ChatPayload } from './types'

export default function App() {
  const { state, loadSessions, sendMessage, dispatch } = useChat()
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null)
  const [kbDocuments, setKbDocuments] = useState<KnowledgeDocument[]>([])
  const [focusKbDoc, setFocusKbDoc] = useState<{ docId: string; category: string } | null>(null)
  const handleDocumentsChange = useCallback((docs: KnowledgeDocument[]) => {
    setKbDocuments(docs)
  }, [])
  const handleMentionClick = useCallback((docId: string, category: string) => {
    setFocusKbDoc({ docId, category })
  }, [])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  const handleSend = async (payload: ChatPayload) => {
    const sessionKey = state.sessions[0]?.key || 'agent:main:main'
    try {
      await clearTasks()
      await sendMessage(payload, sessionKey)
    } catch (err) {
      dispatch({
        type: 'SET_CONNECTION',
        status: 'error',
        label: '请求失败',
        badge: (err as Error).message,
      })
    }
  }

  return (
    <div className={styles.shell}>
      <KnowledgePanel
        onDocumentsChange={handleDocumentsChange}
        focusDocId={focusKbDoc?.docId}
        focusCategory={focusKbDoc?.category}
      />
      <ChatPanel
        messages={state.messages}
        activities={state.activities}
        connection={state.connection}
        connectionBadge={state.connectionBadge}
        currentRunId={state.currentRunId}
        sessions={state.sessions}
        onSend={handleSend}
        onRefreshSessions={loadSessions}
        onRefClick={setActiveChunkId}
        documents={kbDocuments}
        onMentionClick={handleMentionClick}
        causeChains={state.causeChains}
      />
      <DeliveryPanel />
      <ChunkDrawer chunkId={activeChunkId} onClose={() => setActiveChunkId(null)} />
    </div>
  )
}
