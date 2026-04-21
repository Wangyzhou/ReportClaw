import { useState, useCallback } from 'react'
import styles from './ChatPanel.module.css'

interface Props {
  onSend: (message: string) => void
  disabled: boolean
}

export function Composer({ onSend, disabled }: Props) {
  const [text, setText] = useState('')

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
  }, [text, disabled, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const trimmed = text.trim()
      if (trimmed && !disabled) {
        onSend(trimmed)
        setText('')
      }
    }
  }, [text, disabled, onSend])

  return (
    <form className={styles.composer} onSubmit={handleSubmit}>
      <textarea
        className={styles.textarea}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="例如：帮我检索鹿晗关晓彤相关舆情"
        rows={3}
        disabled={disabled}
      />
      <div className={styles.composerBar}>
        <span className={styles.composerTip}>Enter 发送，Shift + Enter 换行</span>
        <button className={styles.sendBtn} type="submit" disabled={disabled || !text.trim()}>
          {disabled ? '发送中...' : '发送'}
        </button>
      </div>
    </form>
  )
}
