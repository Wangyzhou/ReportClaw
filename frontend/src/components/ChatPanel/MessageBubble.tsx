import styles from './ChatPanel.module.css'
import { renderMarkdown } from './markdown'
import type { ChatMessage } from '../../types'

interface Props {
  message: ChatMessage
  onRefClick?: (chunkId: string) => void
}

export function MessageBubble({ message, onRefClick }: Props) {
  const time = message.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (target.classList.contains('md-ref') && target.dataset.chunkId) {
      e.preventDefault()
      onRefClick?.(target.dataset.chunkId)
    }
  }

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
          onClick={handleClick}
        />
      ) : (
        <div className={styles.messageBubble}>{message.text}</div>
      )}
    </article>
  )
}
