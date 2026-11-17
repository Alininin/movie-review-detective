// 极简 Markdown 渲染：只支持本项目用到的 # / ## / ###、无序列表、粗体、行内代码。
// 内容来自后端读取的本地实验结果文件，属于可信来源；仍做 HTML 转义以防万一。
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function inline(text) {
  return escapeHtml(text)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

export function renderMarkdown(markdown) {
  if (!markdown) return ''
  const lines = String(markdown).split(/\r?\n/)
  const output = []
  let inList = false

  const closeList = () => {
    if (inList) {
      output.push('</ul>')
      inList = false
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    if (!line.trim()) {
      closeList()
      continue
    }
    if (line.startsWith('### ')) {
      closeList()
      output.push(`<h3>${inline(line.slice(4))}</h3>`)
      continue
    }
    if (line.startsWith('## ')) {
      closeList()
      output.push(`<h2>${inline(line.slice(3))}</h2>`)
      continue
    }
    if (line.startsWith('# ')) {
      closeList()
      output.push(`<h1>${inline(line.slice(2))}</h1>`)
      continue
    }
    if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        output.push('<ul>')
        inList = true
      }
      output.push(`<li>${inline(line.replace(/^[-*]\s+/, ''))}</li>`)
      continue
    }
    if (/^\|/.test(line)) {
      // 表格在本项目的案例文件里不用；遇到就按普通段落显示，避免样式错乱
      closeList()
      output.push(`<p class="small mono">${inline(line)}</p>`)
      continue
    }
    closeList()
    output.push(`<p>${inline(line)}</p>`)
  }
  closeList()
  return output.join('\n')
}
