import type { KnowledgeDocument } from '../../types'
import styles from './KnowledgePanel.module.css'

interface Props {
  documents: KnowledgeDocument[]
  onDelete: (documentId: string) => void
}

const statusLabels: Record<string, string> = {
  ready: '就绪',
  parsing: '解析中',
  uploading: '上传中',
  error: '异常',
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentList({ documents, onDelete }: Props) {
  if (!documents.length) {
    return <p className={styles.empty}>该分类下暂无文档</p>
  }

  return (
    <ul className={styles.docList}>
      {documents.map(doc => (
        <li key={doc.id} id={`doc-${doc.id}`} className={styles.docItem}>
          <div className={styles.docName}>{doc.name}</div>
          <div className={styles.docMeta}>
            <span>{formatSize(doc.size)}</span>
            {doc.chunkCount > 0 && <span>{doc.chunkCount} 块</span>}
            <span className={`${styles.docStatus} ${styles[`status_${doc.status}`]}`}>
              {statusLabels[doc.status] ?? doc.status}
            </span>
            <button
              className={styles.deleteBtn}
              onClick={() => onDelete(doc.id)}
              title="删除文档"
            >
              ×
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}
