/**
 * 补零
 */
const padZero = (num) => {
  return String(num).padStart(2, '0')
}

/**
 * 格式化日期
 * yyyy-MM-dd
 */
export const formatDate = (date = new Date()) => {
  const d = new Date(date)

  const year = d.getFullYear()
  const month = padZero(d.getMonth() + 1)
  const day = padZero(d.getDate())

  return `${year}-${month}-${day}`
}

/**
 * 格式化日期时间
 * yyyy-MM-dd HH:mm
 */
export const formatDateTime = (date = new Date()) => {
  const d = new Date(date)

  const year = d.getFullYear()
  const month = padZero(d.getMonth() + 1)
  const day = padZero(d.getDate())

  const hours = padZero(d.getHours())
  const minutes = padZero(d.getMinutes())

  return `${year}-${month}-${day} ${hours}:${minutes}`
}

/**
 * 格式化时间
 * HH:mm
 */
export const formatTime = (date = new Date()) => {
  const d = new Date(date)

  const hours = padZero(d.getHours())
  const minutes = padZero(d.getMinutes())

  return `${hours}:${minutes}`
}

/**
 * 获取星期
 */
export const getWeekday = (date = new Date()) => {
  const d = new Date(date)

  const weekdays = [
    '星期日',
    '星期一',
    '星期二',
    '星期三',
    '星期四',
    '星期五',
    '星期六'
  ]

  return weekdays[d.getDay()]
}

/**
 * 获取剩余天数
 */
export const getRemainingDays = (endDate) => {
  if (!endDate) return 0

  const now = new Date()

  const target = new Date(endDate)

  const diff = target - now

  return Math.max(
    Math.ceil(diff / (1000 * 60 * 60 * 24)),
    0
  )
}

/**
 * 判断是否今天
 */
export const isToday = (date) => {
  const today = formatDate(new Date())

  return formatDate(date) === today
}

/**
 * 秒转 mm:ss
 */
export const formatSeconds = (seconds = 0) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60

  return `${padZero(mins)}:${padZero(secs)}`
}

/**
 * 分钟转小时
 */
export const formatMinutesToHour = (minutes = 0) => {
  if (minutes < 60) {
    return `${minutes}分钟`
  }

  const hours = Math.floor(minutes / 60)

  const remainMinutes = minutes % 60

  if (remainMinutes === 0) {
    return `${hours}小时`
  }

  return `${hours}小时${remainMinutes}分钟`
}