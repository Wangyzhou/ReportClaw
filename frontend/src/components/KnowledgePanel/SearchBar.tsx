import { useState, useRef, useEffect } from 'react'
import styles from './KnowledgePanel.module.css'

interface Props {
  onSearch: (query: string) => void
  onClear: () => void
}

export function SearchBar({ onSearch, onClear }: Props) {
  const [query, setQuery] = useState('')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [])

  const handleChange = (value: string) => {
    setQuery(value)
    if (timerRef.current) clearTimeout(timerRef.current)
    if (!value.trim()) {
      onClear()
      return
    }
    timerRef.current = setTimeout(() => onSearch(value.trim()), 300)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) onSearch(query.trim())
  }

  return (
    <form className={styles.searchBar} onSubmit={handleSubmit}>
      <input
        className={styles.searchInput}
        type="text"
        placeholder="搜索知识库..."
        value={query}
        onChange={e => handleChange(e.target.value)}
      />
      {query && (
        <button
          type="button"
          className={styles.searchClear}
          onClick={() => { setQuery(''); onClear() }}
        >
          ×
        </button>
      )}
    </form>
  )
}
