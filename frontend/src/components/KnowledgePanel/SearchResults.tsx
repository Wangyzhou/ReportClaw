import type { ChunkResult } from '../../types'
import styles from './KnowledgePanel.module.css'

interface Props {
  chunks: ChunkResult[]
  loading: boolean
}

export function SearchResults({ chunks, loading }: Props) {
  if (loading) {
    return <p className={styles.empty}>搜索中...</p>
  }

  if (chunks.length === 0) {
    return <p className={styles.empty}>未找到相关内容</p>
  }

  return (
    <ul className={styles.docList}>
      {chunks.map((chunk, i) => (
        <li key={chunk.chunkId || i} className={styles.chunkItem}>
          <div className={styles.chunkDoc}>{chunk.documentName}</div>
          <div className={styles.chunkContent}>
            {chunk.content.length > 120 ? chunk.content.slice(0, 120) + '...' : chunk.content}
          </div>
          <div className={styles.chunkMeta}>
            <span className={styles.chunkScore}>
              相关度 {Math.round(chunk.score * 100)}%
            </span>
          </div>
        </li>
      ))}
    </ul>
  )
}
