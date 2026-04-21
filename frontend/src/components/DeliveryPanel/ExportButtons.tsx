import styles from './DeliveryPanel.module.css'

export function ExportButtons() {
  return (
    <div className={styles.exportRow}>
      <button
        className={styles.exportBtn}
        onClick={() => alert('Word 导出功能即将接入')}
      >
        导出 Word
      </button>
      <button
        className={styles.exportBtn}
        onClick={() => alert('PDF 导出功能即将接入')}
      >
        导出 PDF
      </button>
    </div>
  )
}
