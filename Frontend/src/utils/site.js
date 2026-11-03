/**
 * 站点信息（备案号、联系邮箱、条款版本）与 AI 额度的展示逻辑。纯函数部分有单元测试（site.test.js）。
 */

/** 后端不可用或旧版服务器没有 /site/info 时的默认值 */
export const DEFAULT_SITE = Object.freeze({
  app_name: '学业管家',
  version: '',
  icp_number: '',
  icp_url: '',
  police_beian: '',
  police_url: '',
  contact_email: '',
  terms_version: '',
})

export const MIIT_URL = 'https://beian.miit.gov.cn/'
export const MPS_URL = 'https://beian.mps.gov.cn/'

/** 备案链接：号码为空的不显示；链接缺省时用工信部 / 公安部官网。 */
export function beianLinks(info) {
  const links = []
  const icp = String(info?.icp_number || '').trim()
  const police = String(info?.police_beian || '').trim()
  if (icp) links.push({ key: 'icp', text: icp, url: info.icp_url || MIIT_URL })
  if (police) links.push({ key: 'police', text: police, url: info.police_url || MPS_URL })
  return links
}

/**
 * AI 额度提示文字：只在使用服务器 Key 且有上限时返回，例如"今日剩余 12 次"；
 * 已用完返回 { exceeded: true }；不限时返回 null。
 */
export function quotaText(quota) {
  if (!quota || !quota.limited) return null
  if (quota.exceeded) return { exceeded: true, text: '今日服务器 AI 额度已用完' }
  if (quota.calls_left != null) return { exceeded: false, text: `今日剩余 ${quota.calls_left} 次` }
  if (quota.tokens_left != null) return { exceeded: false, text: `今日剩余 ${formatTokens(quota.tokens_left)} tokens` }
  return null
}

export function formatTokens(value) {
  const n = Number(value) || 0
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M`
  if (n >= 1e4) return `${(n / 1e3).toFixed(0)}k`
  return String(n)
}

let cache = null
/** 读取站点信息（同一页面会话内只请求一次；失败返回默认值，不报错）。 */
export function loadSiteInfo(fetcher) {
  if (!cache) {
    cache = Promise.resolve()
      .then(fetcher)
      .then((data) => ({ ...DEFAULT_SITE, ...(data || {}) }))
      .catch(() => {
        cache = null
        return { ...DEFAULT_SITE }
      })
  }
  return cache
}
