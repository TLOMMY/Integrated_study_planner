/**
 * 站点信息（公开，无需登录）：备案号、联系邮箱、隐私政策 / 用户协议版本。
 * 只放本模块的接口；路径与后端路由一一对应，契约测试会扫描本文件。
 */
import http from './request'

export const siteApi = {
  info: () => http.get('/site/info', { skipAuthRedirect: true }),
}

export default http
