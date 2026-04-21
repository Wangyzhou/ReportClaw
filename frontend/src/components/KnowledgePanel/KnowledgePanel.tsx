import { useState, useEffect, useCallback, useRef } from 'react'
import styles from './KnowledgePanel.module.css'
import { CategoryTabs } from './CategoryTabs'
import { DocumentList } from './DocumentList'
import { UploadButton } from './UploadButton'
import { SearchBar } from './SearchBar'
import { SearchResults } from './SearchResults'
import { fetchDocuments, uploadDocument, deleteDocument, searchKnowledge } from '../../services/api'
import type { KnowledgeCategory, KnowledgeDocument, ChunkResult } from '../../types'

const categories: KnowledgeCategory[] = [
  { id: '政策法规', label: '政策法规', icon: '📜' },
  { id: '行业报告', label: '行业报告', icon: '📊' },
  { id: '历史报告', label: '历史报告', icon: '📁' },
  { id: '媒体资讯', label: '媒体资讯', icon: '📰' },
]

interface Props {
  onDocumentsChange?: (docs: KnowledgeDocument[]) => void
  focusDocId?: string
  focusCategory?: string
}

export function KnowledgePanel({ onDocumentsChange, focusDocId, focusCategory }: Props = {}) {
  const [activeCategory, setActiveCategory] = useState(categories[0].id)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [searchMode, setSearchMode] = useState(false)
  const [searchResults, setSearchResults] = useState<ChunkResult[]>([])
  const [searching, setSearching] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval>>()

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

  useEffect(() => {
    onDocumentsChange?.(documents)
  }, [documents, onDocumentsChange])

  useEffect(() => {
    if (focusDocId && focusCategory) setActiveCategory(focusCategory)
  }, [focusDocId, focusCategory])

  useEffect(() => {
    if (!focusDocId) return
    const el = document.getElementById(`doc-${focusDocId}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [documents, focusDocId])

  const hasParsing = documents.some(d => d.status === 'parsing')

  useEffect(() => {
    if (!hasParsing) return
    const category = activeCategory
    pollingRef.current = setInterval(async () => {
      try {
        const docs = await fetchDocuments(category)
        setDocuments(docs)
        if (!docs.some(d => d.status === 'parsing')) {
          clearInterval(pollingRef.current)
        }
      } catch { /* ignore polling errors */ }
    }, 3000)
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [hasParsing, activeCategory])

  const showError = (msg: string) => {
    setErrorMessage(msg)
    setTimeout(() => setErrorMessage(''), 3000)
  }

  const handleUpload = async (file: File) => {
    try {
      await uploadDocument(activeCategory, file)
      loadDocuments()
    } catch (e) {
      showError(e instanceof Error ? e.message : '上传失败')
    }
  }

  const handleDelete = async (documentId: string) => {
    const doc = documents.find(d => d.id === documentId)
    if (!window.confirm(`确认删除「${doc?.name || documentId}」？`)) return
    try {
      await deleteDocument(activeCategory, documentId)
      loadDocuments()
    } catch (e) {
      showError(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleSearch = async (query: string) => {
    setSearchMode(true)
    setSearching(true)
    try {
      const resp = await searchKnowledge({
        question: query,
        categories: [activeCategory],
        topK: 5,
      })
      setSearchResults(resp.chunks)
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleClearSearch = () => {
    setSearchMode(false)
    setSearchResults([])
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
        onChange={(id) => { setActiveCategory(id); handleClearSearch() }}
      />

      <SearchBar onSearch={handleSearch} onClear={handleClearSearch} />

      {errorMessage && <div className={styles.errorToast}>{errorMessage}</div>}

      <div className={styles.listArea}>
        {searchMode ? (
          <SearchResults chunks={searchResults} loading={searching} />
        ) : loading ? (
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
