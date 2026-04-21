import styles from './DeliveryPanel.module.css'
import type { ReportVersion } from '../../types'

interface Props {
  versions: ReportVersion[]
}

const statusMap: Record<string, { label: string; className: string }> = {
  draft: { label: '草稿', className: styles.statusDraft },
  reviewed: { label: '已审', className: styles.statusReviewed },
  final: { label: '终稿', className: styles.statusFinal },
}

export function VersionList({ versions }: Props) {
  return (
    <ul className={styles.versionList}>
      {versions.map(v => {
        const st = statusMap[v.status] || statusMap.draft
        return (
          <li key={v.id} className={styles.versionItem}>
            <span className={styles.versionTag}>
              v{v.version}
              <span className={`${styles.statusBadge} ${st.className}`}>{st.label}</span>
            </span>
            <span className={styles.versionMeta}>
              <span>{v.wordCount} 字</span>
              <span>{v.createdAt}</span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}
