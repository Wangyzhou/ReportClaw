import { useState, useEffect, useCallback } from 'react'
import styles from './KnowledgePanel.module.css'
import { CategoryTabs } from './CategoryTabs'
import { DocumentList } from './DocumentList'
import { UploadButton } from './UploadButton'
import { fetchDocuments, uploadDocument, deleteDocument } from '../../services/api'
import type { KnowledgeCategory, KnowledgeDocument } from '../../types'

const categories: KnowledgeCategory[] = [
  { id: '政策法规', label: '政策法规', icon: '📜' },
  { id: '行业报告', label: '行业报告', icon: '📊' },
  { id: '历史报告', label: '历史报告', icon: '📁' },
  { id: '媒体资讯', label: '媒体资讯', icon: '📰' },
]

export function KnowledgePanel() {
  const [activeCategory, setActiveCategory] = useState(categories[0].id)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [loading, setLoading] = useState(false)

  const loadDocuments = useCallback(async () => {
    setLoading(true)
    try {
      const docs = await fetchDocuments(activeCategory)
      setDocuments(docs)
    } catch {
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [activeCategory])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  const handleUpload = async (file: File) => {
    await uploadDocument(activeCategory, file)
    loadDocuments()
  }

  const handleDelete = async (documentId: string) => {
    await deleteDocument(activeCategory, documentId)
    loadDocuments()
  }

  return (
    <aside className={styles.panel}>
      <header className={styles.header}>
        <span className={styles.label}>知识库</span>
        <h2 className={styles.title}>文档管理</h2>
      </header>

      <CategoryTabs
        categories={categories}
        active={activeCategory}
        onChange={setActiveCategory}
      />

      <div className={styles.listArea}>
        {loading ? (
          <p className={styles.empty}>加载中...</p>
        ) : (
          <DocumentList documents={documents} onDelete={handleDelete} />
        )}
      </div>

      <div className={styles.footer}>
        <UploadButton onUpload={handleUpload} />
      </div>
    </aside>
  )
}
