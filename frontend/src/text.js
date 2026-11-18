// 纯前端的文本小工具：只做字符串处理，不产生任何「模型结论」。
// 两个用途：
//   1. 命中高亮——检索结果里标出与查询重合的词，并统计重合词数；
//   2. 差异高亮——模型挑战里并排展示原句与改写句的增删，方便肉眼看出改了哪个词。

const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'of', 'to', 'in', 'on', 'for', 'with', 'is', 'are',
  'was', 'were', 'be', 'been', 'it', 'its', 'this', 'that', 'these', 'those', 'as', 'at',
  'by', 'from', 'so', 'if', 'then', 'than', 'too', 'very', 'not', 'no', 'do', 'does', 'did',
  'i', 'you', 'he', 'she', 'we', 'they', 'my', 'your', 'his', 'her', 'their', 'there',
])

/** 把文本切成「词」与「非词」两种片段，顺序保留，便于逐段渲染。 */
function splitSegments(text) {
  return String(text ?? '').match(/[A-Za-z0-9']+|[^A-Za-z0-9']+/g) || []
}

function normalize(word) {
  return word.toLowerCase().replace(/^'+|'+$/g, '')
}

/**
 * 命中高亮：把文本切成片段，标出与查询重合的实词。
 * 返回 { segments: [{ text, hit }], hits: ['actors', 'story'] }
 */
export function highlightSegments(text, query) {
  const terms = new Set(
    (String(query ?? '').toLowerCase().match(/[a-z0-9']+/g) || [])
      .map((word) => word.replace(/^'+|'+$/g, ''))
      .filter((word) => word.length > 2 && !STOPWORDS.has(word))
  )

  const found = new Set()
  const segments = splitSegments(text).map((part) => {
    const isWord = /^[A-Za-z0-9']/.test(part)
    const key = isWord ? normalize(part) : ''
    const hit = Boolean(key) && terms.has(key)
    if (hit) found.add(key)
    return { text: part, hit }
  })

  return { segments, hits: [...found] }
}

/**
 * 词级差异：用 LCS 找出两个句子共同的词，其余分别是删除/新增。
 * 返回 { left, right }，两边都是 [{ text, kind }]，kind 为 same / del / add。
 */
export function diffWords(original, rewritten) {
  const left = String(original ?? '').split(/(\s+)/).filter(Boolean)
  const right = String(rewritten ?? '').split(/(\s+)/).filter(Boolean)

  const a = left.filter((token) => token.trim())
  const b = right.filter((token) => token.trim())

  // LCS 长度表
  const dp = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      dp[i][j] =
        normalize(a[i]) === normalize(b[j])
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const leftParts = []
  const rightParts = []
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (normalize(a[i]) === normalize(b[j])) {
      leftParts.push({ text: a[i], kind: 'same' })
      rightParts.push({ text: b[j], kind: 'same' })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      leftParts.push({ text: a[i], kind: 'del' })
      i += 1
    } else {
      rightParts.push({ text: b[j], kind: 'add' })
      j += 1
    }
  }
  while (i < a.length) {
    leftParts.push({ text: a[i], kind: 'del' })
    i += 1
  }
  while (j < b.length) {
    rightParts.push({ text: b[j], kind: 'add' })
    j += 1
  }

  return { left: leftParts, right: rightParts }
}

/** 转义 HTML 特殊字符：v-html 的输入必须先过这一步。 */
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * 把差异片段渲染成安全的 HTML 字符串（词先转义，再套高亮标签）。
 * 只给「模型挑战」页并排对比用，样式在 style.css 的 .diff-add / .diff-del。
 */
export function renderDiffHtml(parts) {
  return parts
    .map((part) => {
      const text = escapeHtml(part.text)
      if (part.kind === 'same') return text
      return `<span class="${part.kind === 'add' ? 'diff-add' : 'diff-del'}">${text}</span>`
    })
    .join(' ')
}
