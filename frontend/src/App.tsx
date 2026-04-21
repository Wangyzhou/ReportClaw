import { useEffect } from 'react'
import styles from './App.module.css'
import { KnowledgePanel } from './components/KnowledgePanel/KnowledgePanel'
import { ChatPanel } from './components/ChatPanel/ChatPanel'
import { DeliveryPanel } from './components/DeliveryPanel/DeliveryPanel'
import { useChat } from './hooks/useChat'

export default function App() {
  const { state, loadSessions, sendMessage, dispatch } = useChat()

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  const handleSend = async (message: string) => {
    const sessionKey = state.sessions[0]?.key || 'agent:main:main'
    try {
      await sendMessage(message, sessionKey)
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
      <KnowledgePanel />
      <ChatPanel
        messages={state.messages}
        activities={state.activities}
        connection={state.connection}
        connectionBadge={state.connectionBadge}
        currentRunId={state.currentRunId}
        sessions={state.sessions}
        onSend={handleSend}
        onRefreshSessions={loadSessions}
      />
      <DeliveryPanel />
    </div>
  )
}
