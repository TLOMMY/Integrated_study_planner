<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { aiApi } from '@/api'
import { useAiStore } from '@/stores/ai'
import { useUiStore } from '@/stores/ui'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const ai = useAiStore()
const ui = useUiStore()

const view = ref('list') // list | edit
const editing = ref(null)
const busy = ref('')
const showKey = ref(false)
const models = ref([])
const testResult = ref(null)
const form = reactive({ preset: 'custom', name: '', base_url: '', model: '', api_key: '' })

const s = computed(() => ai.settings)
const preset = computed(() => s.value?.presets.find((p) => p.key === form.preset))

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    view.value = 'list'
    try {
      await ai.loadSettings()
    } catch (error) {
      ui.fail(error)
    }
  },
)

const startEdit = (provider = null) => {
  editing.value = provider
  models.value = []
  testResult.value = null
  showKey.value = false
  Object.assign(form, provider
    ? { preset: 'custom', name: provider.name, base_url: provider.base_url, model: provider.model, api_key: '' }
    : { preset: 'deepseek', ...pick(s.value.presets[0]), api_key: '' })
  view.value = 'edit'
}
const pick = (p) => ({ name: p.name, base_url: p.base_url, model: p.model })
const applyPreset = (p) => {
  form.preset = p.key
  Object.assign(form, pick(p))
  models.value = []
  testResult.value = null
}

const probe = () => ({
  provider_id: editing.value ? String(editing.value.id) : null,
  base_url: form.base_url.trim(),
  model: form.model.trim(),
  api_key: form.api_key.trim() || null,
})

const fetchModels = async () => {
  busy.value = 'models'
  try {
    models.value = (await aiApi.listModels(probe())).models
    if (!models.value.length) ui.toast('接口没有返回模型，请手动填写', 'warning')
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = ''
  }
}

const test = async () => {
  if (!form.model.trim()) return ui.toast('请先填写模型名称', 'warning')
  busy.value = 'test'
  testResult.value = null
  try {
    const data = await aiApi.testProvider(probe())
    testResult.value = { ok: true, text: `连接成功 · ${data.latency_ms} ms · 回复「${data.reply}」` }
  } catch (error) {
    testResult.value = { ok: false, text: error.message }
  } finally {
    busy.value = ''
  }
}

const save = async () => {
  if (!form.name.trim() || !form.base_url.trim() || !form.model.trim()) return ui.toast('请填写名称、接口地址和模型', 'warning')
  if (!editing.value && preset.value?.needs_key && !form.api_key.trim()) return ui.toast('该服务需要 API Key', 'warning')
  busy.value = 'save'
  try {
    const payload = { name: form.name.trim(), base_url: form.base_url.trim(), model: form.model.trim() }
    if (form.api_key.trim() || !editing.value) payload.api_key = form.api_key.trim() || null
    await ai.saveProvider(payload, editing.value?.id)
    view.value = 'list'
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = ''
  }
}

const activate = (value) => ai.activate(value).catch((error) => ui.fail(error))

// 思考强度作用于当前使用的配置；不支持思考模式的模型置灰
const THINKING = [
  { key: 'off', label: '关闭', hint: '回复最快' },
  { key: 'high', label: '高', hint: '推荐' },
  { key: 'max', label: '最高', hint: '最慢、最仔细' },
]
const thinkingValue = computed(() => s.value?.resolved?.thinking_setting || 'high')
const thinkingEnabled = computed(() => s.value?.resolved?.provider === 'llm' && s.value?.resolved?.thinking_supported)
const setThinking = (key) => ai.setThinking(key).catch((error) => ui.fail(error))
const remove = (provider) => ai.removeProvider(provider)?.catch?.((error) => ui.fail(error))
</script>

