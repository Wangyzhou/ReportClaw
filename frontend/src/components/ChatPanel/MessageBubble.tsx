import styles from './ChatPanel.module.css'
import { renderMarkdown } from './markdown'
import type { ChatMessage } from '../../types'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const time = message.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  return (
    <article className={`${styles.messageRow} ${styles[message.role]}`}>
      <div className={styles.messageMeta}>
        <span className={styles.messageRole}>{message.role === 'user' ? 'You' : 'Assistant'}</span>
        <span className={styles.messageTime}>{time}</span>
      </div>
      {message.role === 'assistant' ? (
        <div
          className={styles.messageBubble}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(message.text) }}
        />
      ) : (
        <div className={styles.messageBubble}>{message.text}</div>
      )}
    </article>
  )
}
