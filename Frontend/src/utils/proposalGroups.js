/**
 * AI 任务提案按天分组。
 *
 * 分组用的是条目的 group（"已提交的日期"），不是输入框实时绑定的 date：
 * 日期输入框每敲一个数字就会更新 date，如果直接按 date 分组，条目会立刻跳到别的组、输入框被重建，
 * 正在输入的"2"就变成了"02"，没法从容输入"28"。所以编辑中只改 date，失焦 / 回车后再把 group 同步过来。
 * 组内保持原来的顺序，改时间、时长时条目也不会跳动。
 */
export const groupKey = (t) => (t.group !== undefined ? t.group : t.date)

export function groupTasksByDate(items) {
  const order = new Map(items.map((t, i) => [t.key, i]))
  const map = new Map()
  const sorted = [...items].sort((a, b) => String(groupKey(a)).localeCompare(String(groupKey(b))) || order.get(a.key) - order.get(b.key))
  for (const t of sorted) {
    const key = groupKey(t)
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(t)
  }
  return [...map.entries()].map(([date, list]) => ({
    date,
    items: list,
    minutes: list.reduce((s, t) => s + Number(t.duration_minutes || 0), 0),
  }))
}

/** 失焦 / 回车 / 选择后提交日期：日期合法才重新分组，返回是否换了组。 */
export function commitDate(t) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(t.date || ''))) return false
  const moved = t.group !== t.date
  t.group = t.date
  return moved
}