<template>
  <BottomSheet
    :open="open"
    :title="view === 'list' ? 'AI 模型' : editing ? '编辑配置' : '添加模型'"
    :subtitle="view === 'list' ? '兼容 OpenAI 协议的模型都可以接入，一键切换' : '填写 OpenAI 兼容接口（/v1/chat/completions）'"
    @close="emit('close')"
  >
    <div v-if="!s" class="space-y-2 pb-4"><div v-for="i in 3" :key="i" class="skeleton h-16" /></div>

    <!-- 配置列表 -->
    <div v-else-if="view === 'list'" class="space-y-2.5 pb-2">
      <p class="rounded-2xl bg-primary-light px-4 py-2.5 text-xs font-semibold text-primary">
        当前使用：{{ s.resolved.label }}
      </p>

      <div class="rounded-3xl border border-ink-line/70 p-3.5" :class="!thinkingEnabled && 'opacity-60'">
        <p class="flex items-center gap-1.5 text-sm font-black text-ink"><Icon icon="lucide:brain" width="16" class="text-primary" />思考强度</p>
        <p class="mt-0.5 text-[11px] text-ink-mute">{{ thinkingEnabled ? '开启后模型会先思考再回答，追问和排程更靠谱，但会慢一些' : '当前模型不支持思考模式（如 deepseek-v4-pro 才支持），不会传思考参数' }}</p>
        <div class="mt-2 grid grid-cols-3 gap-2">
          <button
            v-for="t in THINKING"
            :key="t.key"
            type="button"
            class="rounded-2xl border-2 px-2 py-2 text-center transition"
            :class="thinkingValue === t.key ? 'border-primary bg-primary-light/40 text-primary' : 'border-ink-line/70 text-ink-soft'"
            :disabled="!thinkingEnabled"
            @click="setThinking(t.key)"
          >
            <span class="block text-xs font-black">{{ t.label }}</span>
            <span class="block text-[10px] text-ink-mute">{{ t.hint }}</span>
          </button>
        </div>
      </div>

      <button
        type="button"
        class="flex w-full items-center gap-3 rounded-3xl border-2 p-3.5 text-left transition"
        :class="s.active === 'auto' ? 'border-primary bg-primary-light/40' : 'border-ink-line/70'"
        @click="activate('auto')"
      >
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-background text-ink-soft"><Icon icon="lucide:server" width="20" /></span>
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-black text-ink">自动</span>
          <span class="block truncate text-[11px] text-ink-mute">{{ s.env.configured ? `${s.env.name} · ${s.env.model}` : '服务器未配置模型，将使用本地规则引擎' }}</span>
        </span>
        <Icon v-if="s.active === 'auto'" icon="lucide:circle-check" width="20" class="text-primary" />
      </button>

      <button
        type="button"
        class="flex w-full items-center gap-3 rounded-3xl border-2 p-3.5 text-left transition"
        :class="s.active === 'rule' ? 'border-primary bg-primary-light/40' : 'border-ink-line/70'"
        @click="activate('rule')"
      >
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-background text-ink-soft"><Icon icon="lucide:cpu" width="20" /></span>
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-black text-ink">本地规则引擎</span>
          <span class="block text-[11px] text-ink-mute">不联网、秒出结果，建议为模板化文字</span>
        </span>
        <Icon v-if="s.active === 'rule'" icon="lucide:circle-check" width="20" class="text-primary" />
      </button>

      <div
        v-for="p in s.providers"
        :key="p.id"
        class="flex items-center gap-3 rounded-3xl border-2 p-3.5 transition"
        :class="p.active ? 'border-primary bg-primary-light/40' : 'border-ink-line/70'"
      >
        <button type="button" class="flex min-w-0 flex-1 items-center gap-3 text-left" @click="activate(String(p.id))">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-xp text-on-primary"><Icon icon="lucide:sparkles" width="20" /></span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-black text-ink">{{ p.name }}</span>
            <span class="block truncate text-[11px] text-ink-mute">{{ p.model }} · {{ p.has_key ? p.key_masked : '无 Key' }}</span>
            <span v-if="p.key_unreadable" class="block text-[11px] font-bold text-danger">密钥已失效，请重新填写</span>
          </span>
        </button>
        <Icon v-if="p.active" icon="lucide:circle-check" width="20" class="shrink-0 text-primary" />
        <button class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-background text-ink-soft" type="button" aria-label="编辑" @click="startEdit(p)"><Icon icon="lucide:pencil" width="14" /></button>
        <button class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-danger-light text-danger" type="button" aria-label="删除" @click="remove(p)"><Icon icon="lucide:trash-2" width="14" /></button>
      </div>

      <button class="btn-ghost w-full" type="button" @click="startEdit()"><Icon icon="lucide:plus" width="16" />添加模型</button>
      <p class="px-1 text-[11px] leading-5 text-ink-mute">API Key 加密保存在服务器，页面只显示脱敏后的末四位。AI 生成的任务、课程和修改都会先显示成卡片，导入时逐条检查冲突。</p>
    </div>

    <!-- 编辑表单 -->
    <form v-else class="space-y-3.5 pb-2" @submit.prevent="save">
      <div v-if="!editing">
        <span class="label">选择服务商</span>
        <div class="flex flex-wrap gap-2">
          <button v-for="p in s.presets" :key="p.key" type="button" class="chip" :class="form.preset === p.key && 'chip-active'" @click="applyPreset(p)">{{ p.name }}</button>
        </div>
        <p v-if="preset?.hint" class="mt-1.5 text-[11px] text-ink-mute">{{ preset.hint }}</p>
      </div>

      <label class="block"><span class="label">名称</span><input v-model="form.name" class="field" maxlength="40" placeholder="如 我的 DeepSeek" /></label>
      <label class="block"><span class="label">接口地址（Base URL）</span><input v-model="form.base_url" class="field font-mono text-xs" placeholder="https://api.deepseek.com/v1" autocomplete="off" /></label>
      <label class="block">
        <span class="label">API Key{{ editing ? '（留空则保持不变）' : preset?.needs_key ? '' : '（可选）' }}</span>
        <div class="relative">
          <input v-model="form.api_key" class="field pr-12 font-mono text-xs" :type="showKey ? 'text' : 'password'" :placeholder="editing?.has_key ? editing.key_masked : 'sk-...'" autocomplete="off" />
          <button class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-ink-mute" type="button" :aria-label="showKey ? '隐藏' : '显示'" @click="showKey = !showKey">
            <Icon :icon="showKey ? 'lucide:eye-off' : 'lucide:eye'" width="16" />
          </button>
        </div>
      </label>
      <div>
        <span class="label">模型</span>
        <div class="flex gap-2">
          <input v-model="form.model" class="field flex-1 font-mono text-xs" list="ai-model-options" placeholder="deepseek-v4-pro" autocomplete="off" />
          <button class="btn-ghost shrink-0 px-3 py-2" type="button" :disabled="busy === 'models'" @click="fetchModels">
            <Icon :icon="busy === 'models' ? 'lucide:loader-circle' : 'lucide:list'" width="16" :class="busy === 'models' && 'animate-spin'" />获取
          </button>
        </div>
        <datalist id="ai-model-options"><option v-for="m in models" :key="m" :value="m" /></datalist>
        <div v-if="models.length" class="scrollbar-hide mt-2 flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
          <button v-for="m in models" :key="m" type="button" class="chip py-1 font-mono text-[11px]" :class="form.model === m && 'chip-active'" @click="form.model = m">{{ m }}</button>
        </div>
      </div>

      <div v-if="testResult" class="flex items-start gap-2 rounded-2xl px-4 py-2.5 text-xs font-semibold" :class="testResult.ok ? 'bg-success-light text-success' : 'bg-danger-light text-danger'">
        <Icon :icon="testResult.ok ? 'lucide:circle-check' : 'lucide:circle-x'" width="16" class="mt-0.5 shrink-0" />{{ testResult.text }}
      </div>
    </form>

    <template v-if="s && view === 'edit'" #footer>
      <div class="grid grid-cols-[auto_auto_1fr] gap-2">
        <button class="btn-ghost px-3" type="button" @click="view = 'list'">返回</button>
        <button class="btn-ghost" type="button" :disabled="busy === 'test'" @click="test">
          <Icon :icon="busy === 'test' ? 'lucide:loader-circle' : 'lucide:plug-zap'" width="16" :class="busy === 'test' && 'animate-spin'" />测试
        </button>
        <button class="btn-primary" type="button" :disabled="busy === 'save'" @click="save">{{ editing ? '保存' : '保存并启用' }}</button>
      </div>
    </template>
  </BottomSheet>
</template>
