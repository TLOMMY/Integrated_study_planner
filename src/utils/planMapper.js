export const mapPlanItem = (item) => {
  return {
    id: item.id,
    title: item.title,
    icon: item.icon || 'lucide:book-open',
    remainText:
      item.remainText ||
      `剩余 ${item.remaining_days || 0} 天`,
    status: item.status || '进行中',
    progress: item.progress || 0,
    tags: item.tags || [],
    todo: item.todo || '',
    finalResult: item.finalResult || '',
    type: item.type || 'running'
  }
}