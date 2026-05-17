export const mapTaskItem = (item) => {
  return {
    id: item.id,

    title: item.title || '未命名任务',

    type: item.type || '学习任务',

    completed: Boolean(item.completed),

    priority: item.priority || 'normal',

    startTime: item.start_time || '',

    endTime: item.end_time || '',

    duration: item.duration || 0,

    icon: item.icon || 'lucide:check-circle',

    description: item.description || '',

    tag: item.tag || '',

    createdAt: item.created_at || '',

    updatedAt: item.updated_at || ''
  }
}