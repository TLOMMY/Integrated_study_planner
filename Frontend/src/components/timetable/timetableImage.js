/**
 * 用 Canvas 2D 自绘当前周课表（不引入任何截图库）。
 * 颜色取自当前主题（themeColor），课程块用课程自己的颜色。
 * 返回 canvas，调用方再 toBlob 导出 PNG。
 */
import { themeColor } from '@/composables/useTheme'

const FONT = '"PingFang SC","HarmonyOS Sans SC","Microsoft YaHei",system-ui,sans-serif'

function roundRect(ctx, x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + w, y, x + w, y + h, radius)
  ctx.arcTo(x + w, y + h, x, y + h, radius)
  ctx.arcTo(x, y + h, x, y, radius)
  ctx.arcTo(x, y, x + w, y, radius)
  ctx.closePath()
}

/** 按宽度折行（中文逐字），最多 maxLines 行，超出加省略号。 */
function wrap(ctx, text, width, maxLines) {
  const lines = []
  let line = ''
  for (const ch of String(text || '')) {
    if (ctx.measureText(line + ch).width > width && line) {
      lines.push(line)
      line = ch
      if (lines.length === maxLines) break
    } else line += ch
  }
  if (lines.length < maxLines && line) lines.push(line)
  else if (lines.length === maxLines && line) {
    let last = lines[maxLines - 1]
    while (last && ctx.measureText(`${last}…`).width > width) last = last.slice(0, -1)
    lines[maxLines - 1] = `${last}…`
  }
  return lines
}

