function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}

export function renderMarkdown(raw: string): string {
  const escaped = escapeHtml(raw)
  let html = escaped

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    return `<pre class="md-code-block"><code${lang ? ` data-lang="${lang}"` : ''}>${code.trim()}</code></pre>`
  })

  html = html.replace(/`([^`\n]+)`/g, '<code class="md-inline-code">$1</code>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\[ref:([^\]]+)\]/g, '<span class="md-ref">[ref:$1]</span>')

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
