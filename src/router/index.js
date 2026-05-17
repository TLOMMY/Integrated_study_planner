import { createRouter, createWebHistory } from 'vue-router'

const MainLayout = () => import('@/layouts/MainLayout.vue')

const AiAssistantView = () => import('@/views/AiAssistantView.vue')
const DayView = () => import('@/views/DayView.vue')
const TodayTaskView = () => import('@/views/TodayTaskView.vue')
const FocusTimerView = () => import('@/views/FocusTimerView.vue')
const PlansView = () => import('@/views/PlansView.vue')
const ProfileView = () => import('@/views/ProfileView.vue')
const StatisticsView = () => import('@/views/StatisticsView.vue')
const TimetableView = () => import('@/views/TimetableView.vue')

const routes = [
  {
    path: '/',
    component: MainLayout,

    children: [
      {
        path: '',
        redirect: '/today-task',
      },

      {
        path: 'ai',
        name: 'ai',
        component: AiAssistantView,
        meta: {
          title: 'AI助手',
        },
      },

      {
        path: 'day',
        name: 'day',
        component: DayView,
        meta: {
          title: '日程视图',
        },
      },

      {
        path: 'today-task',
        name: 'today-task',
        component: TodayTaskView,
        meta: {
          title: '今日任务',
        },
      },

      {
        path: 'focus-timer',
        name: 'focusTimer',
        component: FocusTimerView,
        meta: {
          title: '专注计时',
        },
      },

      {
        path: 'plans',
        name: 'plans',
        component: PlansView,
        meta: {
          title: '学习计划',
        },
      },

      {
        path: 'profile',
        name: 'profile',
        component: ProfileView,
        meta: {
          title: '个人中心',
        },
      },

      {
        path: 'statistics',
        name: 'statistics',
        component: StatisticsView,
        meta: {
          title: '学习统计',
        },
      },

      {
        path: 'timetable',
        name: 'timetable',
        component: TimetableView,
        meta: {
          title: '课程表',
        },
      },
    ],
  },

  {
    path: '/:pathMatch(.*)*',
    redirect: '/today-task',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router