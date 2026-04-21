import type { KnowledgeCategory } from '../../types'
import styles from './KnowledgePanel.module.css'

interface Props {
  categories: KnowledgeCategory[]
  active: string
  onChange: (id: string) => void
}

export function CategoryTabs({ categories, active, onChange }: Props) {
  return (
    <div className={styles.tabs}>
      {categories.map(cat => (
        <button
          key={cat.id}
          className={`${styles.tab} ${cat.id === active ? styles.tabActive : ''}`}
          onClick={() => onChange(cat.id)}
        >
          <span>{cat.icon}</span>
          <span>{cat.label}</span>
        </button>
      ))}
    </div>
  )
}