/** 根据背景色亮度决定课程块上的文字用白色还是深色。 */
function textOn(hex) {
  const n = Number.parseInt(String(hex || '').replace('#', '').slice(0, 6), 16)
  if (Number.isNaN(n)) return 'rgba(255,255,255,1)'
  const lum = (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255
  return lum > 0.72 ? themeColor('ink') : 'rgba(255,255,255,1)'
}

/** 每天的课程分栏：同一时段多门课并排（与 CourseGrid 相同的规则）。 */
function layoutDay(courses) {
  const list = [...courses].sort((a, b) => a.start_period - b.start_period || Number(b.in_week) - Number(a.in_week))
  const lanes = []
  const placed = list.map((course) => {
    let lane = lanes.findIndex((end) => end < course.start_period)
    if (lane === -1) lane = lanes.push(0) - 1
    lanes[lane] = course.end_period
    return { course, lane }
  })
  return placed.map((item) => {
    const overlapping = placed.filter((o) => o.course.start_period <= item.course.end_period && o.course.end_period >= item.course.start_period)
    return { ...item, width: Math.max(...overlapping.map((o) => o.lane)) + 1 }
  })
}

export function drawTimetable(data, { showOff = false, title = '' } = {}) {
  const hasWeekend = data.courses.some((c) => c.day_of_week >= 6)
  const days = data.days.slice(0, hasWeekend ? 7 : 5)
  const periods = data.period_times
  const W = 1080
  const pad = 40
  const headerH = 150
  const dayH = 76
  const periodW = 92
  const rowH = periods.length > 12 ? 76 : 88
  const footerH = 64
  const H = headerH + dayH + rowH * periods.length + footerH + pad
  const scale = 2
  const canvas = document.createElement('canvas')
  canvas.width = W * scale
  canvas.height = H * scale
  const ctx = canvas.getContext('2d')
  ctx.scale(scale, scale)
  ctx.textBaseline = 'middle'

  const c = {
    page: themeColor('background'),
    surface: themeColor('surface'),
    ink: themeColor('ink'),
    soft: themeColor('ink-soft'),
    mute: themeColor('ink-mute'),
    line: themeColor('ink-line'),
    primary: themeColor('primary'),
    primaryLight: themeColor('primary-light'),
  }

  // 背景
  ctx.fillStyle = c.page
  ctx.fillRect(0, 0, W, H)

  // 标题：学期 · 第几周
  ctx.fillStyle = c.ink
  ctx.font = `900 44px ${FONT}`
  ctx.fillText(title || `第 ${data.week} 周课表`, pad, 62)
  ctx.fillStyle = c.soft
  ctx.font = `600 22px ${FONT}`
  const range = `${days[0].date.replaceAll('-', '/')} – ${days[days.length - 1].date.slice(5).replace('-', '/')}`
  const sub = [data.semester, data.settings_ready ? `第 ${data.week} 周 / 共 ${data.total_weeks} 周` : '未设置开学日期', range].filter(Boolean).join('  ·  ')
  ctx.fillText(sub, pad, 112)

  // 网格卡片
  const gridX = pad
  const gridY = headerH
  const gridW = W - pad * 2
  const gridH = dayH + rowH * periods.length
  ctx.fillStyle = c.surface
  roundRect(ctx, gridX - 12, gridY - 12, gridW + 24, gridH + 24, 28)
  ctx.fill()

  const colW = (gridW - periodW) / days.length
  // 星期表头
  days.forEach((day, i) => {
    const x = gridX + periodW + colW * i
    if (day.is_today) {
      ctx.fillStyle = c.primary
      roundRect(ctx, x + 4, gridY + 4, colW - 8, dayH - 8, 16)
      ctx.fill()
    }
    ctx.textAlign = 'center'
    ctx.fillStyle = day.is_today ? 'rgba(255,255,255,1)' : c.ink
    ctx.font = `900 24px ${FONT}`
    ctx.fillText(day.label, x + colW / 2, gridY + 28)
    ctx.fillStyle = day.is_today ? 'rgba(255,255,255,0.85)' : c.mute
    ctx.font = `600 17px ${FONT}`
    ctx.fillText(day.short, x + colW / 2, gridY + 54)
  })

  // 节次列 + 横线
  periods.forEach((p, i) => {
    const y = gridY + dayH + rowH * i
    ctx.strokeStyle = c.line
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(gridX, y)
    ctx.lineTo(gridX + gridW, y)
    ctx.stroke()
    ctx.textAlign = 'center'
    ctx.fillStyle = c.soft
    ctx.font = `900 24px ${FONT}`
    ctx.fillText(String(i + 1), gridX + periodW / 2, y + rowH / 2 - 14)
    ctx.fillStyle = c.mute
    ctx.font = `500 15px ${FONT}`
    ctx.fillText(p.start, gridX + periodW / 2, y + rowH / 2 + 10)
    ctx.fillText(p.end, gridX + periodW / 2, y + rowH / 2 + 28)
  })

  // 课程块
  ctx.textAlign = 'left'
  days.forEach((day, i) => {
    const colX = gridX + periodW + colW * i
    const list = data.courses.filter((course) => course.day_of_week === day.day_of_week && (course.in_week || showOff))
    for (const { course, lane, width } of layoutDay(list)) {
      const x = colX + (colW / width) * lane + 4
      const w = colW / width - 8
      const y = gridY + dayH + (course.start_period - 1) * rowH + 4
      const h = (course.end_period - course.start_period + 1) * rowH - 8
      roundRect(ctx, x, y, w, h, 16)
      if (course.in_week) {
        ctx.fillStyle = course.color || c.primary
        ctx.fill()
      } else {
        ctx.fillStyle = c.page
        ctx.fill()
        ctx.setLineDash([6, 5])
        ctx.strokeStyle = c.mute
        ctx.stroke()
        ctx.setLineDash([])
      }
      const fg = course.in_week ? textOn(course.color) : c.mute
      const inner = w - 20
      ctx.save()
      roundRect(ctx, x, y, w, h, 16)
      ctx.clip()
      ctx.fillStyle = fg
      ctx.font = `800 ${width > 1 ? 17 : 20}px ${FONT}`
      const nameLines = wrap(ctx, course.course_name, inner, Math.max(1, Math.min(4, Math.floor((h - 40) / 26))))
      let ty = y + 22
      for (const line of nameLines) {
        ctx.fillText(line, x + 10, ty)
        ty += 25
      }
      ctx.font = `500 ${width > 1 ? 14 : 16}px ${FONT}`
      ctx.globalAlpha = 0.92
      if (course.classroom && ty + 4 < y + h) {
        for (const line of wrap(ctx, `@${course.classroom}`, inner, 2)) {
          if (ty + 4 > y + h) break
          ctx.fillText(line, x + 10, ty + 2)
          ty += 21
        }
      }
      if (course.teacher && ty + 4 < y + h && h > 120) ctx.fillText(wrap(ctx, course.teacher, inner, 1)[0] || '', x + 10, ty + 2)
      if (!course.in_week && ty + 4 < y + h) ctx.fillText('非本周', x + 10, ty + 2)
      ctx.globalAlpha = 1
      ctx.restore()
    }
  })

  // 页脚
  ctx.textAlign = 'center'
  ctx.fillStyle = c.mute
  ctx.font = `600 18px ${FONT}`
  ctx.fillText('学业管家 · 课表 × 待办 × 专注', W / 2, H - pad / 2 - footerH / 2 + 8)
  return canvas
}

export const canvasToBlob = (canvas) =>
  new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('图片生成失败'))), 'image/png'))
