import styles from './DeliveryPanel.module.css'
import { ReportPreview } from './ReportPreview'
import { VersionList } from './VersionList'
import { ExportButtons } from './ExportButtons'
import { TaskTreePanel } from './TaskTreePanel'
import { reportVersions, sampleReport } from '../../mocks/reports'

export function DeliveryPanel() {
  return (
    <aside className={styles.panel}>
      <div className={styles.taskArea}>
        <TaskTreePanel />
      </div>

      <div className={styles.reportArea}>
        <header className={styles.header}>
          <span className={styles.label}>交付区</span>
          <h2 className={styles.title}>报告预览</h2>
        </header>

        <div className={styles.previewArea}>
          <ReportPreview markdown={sampleReport} />
        </div>

        <div className={styles.bottomArea}>
          <VersionList versions={reportVersions} />
          <ExportButtons />
        </div>
      </div>
    </aside>
  )
}
