import { useState, useCallback, useRef, useMemo, useEffect } from 'react'
import styles from './ChatPanel.module.css'
import type { KnowledgeDocument, ChatPayload } from '../../types'

type ChatMode = 'smart' | 'report_gen' | 'report_rewrite'

const MODES: { id: ChatMode; label: string; prefix: string }[] = [
  { id: 'smart',          label: '智能模式', prefix: '' },
  { id: 'report_gen',     label: '报告生成', prefix: '【报告生成模式】\n' },
  { id: 'report_rewrite', label: '报告改写', prefix: '【报告改写模式】\n' },
]

interface MentionState {
  start: number
  query: string
}

interface Props {
  onSend: (payload: ChatPayload) => void
  disabled: boolean
  documents?: KnowledgeDocument[]
  onMentionClick?: (docId: string, category: string) => void
}

// Parse @mentions from text, return matched docs
function extractMentions(text: string, documents: KnowledgeDocument[]): KnowledgeDocument[] {
  const matches: KnowledgeDocument[] = []
  const pattern = /@([^\s@]+)/g
  let m: RegExpExecArray | null
  while ((m = pattern.exec(text)) !== null) {
    const name = m[1]
    const doc = documents.find(d => d.name === name)
    if (doc && !matches.find(d => d.id === doc.id)) matches.push(doc)
  }
  return matches
}

// Render text with @mentions highlighted (for the overlay)
function renderHighlighted(text: string, documents: KnowledgeDocument[]) {
  const docNames = new Set(documents.map(d => d.name))
  const parts = text.split(/(@[^\s@]+)/g)
  return parts.map((part, i) => {
    if (part.startsWith('@') && docNames.has(part.slice(1))) {
      return <mark key={i} className={styles.mentionToken}>{part}</mark>
    }
    if (part.startsWith('@') && part.length > 1) {
      return <mark key={i} className={styles.mentionTokenPending}>{part}</mark>
    }
    // Replace newlines with <br> for display
    return <span key={i}>{part}</span>
  })
}

export function Composer({ onSend, disabled, documents = [], onMentionClick }: Props) {
  const [text, setText] = useState('')
  const [modeIdx, setModeIdx] = useState(0)
  const [mention, setMention] = useState<MentionState | null>(null)
  const [mentionIdx, setMentionIdx] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const highlightRef = useRef<HTMLDivElement>(null)

  const mode = MODES[modeIdx]

  const filteredDocs = useMemo(() => {
    if (!mention) return []
    const q = mention.query.toLowerCase()
    return documents.filter(d => d.name.toLowerCase().includes(q)).slice(0, 8)
  }, [mention, documents])

  const mentionedDocs = useMemo(() => extractMentions(text, documents), [text, documents])

  const detectMention = (value: string, cursor: number): MentionState | null => {
    const before = value.slice(0, cursor)
    const atIdx = before.lastIndexOf('@')
    if (atIdx === -1) return null
    const query = before.slice(atIdx + 1)
    if (query.includes(' ') || query.includes('\n')) return null
    return { start: atIdx, query }
  }

  // Sync highlight scroll with textarea
  const syncScroll = useCallback(() => {
    if (highlightRef.current && textareaRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop
    }
  }, [])

  // Keep highlight text in sync for newlines
  useEffect(() => {
    if (highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current?.scrollTop ?? 0
    }
  }, [text])

  const insertMention = useCallback((doc: KnowledgeDocument) => {
    if (!mention) return
    const before = text.slice(0, mention.start)
    const after = text.slice(mention.start + 1 + mention.query.length)
    const newText = before + '@' + doc.name + ' ' + after
    setText(newText)
    setMention(null)
    setTimeout(() => {
      const ta = textareaRef.current
      if (ta) {
        const pos = before.length + 1 + doc.name.length + 1
        ta.focus()
        ta.setSelectionRange(pos, pos)
      }
    }, 0)
  }, [text, mention])

  const doSend = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend({
      text: trimmed,
      mode: mode.id,
      mentionedDocs: mentionedDocs.map(d => ({ id: d.id, name: d.name, category: d.category })),
    })
    setText('')
    setMention(null)
  }, [text, disabled, onSend, mode, mentionedDocs])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value
    setText(val)
    const cursor = e.target.selectionStart ?? val.length
    setMention(detectMention(val, cursor))
    setMentionIdx(0)
  }, [])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Tab' && e.shiftKey) {
      e.preventDefault()
      setModeIdx(i => (i + 1) % MODES.length)
      return
    }

    if (mention && filteredDocs.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setMentionIdx(i => Math.min(i + 1, filteredDocs.length - 1)); return }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setMentionIdx(i => Math.max(i - 1, 0)); return }
      if (e.key === 'Enter')     { e.preventDefault(); insertMention(filteredDocs[mentionIdx]); return }
      if (e.key === 'Escape')    { setMention(null); return }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      doSend()
    }
  }, [mention, filteredDocs, mentionIdx, doSend, insertMention])

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    doSend()
  }, [doSend])

  return (
    <form className={styles.composer} onSubmit={handleSubmit}>
      <div className={styles.composerHeader}>
        <button
          type="button"
          className={`${styles.modePill} ${styles['modePill_' + mode.id]}`}
          onClick={() => setModeIdx(i => (i + 1) % MODES.length)}
          title="Shift+Tab 切换模式"
        >
          {mode.label}
        </button>
        <span className={styles.modeTip}>Shift+Tab 切换 · @ 引用文件</span>
      </div>

      <div className={styles.textareaWrap} data-mode={mode.id}>
        {/* Highlight overlay — pointer-events: none, sits behind textarea visually but in front in DOM */}
        <div ref={highlightRef} className={styles.textareaHighlight} aria-hidden>
          {renderHighlighted(text, documents)}
          {/* trailing space prevents last-line collapse */}
          {'\u200b'}
        </div>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onScroll={syncScroll}
          placeholder="输入研究主题，AI 团队将检索 → 写作 → 审查（如：帮我写一份 A 股 AI 算力 Q1 流动性报告）"
          rows={3}
          disabled={disabled}
        />
        {mention && filteredDocs.length > 0 && (
          <ul className={styles.mentionDropdown}>
            {filteredDocs.map((doc, i) => (
              <li
                key={doc.id}
                className={`${styles.mentionItem} ${i === mentionIdx ? styles.mentionItemActive : ''}`}
                onMouseDown={e => { e.preventDefault(); insertMention(doc) }}
                onMouseEnter={() => setMentionIdx(i)}
              >
                <span className={styles.mentionIcon}>📄</span>
                <span className={styles.mentionName}>{doc.name}</span>
                <span className={styles.mentionCat}>{doc.category}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {mentionedDocs.length > 0 && (
        <div className={styles.mentionChips}>
          {mentionedDocs.map(doc => (
            <button
              key={doc.id}
              type="button"
              className={styles.mentionChip}
              onClick={() => onMentionClick?.(doc.id, doc.category)}
              title="点击定位到左侧知识库"
            >
              📄 {doc.name}
            </button>
          ))}
        </div>
      )}

      <div className={styles.composerBar}>
        <span className={styles.composerTip}>Enter 发送，Shift + Enter 换行</span>
        <button className={styles.sendBtn} type="submit" disabled={disabled || !text.trim()}>
          {disabled ? '发送中...' : '发送'}
        </button>
      </div>
    </form>
  )
}
