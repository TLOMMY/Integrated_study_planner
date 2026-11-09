/**
 * App 内置浏览器导入课表：注入教务系统页面的脚本，以及把回传内容整理成上传文件。纯函数，便于测试。
 *
 * 流程：内置浏览器打开教务系统 → 每次页面加载完注入 CAPTURE_SCRIPT，在页面右下角放一个"导入此页课表"按钮 →
 * 同学登录、进到课表页后点按钮 → 脚本收集顶层页面和同源 iframe / frame 渲染后的 HTML，
 * 用 FRAME_MARKER（与后端 import_web.FRAME_MARKER 一致）拼接，经 window.mobileApp.postMessage 回传 App →
 * App 把它包装成 .html 文件，走现有的网页导入解析与预览。
 * 只读取页面内容，不保存账号密码，也不在后台访问教务系统。
 */

export const FRAME_MARKER = '<!--STUDY-PLANNER-FRAME-->'
export const MESSAGE_TYPE = 'xyg-timetable'
// 与后端 MAX_UPLOAD_BYTES 一致；超出时去掉 script / style 再试
export const MAX_BYTES = 5 * 1024 * 1024
const BUTTON_ID = '__xyg_import_btn'

/**
 * 注入页面的脚本（ES5，兼容老旧教务系统的页面环境）。重复注入时只保留一个按钮。
 * accent：按钮颜色（App 当前主题的主色），只用于这个按钮，不影响页面本身。
 */
export const captureScript = (accent = '#D85A30') => `(function(){
  if (window.top !== window || document.getElementById('${BUTTON_ID}')) return;
  var M='${FRAME_MARKER}';
  function walk(w,d,out){if(d>4)return;try{var doc=w.document;var html=doc.documentElement.outerHTML;out.push(html);}catch(e){return;}
    for(var i=0;i<w.frames.length;i++){walk(w.frames[i],d+1,out);}}
  function add(){
    if(!document.body){setTimeout(add,300);return;}
    var b=document.createElement('button');
    b.id='${BUTTON_ID}';b.type='button';b.textContent='导入此页课表';
    b.setAttribute('style','position:fixed;right:16px;bottom:24px;z-index:2147483647;padding:12px 18px;border:0;border-radius:999px;background:${accent};color:#fff;font:600 15px/1 system-ui,sans-serif;box-shadow:0 6px 20px rgba(0,0,0,.25)');
    b.onclick=function(){
      b.textContent='正在读取…';
      var out=[];walk(window,0,out);
      var html=out.join(M).split('id="${BUTTON_ID}"').join('');
      try{window.mobileApp.postMessage({detail:{type:'${MESSAGE_TYPE}',html:html,url:location.href,title:document.title}});}
      catch(e){b.textContent='读取失败，请重试';return;}
      setTimeout(function(){b.textContent='导入此页课表';},1500);
    };
    document.body.appendChild(b);
  }
  add();
})();`

/** 从 messageFromWebview 事件里取出课表页面；不是本功能的消息返回 null。 */
export const readCapture = (event) => {
  const detail = event?.detail?.detail || event?.detail
  if (!detail || detail.type !== MESSAGE_TYPE || typeof detail.html !== 'string' || !detail.html.trim()) return null
  return { html: detail.html, url: String(detail.url || ''), title: String(detail.title || '') }
}

const byteLength = (text) => new TextEncoder().encode(text).length

/** 太大时去掉 script / style / 注释（解析只看表格文字，去掉不影响结果），仍然太大返回 null。 */
export const shrinkHtml = (html) => {
  if (byteLength(html) <= MAX_BYTES) return html
  const parts = html.split(FRAME_MARKER).map((part) =>
    part
      .replace(/<script\b[\s\S]*?<\/script>/gi, '')
      .replace(/<style\b[\s\S]*?<\/style>/gi, '')
      .replace(/<!--(?!STUDY-PLANNER-FRAME)[\s\S]*?-->/g, '')
      .replace(/\s{2,}/g, ' '),
  )
  const small = parts.join(FRAME_MARKER)
  return byteLength(small) <= MAX_BYTES ? small : null
}

/** 上传用的文件名：教务系统网址的域名，便于在导入记录里辨认。 */
export const captureFileName = (url) => {
  let host = ''
  try {
    host = new URL(url).hostname
  } catch {
    host = ''
  }
  return `${host || '教务系统'}-课表.html`
}
