import { useState, useEffect } from 'react'
import styles from './ChunkDrawer.module.css'
import { lookupChunk } from '../../services/api'
import type { ChunkResult } from '../../types'

interface Props {
  chunkId: string | null
  onClose: () => void
}

export function ChunkDrawer({ chunkId, onClose }: Props) {
  const [chunk, setChunk] = useState<ChunkResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!chunkId) { setChunk(null); return }
    setLoading(true)
    lookupChunk(chunkId)
      .then(setChunk)
      .catch(() => setChunk(null))
      .finally(() => setLoading(false))
  }, [chunkId])

  if (!chunkId) return null

  return (
    <div className={styles.overlay} onClick={onClose}>
      <aside className={styles.drawer} onClick={e => e.stopPropagation()}>
        <header className={styles.drawerHeader}>
          <h3>来源详情</h3>
          <button className={styles.closeBtn} onClick={onClose}>×</button>
        </header>
        <div className={styles.drawerBody}>
          {loading ? (
            <p className={styles.loading}>加载中...</p>
          ) : chunk ? (
            <>
              <div className={styles.field}>
                <label>来源文档</label>
                <span>{chunk.documentName || '未知'}</span>
              </div>
              {chunk.score > 0 && (
                <div className={styles.field}>
                  <label>相关度</label>
                  <span>{Math.round(chunk.score * 100)}%</span>
                </div>
              )}
              <div className={styles.contentArea}>
                <label>内容</label>
                <p>{chunk.content}</p>
              </div>
            </>
          ) : (
            <p className={styles.loading}>无法加载来源内容</p>
          )}
        </div>
      </aside>
    </div>
  )
}
