
// —— 图标回退（内置资源）——
// /local/lixiang-icons 缺失时，img onerror 自动切到集成内置路径。
const __lxIconFallback = (typeof window !== "undefined" && (window.__lxIconFallback = window.__lxIconFallback || function (img) {
  if (img.dataset.lxFb) return;
  img.dataset.lxFb = "1";
  const s = img.getAttribute("src") || "";
  const rel = s.replace(/^\/local\/lixiang-icons\//, "");
  if (rel === s) return;
  img.src = "/lixiang_auto/lixiang-icons/" + rel;
})) || function (img) {};
/*!
 * lixiang-base.js —— 卡片共享基座（样式 / 字体 / 图标 / 工具）
 *
 * ★ 为什么要有它：13 个页面各自抄一遍 `@font-face` + 图标/字体 base + 主题变量
 *   （实测 13/14 个文件重复）→ 改一处要改 13 次，还容易不一致。
 *
 * 提供：
 *   · BASE_CSS      主题变量 + 通用样式（卡片/行/图标/深浅色）
 *     ⚠️ 2026-10-14：原来变量写在 `:host` —— 但除 overview-card 外我们的卡都**不用**
 *        Shadow DOM，`:host` 永不匹配 → 强调色变量（--lx-green/orange/red）一直为空。
 *        改为零特异度的 `:where(.root)`：消费方自己的 .root[data-theme] 仍优先。
 *   · fontFaceCss() 字体声明（按 fontBase 生成）
 *   · iconUrl()     图标 URL（带 cache-buster）
 *   · html`/esc`    小工具
 *
 * ★ 本文件是 ES module（页面用 `import` 引用）；同时挂 `window.LxBase` 供非模块场景。
 *   若同目录没有本文件（老安装），
 *   页面必须有自己的兜底（见各页 `catch`）—— 绝不因为基座缺失而白屏。
 */
export const ICON_BASE_DEFAULT = "/local/lixiang-icons";
export const FONT_BASE_DEFAULT = "/local/lixiang-fonts";

export function fontFaceCss(fontBase) {
  const f = fontBase || FONT_BASE_DEFAULT;
  return `
  @font-face { font-family:"Licium"; src:url("${f}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${f}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${f}/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }`;
}

/** 页面级通用样式（主题变量 + 卡片 + 行） */
export const BASE_CSS = `
  :where(.root) { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :where(.root) { --lx-blue:#4C9AFF; --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; }
  }
  .wrap { font-family:"Licium",system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
          color:var(--lx-t1); background:var(--lx-bg); padding:12px; }
  .card { background:var(--lx-card); border-radius:16px; margin-bottom:12px; overflow:hidden; }
  .row { display:flex; align-items:center; gap:10px; padding:14px 16px; border-bottom:1px solid var(--lx-line); }
  .row:last-child { border-bottom:0; }
  .row .ic { width:20px; height:20px; opacity:.85; }
  .k { flex:1; font-size:14px; }
  .v { font-size:14px; color:var(--lx-t2); }
  .v.na { color:var(--lx-t3); }
  .v.mono { font-family:"LxNum",monospace; letter-spacing:.3px; }
  .muted { color:var(--lx-t3); font-size:13px; }
`;

export function assetV() {
  try {
    return (typeof window !== "undefined" && window.__LX_ASSET_V__) || "0";
  } catch (_) {
    return "0";
  }
}

export function vurl(url) {
  const v = assetV();
  if (!url || v === "0") return url;
  return url + (url.indexOf("?") >= 0 ? "&" : "?") + "v=" + encodeURIComponent(v);
}

export function iconUrl(base, name) {
  return vurl((base || ICON_BASE_DEFAULT) + "/" + name);
}

export function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

const api = {
  ICON_BASE_DEFAULT,
  FONT_BASE_DEFAULT,
  fontFaceCss,
  BASE_CSS,
  assetV,
  vurl,
  iconUrl,
  esc,
};

if (typeof window !== "undefined") window.LxBase = api;
