import type { KnowledgeCategory, KnowledgeDocument } from '../types'

export const categories: KnowledgeCategory[] = [
  { id: '政策法规', label: '政策法规', icon: '📜' },
  { id: '行业报告', label: '行业报告', icon: '📊' },
  { id: '历史报告', label: '历史报告', icon: '📁' },
  { id: '媒体资讯', label: '媒体资讯', icon: '📰' },
]

export const documents: KnowledgeDocument[] = [
  { id: 'd1', name: '2024年互联网行业监管政策汇编.pdf', category: '政策法规', datasetId: '', size: 2457600, status: 'ready', chunkCount: 12, tokenCount: 8500, createdAt: '2026-04-18' },
  { id: 'd2', name: '个人信息保护法实施细则.pdf', category: '政策法规', datasetId: '', size: 1153434, status: 'ready', chunkCount: 8, tokenCount: 5200, createdAt: '2026-04-17' },
]
