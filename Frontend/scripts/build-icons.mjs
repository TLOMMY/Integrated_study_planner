/**
 * 从 lucide 全量图标里裁剪出项目实际用到的子集，生成 src/assets/icons.json。
 * 打包后图标完全离线可用，不依赖 Iconify 在线 API（校园网/断网演示也能正常显示）。
 * 用到不存在的图标名时直接报错，避免页面出现空白图标。
 */
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(import.meta.url)
const lucide = require('@iconify-json/lucide/icons.json')

const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return walk(path)
    return /\.(vue|js)$/.test(name) ? [path] : []
  })

const used = new Set()
for (const file of walk(join(root, 'src'))) {
  for (const match of readFileSync(file, 'utf8').matchAll(/lucide:([a-z0-9-]+)/g)) used.add(match[1])
}

const icons = {}
const aliases = {}
const missing = []
for (const name of [...used].sort()) {
  if (lucide.icons[name]) icons[name] = lucide.icons[name]
  else if (lucide.aliases?.[name]) {
    aliases[name] = lucide.aliases[name]
    const parent = lucide.aliases[name].parent
    icons[parent] = lucide.icons[parent]
  } else missing.push(name)
}

if (missing.length) {
  console.error(`[icons] 未知的 lucide 图标：${missing.join(', ')}`)
  process.exit(1)
}

const subset = { prefix: 'lucide', width: lucide.width, height: lucide.height, icons, aliases }
mkdirSync(join(root, 'src/assets'), { recursive: true })
writeFileSync(join(root, 'src/assets/icons.json'), JSON.stringify(subset))
console.log(`[icons] 已生成 ${Object.keys(icons).length} 个离线图标`)
