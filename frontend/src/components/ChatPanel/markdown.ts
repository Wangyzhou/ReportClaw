import type { CauseChain } from '../../types'

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function buildRefTooltip(chunkId: string, chain: CauseChain | undefined): string {
  if (!chain) return `引用: ${chunkId}（cause chain 未传入）`
  const r = chain.retrieval
  const writerCount = chain.writer_uses?.length ?? 0
  const verdict = chain.reviewer_verdict
  const lines = [
    `📚 Retriever 检索：${r.doc_name}` + (r.page ? ` · 第 ${r.page} 页` : ''),
    `   分类: ${r.category} · 相关度: ${r.relevance_score?.toFixed(2) ?? '?'}`,
    `   "${(r.content_preview || '').slice(0, 80)}..."`,
    ``,
    `✍️ Writer 在本报告引用 ${writerCount} 次`,
    ``,
    verdict
      ? `🔍 Reviewer 校验: ${verdict.valid ? '✓ 引用合法' : '✗ 引用失败'}（citation_accuracy: ${(verdict.citation_accuracy_score * 100).toFixed(0)}%）`
      : `🔍 Reviewer: 未审查`,
  ]
  return lines.join('\n')
}

export function renderMarkdown(raw: string, causeChains?: Record<string, CauseChain>): string {
  const escaped = escapeHtml(raw)
  let html = escaped

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    return `<pre class="md-code-block"><code${lang ? ` data-lang="${lang}"` : ''}>${code.trim()}</code></pre>`
  })

  html = html.replace(/`([^`\n]+)`/g, '<code class="md-inline-code">$1</code>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // [ref:chunk_id] → 可 hover 元素，title 显示完整 cause chain
  html = html.replace(/\[ref:([^\]]+)\]/g, (_match, chunkId) => {
    const chain = causeChains?.[chunkId]
    const tooltip = escapeHtml(buildRefTooltip(chunkId, chain))
    const hasChain = chain ? 'has-chain' : 'no-chain'
    return `<a class="md-ref ${hasChain}" data-chunk-id="${chunkId}" href="#" title="${tooltip}">[来源]</a>`
  })

  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h3">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h2">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h1">$1</h2>')

  html = html.replace(/^[-*] (.+)$/gm, '<li class="md-li">$1</li>')
  html = html.replace(/((?:<li class="md-li">.*<\/li>\n?)+)/g, '<ul class="md-ul">$1</ul>')

  html = html.replace(/^\d+\. (.+)$/gm, '<li class="md-oli">$1</li>')
  html = html.replace(/((?:<li class="md-oli">.*<\/li>\n?)+)/g, '<ol class="md-ol">$1</ol>')

  html = html.replace(/\n{2,}/g, '</p><p>')
  html = `<p>${html}</p>`
  html = html.replace(/<p>\s*(<(?:h[2-4]|pre|ul|ol))/g, '$1')
  html = html.replace(/(<\/(?:h[2-4]|pre|ul|ol)>)\s*<\/p>/g, '$1')
  html = html.replace(/<p>\s*<\/p>/g, '')

  return html
}
