<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Leaderboard from '@/components/stats/Leaderboard.vue'
import { groupApi } from '@/api/growth'
import { useUiStore } from '@/stores/ui'

/** 学习小组与组内排行榜 */
const route = useRoute()
const router = useRouter()
const ui = useUiStore()

const groups = ref([])
const loading = ref(true)
const current = ref(null)
const detailLoading = ref(false)
const sheet = ref('')
const name = ref('')
const code = ref('')
const busy = ref(false)

const selectedId = computed(() => current.value?.id)

const open = async (id) => {
  detailLoading.value = true
  try {
    current.value = await groupApi.detail(id)
    router.replace({ query: { id } })
  } catch (e) {
    ui.fail(e)
    current.value = null
  } finally {
    detailLoading.value = false
  }
}

const load = async (selectId = null) => {
  try {
    groups.value = await groupApi.list()
    const wanted = selectId || Number(route.query.id) || current.value?.id
    const target = groups.value.find((g) => g.id === wanted) || groups.value[0]
    if (target) await open(target.id)
    else current.value = null
  } catch (e) {
    ui.fail(e, '小组加载失败')
  } finally {
    loading.value = false
  }
}

const create = async () => {
  if (!name.value.trim()) return ui.toast('给小组起个名字', 'warning')
  busy.value = true
  try {
    const group = await groupApi.create(name.value.trim())
    ui.success(`小组已创建，邀请码 ${group.invite_code}`)
    sheet.value = ''
    name.value = ''
    await load(group.id)
  } catch (e) {
    ui.fail(e)
  } finally {
    busy.value = false
  }
}

const join = async () => {
  const value = code.value.replace(/[\s-]/g, '').toUpperCase()
  if (value.length < 4) return ui.toast('请输入邀请码', 'warning')
  busy.value = true
  try {
    const group = await groupApi.join(value)
    ui.success(`已加入「${group.name}」`)
    sheet.value = ''
    code.value = ''
    await load(group.id)
  } catch (e) {
    ui.fail(e)
  } finally {
    busy.value = false
  }
}

const copy = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ui.success('已复制')
  } catch {
    ui.toast(`邀请码：${text}`, 'info', 4000)
  }
}
const copyInvite = () => copy(`来「学业管家」加入学习小组「${current.value.name}」一起比拼本周 XP！成长页 → 小组 → 加入，邀请码：${current.value.invite_code}`)

const leave = async () => {
  const g = current.value
  const ok = await ui.confirm({
    title: `退出「${g.name}」？`,
    message: g.is_owner && g.member_count > 1 ? '你是组长，退出后组长会自动转给最早加入的组员。' : g.member_count <= 1 ? '你是最后一名成员，退出后小组将解散。' : '退出后可以用邀请码重新加入。',
    confirmText: '退出',
    danger: true,
  })
  if (!ok) return
  await groupApi.leave(g.id).then(() => ui.success('已退出小组')).catch(ui.fail)
  current.value = null
  router.replace({ query: {} })
  await load()
}

const dissolve = async () => {
  const g = current.value
  const ok = await ui.confirm({ title: `解散「${g.name}」？`, message: `所有 ${g.member_count} 名成员都会被移出，邀请码失效，无法恢复。`, confirmText: '解散', danger: true })
  if (!ok) return
  await groupApi.dissolve(g.id).then(() => ui.success('小组已解散')).catch(ui.fail)
  current.value = null
  router.replace({ query: {} })
  await load()
}

const resetCode = async () => {
  const ok = await ui.confirm({ title: '重新生成邀请码？', message: '旧邀请码会立即失效，已加入的成员不受影响。', confirmText: '重新生成' })
  if (!ok) return
  try {
    const g = await groupApi.resetCode(current.value.id)
    current.value = { ...current.value, invite_code: g.invite_code }
    groups.value = groups.value.map((item) => (item.id === g.id ? { ...item, invite_code: g.invite_code } : item))
    ui.success(`新邀请码 ${g.invite_code}`)
  } catch (e) {
    ui.fail(e)
  }
}

onMounted(() => load())
</script>

