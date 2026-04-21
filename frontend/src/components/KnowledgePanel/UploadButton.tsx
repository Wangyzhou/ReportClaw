import { useRef, useState } from 'react'
import styles from './KnowledgePanel.module.css'

interface Props {
  onUpload: (file: File) => Promise<void>
}

export function UploadButton({ onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await onUpload(file)
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.csv"
        style={{ display: 'none' }}
        onChange={handleChange}
      />
      <button
        className={styles.uploadBtn}
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? '上传中...' : '+ 上传文档'}
      </button>
    </>
  )
}
