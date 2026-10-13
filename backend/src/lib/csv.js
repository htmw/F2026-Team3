// Minimal RFC 4180 CSV support: quoted fields, escaped quotes, CRLF or LF line endings.

export function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') { field += '"'; i++ }
      else if (char === '"') quoted = false
      else field += char
    } else if (char === '"') quoted = true
    else if (char === ',') { row.push(field); field = '' }
    else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[i + 1] === '\n') i++
      row.push(field); rows.push(row); row = []; field = ''
    } else field += char
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row) }
  const nonEmpty = rows.filter((r) => r.some((cell) => cell.trim() !== ''))
  if (nonEmpty.length === 0) return []
  const headers = nonEmpty[0].map((h) => h.trim().toLowerCase())
  return nonEmpty.slice(1).map((cells) => Object.fromEntries(headers.map((h, i) => [h, (cells[i] ?? '').trim()])))
}

const escape = (value) => {
  const text = value == null ? '' : String(value)
  // Prefix cells that spreadsheet apps would run as formulas.
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe
}

export function toCsv(headers, rows) {
  return [headers.map(escape).join(','), ...rows.map((row) => row.map(escape).join(','))].join('\r\n') + '\r\n'
}
