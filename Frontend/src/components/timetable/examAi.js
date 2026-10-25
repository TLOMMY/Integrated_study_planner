/** 考试 → "让 AI 排复习计划"：带上考试名称、剩余天数与日期跳到 AI 页。 */
import dayjs from 'dayjs'

export const examDaysText = (exam) => {
  if (exam.days_left === 0) return '今天'
  if (exam.days_left === 1) return '明天'
  return `${exam.days_left} 天`
}

export const aiRoute = (exam) => {
  const date = dayjs(exam.exam_date).format('M月D日')
  const subject = exam.subject && exam.subject !== exam.title ? `（${exam.subject}）` : ''
  return {
    name: 'ai',
    query: { q: `离《${exam.title}》${subject}考试还有 ${exam.days_left} 天（${date}${exam.start_time ? ` ${exam.start_time}` : ''}），帮我安排复习计划` },
  }
}
