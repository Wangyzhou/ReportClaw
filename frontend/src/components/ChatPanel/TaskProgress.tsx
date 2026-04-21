import { useState } from 'react'
import styles from './ChatPanel.module.css'
import type { InlineActivity } from '../../types'

interface Props {
  activity: InlineActivity
}

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}

function typeIcon(kind: string): string {
  if (kind === 'tool_result' || kind === 'command-output') return '◁'
  if (kind === 'tool_call' || kind === 'command') return '⚡'
  if (kind === 'assistant') return '💬'
  if (kind === 'lifecycle') return '⟳'
  return '⚡'
}

function typeLabel(kind: string): string {
  switch (kind) {
    case 'tool_call': return 'Tool call'
    case 'tool_result': return 'Tool output'
    case 'command': return 'Tool call'
    case 'command-output': return 'Tool output'
    case 'assistant': return 'Assistant'
    case 'lifecycle': return 'Lifecycle'
    default: return 'Event'
  }
}

function chipVariant(kind: string): string {
  if (kind === 'command' || kind === 'command-output') return styles.chipCommand
  if (kind === 'assistant' || kind === 'assistant-trace') return styles.chipAssistant
  return styles.chipTool
}

export function TaskProgress({ activity }: Props) {
  const [open, setOpen] = useState(false)
  const kind = activity.kind || activity.type

  return (
    <div className={styles.inlineActivity}>
      <details open={open} onToggle={e => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary className={`${styles.activitySummary} ${chipVariant(kind)}`}>
          <span className={styles.activityArrow}>{open ? '▾' : '▸'}</span>
          <span>{typeIcon(kind)}</span>
          <span className={styles.activityLabel}>{typeLabel(kind)}</span>
          <span className={styles.activityKind}>{kind}</span>
          {(activity.name || activity.title) && (
            <span className={styles.activityName}>{activity.name || activity.title}</span>
          )}
          {(activity.status || activity.phase) && (
            <span className={styles.activityStatus}>{activity.status || activity.phase}</span>
          )}
        </summary>
        <div className={styles.activityBody}>
          {activity.toolCallId && (
            <div className={styles.activityField}>
              <span className={styles.fieldLabel}>toolCallId:</span> {activity.toolCallId}
            </div>
          )}
          {activity.phase && activity.status && (
            <div className={styles.activityField}>
              <span className={styles.fieldLabel}>phase:</span> {activity.phase} ·{' '}
              <span className={styles.fieldLabel}>status:</span> {activity.status}
            </div>
          )}
          {activity.text && (
            <pre className={styles.activityLog}>{escapeHtml(activity.text)}</pre>
          )}
          {!activity.toolCallId && !activity.text && (
            <div className={styles.activityField} style={{ color: 'var(--text-dim)' }}>暂无详情</div>
          )}
        </div>
      </details>
    </div>
  )
}
