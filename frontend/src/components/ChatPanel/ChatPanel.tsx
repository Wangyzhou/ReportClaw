import { useState, useCallback } from 'react'
import styles from './ChatPanel.module.css'
import { MessageList } from './MessageList'
import { Composer } from './Composer'
import type { ChatMessage, InlineActivity, ConnectionStatus, Session } from '../../types'

interface Props {
  messages: ChatMessage[]
  activities: InlineActivity[]
  connection: ConnectionStatus
  connectionBadge: string
  currentRunId: string | null
  sessions: Session[]
  onSend: (message: string) => Promise<void>
  onRefreshSessions: () => void
}

export function ChatPanel({
  messages,
  activities,
  connection,
  connectionBadge,
  currentRunId,
  sessions,
  onSend,
  onRefreshSessions,
}: Props) {
  const [sending, setSending] = useState(false)
  const [selectedSession, setSelectedSession] = useState('')

  const activeSession = selectedSession || sessions[0]?.key || 'agent:main:main'

  const handleSend = useCallback(async (text: string) => {
    setSending(true)
    try {
      await onSend(text)
    } finally {
      setSending(false)
    }
  }, [onSend])

  return (
    <section className={styles.panel}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.label}>流式对话</span>
          <h2 className={styles.title}>主对话窗口</h2>
        </div>
        <div className={styles.headerRight}>
          <select
            className={styles.sessionSelect}
            value={activeSession}
            onChange={e => setSelectedSession(e.target.value)}
          >
            {sessions.length === 0 && <option value="">暂无会话</option>}
            {sessions.map(s => (
              <option key={s.key} value={s.key}>{s.label} · {s.key}</option>
            ))}
          </select>
          <button className={styles.refreshBtn} onClick={onRefreshSessions}>刷新</button>
          <span className={`${styles.statusPill} ${styles[connection]}`}>
            {connectionBadge}
          </span>
          {currentRunId && (
            <span className={styles.runMarker}>{currentRunId}</span>
          )}
        </div>
      </header>

      <MessageList messages={messages} activities={activities} />

      <Composer onSend={handleSend} disabled={sending} />
    </section>
  )
}