<template>
  <div class="scrollbar-hide h-full overflow-y-auto px-5 pb-24 pt-[calc(var(--safe-top)+16px)] lg:px-10 lg:pb-10 lg:pt-8">
    <div class="desk-page">
      <header class="flex items-center gap-3">
        <button class="icon-btn lg:hidden" type="button" aria-label="返回" @click="router.back()"><Icon icon="lucide:chevron-left" width="20" /></button>
        <div class="min-w-0 flex-1">
          <h1 class="text-[22px] font-black text-ink">学习小组</h1>
          <p class="text-xs font-semibold text-ink-mute">和同学组队，比拼本周 XP</p>
        </div>
        <button class="chip" type="button" @click="sheet = 'join'"><Icon icon="lucide:user-plus" width="14" />加入</button>
        <button class="chip chip-active" type="button" @click="sheet = 'create'"><Icon icon="lucide:plus" width="14" />创建</button>
      </header>

      <div v-if="loading" class="mt-4 space-y-3"><div class="skeleton h-20" /><div class="skeleton h-64" /></div>

      <div v-else-if="!groups.length" class="card mt-4">
        <EmptyState icon="lucide:users" title="还没有加入学习小组" text="创建一个小组，把邀请码发给同学；或者输入同学给你的邀请码加入">
          <button class="chip chip-active" type="button" @click="sheet = 'create'"><Icon icon="lucide:plus" width="13" />创建小组</button>
          <button class="chip" type="button" @click="sheet = 'join'"><Icon icon="lucide:user-plus" width="13" />输入邀请码</button>
        </EmptyState>
      </div>

      <div v-else class="mt-4 lg:grid lg:grid-cols-[320px_1fr] lg:gap-4">
        <!-- 小组列表 -->
        <nav class="scrollbar-hide -mx-5 flex gap-2 overflow-x-auto px-5 lg:mx-0 lg:block lg:space-y-2 lg:px-0" aria-label="我的小组">
          <button
            v-for="g in groups"
            :key="g.id"
            type="button"
            class="flex w-56 shrink-0 items-center gap-3 rounded-3xl border p-3 text-left transition lg:w-full"
            :class="g.id === selectedId ? 'border-primary bg-primary-light' : 'border-ink-line/70 bg-surface'"
            :aria-current="g.id === selectedId"
            @click="open(g.id)"
          >
            <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-surface text-primary shadow-soft"><Icon icon="lucide:users" width="18" /></span>
            <span class="min-w-0 flex-1">
              <span class="flex items-center gap-1 truncate text-sm font-black text-ink">{{ g.name }}<Icon v-if="g.is_owner" icon="lucide:crown" width="12" class="shrink-0 text-flame" /></span>
              <span class="block text-[11px] text-ink-mute">{{ g.member_count }} 人 · 我排第 {{ g.my_rank || '-' }}</span>
            </span>
          </button>
        </nav>

        <!-- 小组详情 -->
        <section class="card mt-3 p-4 lg:mt-0">
          <div v-if="detailLoading && !current" class="skeleton h-64" />
          <template v-else-if="current">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h2 class="truncate text-lg font-black text-ink">{{ current.name }}</h2>
                <p class="text-xs text-ink-mute">组长 {{ current.owner_name }} · {{ current.member_count }}/{{ current.max_members }} 人</p>
              </div>
              <span class="shrink-0 rounded-full bg-xp-light px-2.5 py-1 text-[11px] font-black text-xp">我 +{{ current.my_xp }} XP</span>
            </div>

            <div class="mt-3 flex items-center gap-2 rounded-2xl bg-background px-3 py-2.5">
              <Icon icon="lucide:ticket" width="18" class="shrink-0 text-primary" />
              <span class="text-xs text-ink-soft">邀请码</span>
              <span class="num flex-1 select-all text-base font-black tracking-[0.2em] text-ink">{{ current.invite_code }}</span>
              <button class="text-xs font-bold text-primary" type="button" @click="copy(current.invite_code)">复制</button>
              <button class="text-xs font-bold text-primary" type="button" @click="copyInvite">邀请文字</button>
            </div>

            <div class="mb-2 mt-4 flex items-center justify-between">
              <h3 class="section-title">本周 XP 排行</h3>
              <span class="text-[11px] text-ink-mute">{{ dayjs(current.week_start).format('M/D') }} 起 · 每周一重置</span>
            </div>
            <Leaderboard :board="current.leaderboard" :limit="50" />

            <div class="mt-4 flex flex-wrap justify-end gap-2">
              <button v-if="current.is_owner" class="chip" type="button" @click="resetCode"><Icon icon="lucide:refresh-cw" width="13" />重置邀请码</button>
              <button class="chip" type="button" @click="leave"><Icon icon="lucide:log-out" width="13" />退出小组</button>
              <button v-if="current.is_owner" class="chip border-danger/30 text-danger" type="button" @click="dissolve"><Icon icon="lucide:trash-2" width="13" />解散</button>
            </div>
          </template>
        </section>
      </div>
    </div>

    <BottomSheet :open="sheet === 'create'" title="创建学习小组" subtitle="创建后把邀请码发给同学" @close="sheet = ''">
      <form @submit.prevent="create">
        <label class="block">
          <span class="label">小组名称</span>
          <input v-model="name" class="field" maxlength="40" placeholder="如 高数互助组、25 卓越 4 班" />
        </label>
      </form>
      <template #footer>
        <button class="btn-primary w-full" type="button" :disabled="busy" @click="create">创建</button>
      </template>
    </BottomSheet>

    <BottomSheet :open="sheet === 'join'" title="加入学习小组" subtitle="输入同学给你的 6 位邀请码" @close="sheet = ''">
      <form @submit.prevent="join">
        <input v-model="code" class="field num text-center text-lg font-black uppercase tracking-[0.25em]" maxlength="12" placeholder="邀请码" aria-label="邀请码" autocomplete="off" autocapitalize="characters" />
      </form>
      <template #footer>
        <button class="btn-primary w-full" type="button" :disabled="busy" @click="join">加入</button>
      </template>
    </BottomSheet>
  </div>
</template>
