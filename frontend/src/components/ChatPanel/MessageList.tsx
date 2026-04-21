import styles from './ChatPanel.module.css'
import { MessageBubble } from './MessageBubble'
import { TaskProgress } from './TaskProgress'
import { useAutoScroll } from '../../hooks/useAutoScroll'
import type { ChatMessage, InlineActivity } from '../../types'

interface Props {
  messages: ChatMessage[]
  activities: InlineActivity[]
  onRefClick?: (chunkId: string) => void
}

export function MessageList({ messages, activities, onRefClick }: Props) {
  const { ref } = useAutoScroll<HTMLDivElement>([messages, activities])

  return (
    <div ref={ref} className={styles.messages}>
      {messages.length === 0 && activities.length === 0 && (
        <div className={styles.emptyState}>
          从这里发问题，工具调用和生命周期事件会内联在对话流里。
        </div>
      )}

      {messages.map((msg, i) => {
        const nextMsg = messages[i + 1]
        const activitiesBetween = !nextMsg
          ? (msg.role === 'user' ? activities : [])
          : []

        return (
          <div key={msg.id}>
            <MessageBubble message={msg} onRefClick={onRefClick} />
            {activitiesBetween.map(act => (
              <TaskProgress key={act.key} activity={act} />
            ))}
          </div>
        )
      })}

      {messages.length > 0 && messages[messages.length - 1]?.role === 'assistant' && activities.length > 0 && (
        <>
          {activities.map(act => (
            <TaskProgress key={act.key} activity={act} />
          ))}
        </>
      )}
    </div>
  )
}
