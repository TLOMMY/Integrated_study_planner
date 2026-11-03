<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'

/** 多套课表管理：切换（替换当前生效课表）、新建、重命名、整套删除。 */
const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'import'])

const timetable = useTimetableStore()
const ui = useUiStore()

const sets = computed(() => timetable.sets)
const items = computed(() => sets.value.items || [])
const full = computed(() => items.value.filter((s) => s.id).length >= (sets.value.max || 12))

const busy = ref(false)
const renaming = ref(null)
const renameText = ref('')
const creating = ref(false)
const newName = ref('')
const copySettings = ref(true)
const nameInput = ref(null)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    renaming.value = null
    creating.value = false
    newName.value = ''
    copySettings.value = true
  },
)

const run = async (fn) => {
  if (busy.value) return
  busy.value = true
  try {
    return await fn()
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}

const activate = (set) => run(() => timetable.activateSet(set))

const startRename = async (set) => {
  renaming.value = set.id
  renameText.value = set.name
  await nextTick()
  document.getElementById(`set-rename-${set.id}`)?.select()
}
const saveRename = (set) => {
  const name = renameText.value.trim()
  if (!name) return ui.toast('课表名称不能为空', 'warning')
  if (name === set.name) return (renaming.value = null)
  run(async () => {
    await timetable.renameSet(set, name)
    renaming.value = null
  })
}

const remove = (set) => run(() => timetable.removeSet(set))

const startCreate = async () => {
  creating.value = true
  newName.value = ''
  await nextTick()
  nameInput.value?.focus()
}
const create = () => {
  const name = newName.value.trim()
  if (!name) return ui.toast('给新课表起个名字，如"大二下"', 'warning')
  run(async () => {
    await timetable.createSet({ name, copy_settings: copySettings.value })
    creating.value = false
    emit('close')
  })
}
</script>

<template>
  <BottomSheet :open="open" title="我的课表" subtitle="可以保存多套课表（如不同学期、辅修），点一下切换" @close="emit('close')">
    <ul class="space-y-2" aria-label="课表列表">
      <li
        v-for="set in items"
        :key="set.id ?? 'default'"
        class="flex items-center gap-3 rounded-2xl border px-3 py-2.5"
        :class="set.is_active ? 'border-primary bg-primary-light/60' : 'border-ink-line/70'"
      >
        <button
          class="flex min-w-0 flex-1 items-center gap-3 text-left"
          type="button"
          :disabled="busy || set.is_active || !set.id"
          :aria-label="set.is_active ? `${set.name}（使用中）` : `切换到${set.name}`"
          @click="activate(set)"
        >
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" :class="set.is_active ? 'bg-primary text-on-primary' : 'bg-background text-ink-soft'">
            <Icon :icon="set.is_active ? 'lucide:calendar-check' : 'lucide:calendar'" width="18" />
          </span>
          <span v-if="renaming !== set.id" class="min-w-0 flex-1">
            <span class="flex items-center gap-1.5">
              <span class="truncate text-sm font-bold text-ink">{{ set.name }}</span>
              <span v-if="set.is_active" class="shrink-0 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-bold text-on-primary">使用中</span>
            </span>
            <span class="block truncate text-[11px] text-ink-mute">{{ set.semester || '未设置学期' }} · {{ set.course_count }} 门课</span>
          </span>
        </button>
        <form v-if="renaming === set.id" class="flex min-w-0 flex-1 gap-2" @submit.prevent="saveRename(set)">
          <input :id="`set-rename-${set.id}`" v-model="renameText" class="field py-1.5 text-sm" maxlength="40" aria-label="新名称" @keydown.esc="renaming = null" />
          <button class="btn-primary shrink-0 px-3 py-1.5 text-xs" type="submit" :disabled="busy">保存</button>
        </form>
        <template v-else-if="set.id">
          <button class="icon-btn h-8 w-8 shrink-0" type="button" :aria-label="`重命名${set.name}`" title="重命名" :disabled="busy" @click="startRename(set)">
            <Icon icon="lucide:pencil" width="15" />
          </button>
          <button class="icon-btn h-8 w-8 shrink-0 text-danger" type="button" :aria-label="`删除${set.name}`" title="整套删除" :disabled="busy" @click="remove(set)">
            <Icon icon="lucide:trash-2" width="15" />
          </button>
        </template>
      </li>
    </ul>

    <form v-if="creating" class="mt-3 space-y-2 rounded-3xl bg-background p-4" @submit.prevent="create">
      <label class="label" for="set-new-name">新课表名称</label>
      <input id="set-new-name" ref="nameInput" v-model="newName" class="field" maxlength="40" placeholder="如 大二下、辅修课表" />
      <label class="flex cursor-pointer items-start gap-2 text-xs text-ink-soft">
        <input v-model="copySettings" type="checkbox" class="mt-0.5 accent-primary" />
        <span>沿用当前的学期设置（开学日期、总周数、节次时间）</span>
      </label>
      <div class="grid grid-cols-2 gap-2 pt-1">
        <button class="btn-ghost" type="button" @click="creating = false">取消</button>
        <button class="btn-primary" type="submit" :disabled="busy">新建并切换</button>
      </div>
    </form>

    <p class="mt-3 px-1 text-[11px] leading-5 text-ink-mute">
      首页、日程、AI 助手和分享只使用"使用中"的那套课表。切换时开学日期、总周数和节次时间随课表一起切换。
    </p>

    <template #footer>
      <div v-if="!creating" class="grid grid-cols-2 gap-3">
        <button class="btn-ghost" type="button" @click="emit('import')"><Icon icon="lucide:file-up" width="16" />导入为新课表</button>
        <button class="btn-primary" type="button" :disabled="busy || full" @click="startCreate">
          <Icon icon="lucide:plus" width="16" />{{ full ? `最多 ${sets.max} 套` : '新建空课表' }}
        </button>
      </div>
    </template>
  </BottomSheet>
</template>
