<script setup>
/** 反馈通知设置：机器人地址 / 加签密钥只显示掩码，留空表示不修改。 */
import { computed, onMounted, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { adminApi } from '@/api/admin'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const view = ref(null)
const busy = ref(false)
const form = reactive({ webhook: '', secret: '', emails: '', public_url: '' })
const clear = reactive({ webhook: false, secret: false })

const SOURCE = { admin: '后台设置', env: '服务器 .env', none: '未配置' }
const MAIL = { smtp: 'SMTP 发送', console: '仅写日志（未配置 SMTP）', memory: '测试模式' }

// 服务器 DeepSeek Key 的每人每日 AI 额度（0 = 不限）
const quota = reactive({ calls: 0, tokens: 0 })
const fill = (data) => {
  view.value = data
  Object.assign(form, { webhook: '', secret: '', emails: data.feedback_notify_emails, public_url: data.public_url })
  Object.assign(clear, { webhook: false, secret: false })
  Object.assign(quota, { calls: data.ai_daily_calls ?? 0, tokens: data.ai_daily_tokens ?? 0 })
}
const saveQuota = async () => {
  const calls = Number(quota.calls)
  const tokens = Number(quota.tokens)
  if (![calls, tokens].every((n) => Number.isInteger(n) && n >= 0)) return ui.toast('请输入不小于 0 的整数', 'warning')
  busy.value = true
  try {
    fill(await adminApi.saveSettings({ ai_daily_calls: calls, ai_daily_tokens: tokens }))
    ui.success('AI 额度已保存，立即生效')
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try {
    fill(await adminApi.settings())
  } catch (error) {
    ui.fail(error)
  }
})

const kind = computed(() => {
  const url = form.webhook.trim()
  if (!url) return ''
  if (/qyapi\.weixin\.qq\.com/.test(url)) return '企业微信'
  if (/feishu\.cn|larksuite\.com/.test(url)) return '飞书'
  if (/dingtalk\.com/.test(url)) return '钉钉'
  return '通用 JSON'
})

const save = async () => {
  const payload = {}
  if (clear.webhook) payload.feedback_webhook = ''
  else if (form.webhook.trim()) payload.feedback_webhook = form.webhook.trim()
  if (clear.secret) payload.feedback_webhook_secret = ''
  else if (form.secret.trim()) payload.feedback_webhook_secret = form.secret.trim()
  if (form.emails.trim() !== view.value.feedback_notify_emails) payload.feedback_notify_emails = form.emails.trim()
  if (form.public_url.trim() !== view.value.public_url) payload.public_url = form.public_url.trim()
  if (!Object.keys(payload).length) return ui.toast('没有修改', 'info')
  busy.value = true
  try {
    fill(await adminApi.saveSettings(payload))
    ui.success('设置已保存')
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
const test = async () => {
  busy.value = true
  try {
    const r = await adminApi.testNotify()
    const parts = [r.webhook && `机器人：${r.webhook === 'ok' ? '成功' : r.webhook}`, r.email && `邮件：${r.email === 'ok' ? '已发送' : r.email}`].filter(Boolean)
    ui.success(`测试通知已发送（${parts.join('；')}）`)
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="!view" class="skeleton h-80" />
  <div v-else class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
    <section class="card space-y-4 p-4">
      <h3 class="section-title flex items-center gap-2"><Icon icon="lucide:bell" width="17" class="text-primary" />新反馈通知</h3>

      <div>
        <p class="label">群机器人地址（企业微信 / 飞书 / 钉钉，自动识别）</p>
        <p class="mb-1.5 text-[11px] text-ink-mute">
          当前：<span class="font-bold text-ink-soft">{{ view.feedback_webhook_set ? `${view.feedback_webhook_kind} · ${view.feedback_webhook_masked}` : '未配置' }}</span>
          <span class="ml-1">（{{ SOURCE[view.source.feedback_webhook] }}）</span>
        </p>
        <input v-model="form.webhook" class="field" type="url" inputmode="url" :disabled="clear.webhook" placeholder="粘贴新地址；留空表示不修改" autocomplete="off" />
        <div class="mt-1.5 flex items-center justify-between text-[11px]">
          <span class="text-primary">{{ kind && `将按「${kind}」格式发送` }}</span>
          <label v-if="view.feedback_webhook_set" class="flex items-center gap-1.5 text-ink-soft"><input v-model="clear.webhook" type="checkbox" class="accent-danger" />停用机器人推送</label>
        </div>
      </div>

      <div>
        <p class="label">加签密钥（钉钉 SEC… / 飞书签名校验，选填）</p>
        <p class="mb-1.5 text-[11px] text-ink-mute">当前：<span class="font-bold text-ink-soft">{{ view.feedback_webhook_secret_set ? view.feedback_webhook_secret_masked : '未设置' }}</span></p>
        <input v-model="form.secret" class="field" type="password" :disabled="clear.secret" placeholder="留空表示不修改" autocomplete="new-password" />
        <label v-if="view.feedback_webhook_secret_set" class="mt-1.5 flex items-center justify-end gap-1.5 text-[11px] text-ink-soft"><input v-model="clear.secret" type="checkbox" class="accent-danger" />清除密钥</label>
      </div>

      <div>
        <p class="label">通知邮箱（多个用逗号分隔）</p>
        <input v-model="form.emails" class="field" placeholder="ops@example.com, dev@example.com" autocomplete="off" />
      </div>

      <div>
        <p class="label">网站地址（通知里的后台链接）</p>
        <input v-model="form.public_url" class="field" type="url" inputmode="url" placeholder="https://app.xueyeguanjia.com" autocomplete="off" />
      </div>

      <div class="grid grid-cols-2 gap-2">
        <button class="btn-ghost" type="button" :disabled="busy || (!view.feedback_webhook_set && !view.feedback_notify_emails)" @click="test"><Icon icon="lucide:send" width="15" />发送测试通知</button>
        <button class="btn-primary" type="button" :disabled="busy" @click="save">保存设置</button>
      </div>
    </section>

    <section class="card space-y-4 p-4 lg:order-3">
      <h3 class="section-title flex items-center gap-2"><Icon icon="lucide:gauge" width="17" class="text-xp" />AI 每日额度（服务器 DeepSeek Key）</h3>
      <p class="text-[11px] leading-5 text-ink-mute">
        只限制使用服务器 Key 的请求（对话、规划、课表识别、讲义大纲、每周复盘都计入；一次对话回合算 1 次）。用户自己的 Key 与管理员不受限。0 表示不限。
        <span v-if="!view.ai_env_configured" class="font-bold text-flame">服务器当前未配置 DEEPSEEK_API_KEY。</span>
      </p>
      <div class="grid grid-cols-2 gap-3">
        <label>
          <span class="label">每人每天次数</span>
          <input v-model.number="quota.calls" class="field num" type="number" min="0" step="1" inputmode="numeric" />
          <span class="mt-1 block text-[11px] text-ink-mute">{{ SOURCE[view.ai_limit_source?.calls] || '' }}</span>
        </label>
        <label>
          <span class="label">每人每天 tokens</span>
          <input v-model.number="quota.tokens" class="field num" type="number" min="0" step="10000" inputmode="numeric" />
          <span class="mt-1 block text-[11px] text-ink-mute">{{ SOURCE[view.ai_limit_source?.tokens] || '' }}</span>
        </label>
      </div>
      <button class="btn-primary w-full" type="button" :disabled="busy" @click="saveQuota">保存额度</button>
    </section>

    <aside class="card space-y-3 p-4 text-xs leading-5 text-ink-soft">
      <h3 class="section-title">说明</h3>
      <p>用户提交反馈后，服务器会在后台把类型、摘要、用户、页面和后台链接推送到这里配置的群机器人和邮箱；推送失败不影响用户提交。</p>
      <p>这里的设置优先于服务器 .env 中的 FEEDBACK_WEBHOOK / FEEDBACK_WEBHOOK_SECRET / FEEDBACK_NOTIFY_EMAILS。</p>
      <div class="rounded-2xl bg-background p-3">
        <p class="font-bold text-ink">邮件发送：{{ MAIL[view.mail_backend] || view.mail_backend }}</p>
        <p class="mt-1 text-[11px] text-ink-mute">注册必须验证邮箱：{{ view.require_email_verify ? '已开启' : '未开启' }}（.env 的 REQUIRE_EMAIL_VERIFY）</p>
      </div>
    </aside>
  </div>
</template>
