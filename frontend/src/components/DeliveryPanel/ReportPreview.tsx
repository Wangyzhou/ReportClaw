import styles from './DeliveryPanel.module.css'
import { renderMarkdown } from '../ChatPanel/markdown'

interface Props {
  markdown: string
}

export function ReportPreview({ markdown }: Props) {
  return (
    <div
      className={styles.reportContent}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(markdown) }}
    />
  )
}
