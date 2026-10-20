/* eslint-disable */
/**
 * ⚠️ 自动生成，请勿手改 —— 改源文件后运行 `node scripts/build-cards.mjs`。
 * 内容来源：custom_components/lixiang_auto/www/lixiang-cards/*.js
 * 单文件版：1 个资源即含全部卡片与总卡片外壳，没有相对路径依赖。
 */
window.__LXB = window.__LXB || {};

window.__LXB = window.__LXB || {};
window.__LXB.base = (function () {
/* ===================== lixiang-base.js ===================== */

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
const ICON_BASE_DEFAULT = "/local/lixiang-icons";
const FONT_BASE_DEFAULT = "/local/lixiang-fonts";
function fontFaceCss(fontBase) {
  const f = fontBase || FONT_BASE_DEFAULT;
  return `
  @font-face { font-family:"Licium"; src:url("${f}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${f}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${f}/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }`;
}

/** 页面级通用样式（主题变量 + 卡片 + 行） */
const BASE_CSS = `
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
function assetV() {
  try {
    return (typeof window !== "undefined" && window.__LX_ASSET_V__) || "0";
  } catch (_) {
    return "0";
  }
}
function vurl(url) {
  const v = assetV();
  if (!url || v === "0") return url;
  return url + (url.indexOf("?") >= 0 ? "&" : "?") + "v=" + encodeURIComponent(v);
}
function iconUrl(base, name) {
  return vurl((base || ICON_BASE_DEFAULT) + "/" + name);
}
function esc(s) {
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


/* ══════════════════════════════════════════════════════════════════
 * 车辆位置小地图（高德瓦片自绘）
 *
 * ★ 为什么不复用 HA 官方 <ha-map>：
 *   ha-map 的瓦片走 HA 自己的代理 /api/map_tiles，上游不可达时整块空白
 *   （2026-10-18 实测：部分网络环境解析到 IPv6 但无 IPv6 出口 → 502 → 地图不显示）。
 *   车控「位置页」早就自己拉高德瓦片，这里把那段成熟实现抽成公共函数，
 *   让总览卡与位置页【行为一致】，都只依赖高德。
 *
 * ★ 坐标系坑（位置页踩过，已修）：
 *   lonlatToTile 返回的是【瓦片坐标系里的小数】(如 27394.7)，
 *   车辆相对该瓦片左上角的像素偏移 = (exact - floor(exact)) * 256。
 *   早期把整个 cx（两万多）当像素用 → left ≈ -1400 万 px → 瓦片全跑到屏幕外。
 */
function lonlatToTile(lat, lon, z) {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const y = Math.floor(
    ((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n);
  const fx = ((lon + 180) / 360) * n - x;
  const fy = ((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n - y;
  return [x + fx, y + fy, fx * 256, fy * 256];
}

/** 高德瓦片 URL（style=8 深色；4 个节点轮询） */
function amapTileUrl(tx, ty, z, dark) {
  const s = ((tx + ty) % 4 + 4) % 4 + 1;
  return `https://webrd0${s}.is.autonavi.com/appmaptile`
       + `?lang=zh_cn&size=1&scale=1&style=${dark ? 6 : 8}&x=${tx}&y=${ty}&z=${z}`;
}

/**
 * 把一组瓦片 <img> 铺进容器，使 (lat,lon) 落在容器中心。
 * @param {HTMLElement} box   瓦片容器（position:relative，overflow:hidden）
 * @param {number} lat @param {number} lon @param {number} z
 * @param {{w?:number,h?:number,dark?:boolean}} [opt]
 */
function renderTileMap(box, lat, lon, z, opt) {
  if (!box) return;
  const W = opt && opt.w ? opt.w : (box.clientWidth || 320);
  const H = opt && opt.h ? opt.h : (box.clientHeight || 180);
  const dark = !!(opt && opt.dark);
  const [fx, fy, offX, offY] = lonlatToTile(lat, lon, z);
  const cxInt = Math.floor(fx), cyInt = Math.floor(fy);
  const cpx = W / 2, cpy = H / 2;
  const x0 = cxInt - Math.ceil((cpx - offX) / 256);
  const x1 = cxInt + Math.ceil((W - cpx + offX) / 256);
  const y0 = cyInt - Math.ceil((cpy - offY) / 256);
  const y1 = cyInt + Math.ceil((H - cpy + offY) / 256);
  const n = 2 ** z;
  const keep = new Set();
  const wanted = [];
  for (let tx = x0; tx <= x1; tx++) {
    for (let ty = y0; ty <= y1; ty++) {
      if (tx < 0 || ty < 0 || tx >= n || ty >= n) continue;
      const key = tx + "_" + ty;
      keep.add(key);
      wanted.push({ key, tx, ty,
        left: Math.round(cpx - offX + (tx - cxInt) * 256),
        top: Math.round(cpy - offY + (ty - cyInt) * 256) });
    }
  }
  // 复用已有节点，减少闪烁
  const have = new Map();
  box.querySelectorAll("img").forEach((im) => have.set(im.dataset.k, im));
  for (const w of wanted) {
    const im = have.get(w.key);
    if (im) {
      im.style.left = w.left + "px";
      im.style.top = w.top + "px";
      if (im.getAttribute("src") !== amapTileUrl(w.tx, w.ty, z, dark)) {
        im.src = amapTileUrl(w.tx, w.ty, z, dark);
      }
      have.delete(w.key);
    } else {
      const el = document.createElement("img");
      el.dataset.k = w.key;
      el.src = amapTileUrl(w.tx, w.ty, z, dark);
      el.style.left = w.left + "px";
      el.style.top = w.top + "px";
      box.appendChild(el);
    }
  }
  have.forEach((im) => im.remove());
}
  return { ICON_BASE_DEFAULT, FONT_BASE_DEFAULT, fontFaceCss, BASE_CSS, assetV, vurl, iconUrl, esc, lonlatToTile, amapTileUrl, renderTileMap };
})();

window.__LXB = window.__LXB || {};
window.__LXB.info = (function () {
/* ===================== lixiang-info-page.js ===================== */
const { BASE_CSS, fontFaceCss, iconUrl, esc, ICON_BASE_DEFAULT, FONT_BASE_DEFAULT } = window.__LXB.base;

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
 * lixiang-info-page.js —— 通用「信息型页面」渲染器（数据驱动）
 *
 * ★ 解决的问题：vehicle-info / health / energy / setting 这类页面结构都是
 *   「卡片 + 行（图标 + 标签 + 值）」，却各写了一份 HTML。现在只写一次渲染逻辑，
 *   各页只提供**行定义**（数据），从而：
 *     · 样式/结构改动只改一处
 *     · 新页面 = 写一份行定义（几十行而不是几百行）
 *     · 天然适配所有车型（行里放什么由能力/实体决定，见 `when`）
 *
 * 用法（页面里）：
 *   import { buildInfoPage } from './lixiang-info-page.js';
 *   buildInfoPage(this, {
 *     title: "车辆信息",
 *     cards: [
 *       { rows: [ {icon:"ic_home_control.webp", k:"车辆昵称", id:"v-name"}, ... ] }
 *     ],
 *     onFill: (q) => { q("#v-name").textContent = ...; }
 *   });
 *
 * ★ 兜底：拿不到 `lixiang-base.js` 时用内置最小样式（绝不白屏）。
 */

/**
 * @param {HTMLElement} host  自定义元素本身（shadow root 的宿主）
 * @param {object} cfg
 *   title    页面标题
 *   cards    [{ title?:string, rows:[{icon,k,id,na,mono,when}] }]
 *             when: 可选布尔（false 时整行不渲染 —— 用于「按能力/车型」显隐）
 *   onFill   (q, ctx) => void   渲染后填值（q = 选择器）
 *   fontBase/iconBase 可覆盖
 */
/**
 * 只渲染「卡片区」（行由数据定义）—— 供已有页面嵌入自己的外壳（保留 topbar/返回/toast）。
 * ★ 这是**渐进改造**的关键：先消除行标记的重复，外壳一个都不动。
 */
function renderCards(cfg) {
  cfg = cfg || {};
  const iconBase = cfg.iconBase || ICON_BASE_DEFAULT;
  return (cfg.cards || []).map(card => {
    const rows = (card.rows || [])
      .filter(r => r && (r.when == null || r.when === true))
      .map(r => `
        <div class="row${r.click ? " click" : ""}"${r.rowId ? ` id="${esc(r.rowId)}"` : ""}>
          ${r.icon ? `<img class="ic" src="${iconUrl(iconBase, r.icon)}" alt="" onerror="this.style.visibility='hidden'">` : `<span class="ic"></span>`}
          <span class="k">${esc(r.k)}</span>
          <span class="v${r.na ? " na" : ""}${r.mono ? " mono" : ""}" id="${esc(r.id || "")}">${esc(r.na || "—")}</span>
        </div>`).join("");
    return `<div class="card">${card.title ? `<div class="row"><span class="k muted">${esc(card.title)}</span></div>` : ""}${rows}</div>`;
  }).join("");
}
function buildInfoPage(host, cfg) {
  cfg = cfg || {};
  const iconBase = cfg.iconBase || ICON_BASE_DEFAULT;
  const fontBase = cfg.fontBase || FONT_BASE_DEFAULT;

  const cards = renderCards({ iconBase, cards: cfg.cards });

  const title = cfg.title
    ? `<div class="row" style="border-bottom:0"><span class="k" style="font-size:16px;font-weight:600">${esc(cfg.title)}</span></div>` : "";

  const root = host;
  root.innerHTML = `
    <style>${fontFaceCss(fontBase)}${BASE_CSS}</style>
    <div class="wrap">
      ${title}
      ${cards}
      <div id="lx-extra"></div>
    </div>`;

  if (typeof cfg.onFill === "function") {
    const q = s => root.querySelector(s);
    try {
      cfg.onFill(q, root);
    } catch (_) { /* 填值失败不应影响结构 */ }
  }
  return root;
}
  return { renderCards, buildInfoPage };
})();

/* ===================== lixiang-vehicle-info-page.js ===================== */
const { renderCards } = window.__LXB.info;
(function () {

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


/**
 * lixiang-vehicle-info-page —— 车辆信息（二级页）
 *   ★ 2026-10-12 修正：标题原为「车辆设置」，与首页入口「钥匙管理」、
 *     卡片名「车辆信息」三处不一致，车主反馈「钥匙管理显示的设置的内容」。
 *     现统一为「车辆信息」—— 因为内容就是车辆昵称/车牌/型号/车架号/软件版本。
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   卡1（4 行）：🚗车辆昵称 理想L6 / 🚗车牌号 浙A12345 /
 *                🚗车辆型号 理想L6 / Ⓥ车架号 HLX32XXXXXXXXXXXX
 *   卡2（2 行）：ⓘ车机版本 / OTA（版本 · 状态 · 进度）
 *
 * 数据源：
 *   ✅ 车辆昵称/型号 —— HA 设备注册表
 *   ✅ 车架号 —— 设备 serial_number
 *   ✅ 配置等级 / 辅助驾驶等级 —— 车辆配置实体属性
 *   ⚠️ 车牌号 —— 接口需特殊 token（100032），暂不可用
 *   ✅ 车机版本 / OTA —— head_unit_ver + ota_version/status/progress（2026-10-14 补）
 */

const CARD_TAG = "lixiang-vehicle-info-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-vehicle-info-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-vehicle-info-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:24px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; position:relative; }
  .back { width:34px; height:34px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center; cursor:pointer; }
  .back img { width:18px; height:18px; opacity:.7; }
  .topbar h1 { position:absolute; left:0; right:0; text-align:center;
               font-size:18px; font-weight:500; margin:0; pointer-events:none; }

  .card { margin:8px 16px 0; background:var(--lx-card); border-radius:18px;
          overflow:hidden; }
  .row { display:flex; align-items:center; gap:13px; padding:19px 18px;
         border-bottom:1px solid var(--lx-line); }
  .row:last-child { border-bottom:none; }
  .row .ic { width:24px; height:24px; opacity:.55; flex:0 0 auto; }
  .row .k { font-size:16px; }
  .row .v { margin-left:auto; font-size:15px; color:var(--lx-t3);
            font-family:"LxNum","Licium"; text-align:right; word-break:break-all;
            max-width:62%; }
  .row .v.mono { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:14px;
                 letter-spacing:.3px; }
  .row .v.na { font-size:13px; color:#C7C7CC; }
  .row.click { cursor:pointer; transition:background .15s; }
  .row.click:hover { background:rgba(0,0,0,.03); }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:80%; text-align:center; line-height:1.5; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangVehicleInfoPage extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._built = false; }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 10; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  /** 从设备注册表取车辆信息 */
  _vehicle() {
    const h = this._hass;
    const c = this._config || {};
    if (!h || !h.devices) return null;
    const vinWant = c.vin || "";
    for (const d of Object.values(h.devices)) {
      const isLi = (d.manufacturer || "").includes("理想")
        || JSON.stringify(d.identifiers || []).includes("lixiang");
      if (!isLi) continue;
      if (vinWant && !JSON.stringify(d.identifiers || []).includes(vinWant)) continue;
      return d;
    }
    return null;
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    root.innerHTML = `
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <h1>车辆信息</h1>
      </div>

      ${renderCards({
        iconBase: __iconBase,
        cards: [
          { rows: [
              { icon: "ic_home_control.webp",    k: "车辆昵称", id: "v-name" },
              { icon: "ic_home_control.webp",    k: "车牌号",   id: "v-plate", na: "暂不可用", rowId: "r-plate", click: true },
              { icon: "ic_home_control.webp",    k: "车辆型号", id: "v-model" },
              { icon: "ic_home_dialogue.png",    k: "车架号",   id: "v-vin", mono: true },
          ]},
          { rows: [
              // ★ 2026-10-14 修正：原来写死「暂不可用/集成未采集」，但集成确有
              //   `车机版本`（head_unit_ver）与 `OTA 版本/状态/进度` 实体。
              { icon: "ic_home_health.webp",     k: "整车软件版本", id: "v-sw" },
              { icon: "ic_home_update.webp",     k: "OTA",      id: "v-ota" },
          ]},
          { rows: [
              { icon: "ic_home_control.webp",    k: "配置等级",     id: "v-cfg" },
              { icon: "ic_home_navigation.webp", k: "辅助驾驶等级", id: "v-ad" },
          ]},
        ],
      })}
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    // 暂不可用的两项：点击说明原因
    const why = (msg) => () => this._toast(msg);
    const p1 = why("车牌号需要额外的接口令牌（当前返回 100032），集成暂无法读取");
    [["#r-plate", p1, "车牌号"]].forEach(([sel, fn, label]) => {
      const el = this.querySelector(sel); if (!el) return;
      this._a11y(el, label, fn);
      el.addEventListener("click", fn);
    });

    this._built = true;
  }

  _toast(msg) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show";
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 3200);
  }

  /**
   * 按需加载共享资源模块（`lixiang-assets.js`，与本页同目录）。
   * ★ 加载失败只影响「有没有车型图」，页面其余部分照常 —— 所以直接吞掉异常。
   */
  async _ensureAssets() {
    if (typeof window === "undefined") return null;
    if (window.LxAssets) return window.LxAssets;
    if (this.__assetsTried) return null;
    this.__assetsTried = true;
    try {
      const base = new URL(".", import.meta.url).href.replace(/\/$/, "");
      await import(base + "/lixiang-assets.js");
    } catch (_) { /* 同目录没有该模块（老安装）→ 退化 */ }
    return window.LxAssets || null;
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);
    const d = this._vehicle();
    const c = this._config || {};

    // ★ 车型剪影（资源层）：用户本地图 → 车系剪影 → 通用占位。
    //   资源模块没加载成功就什么都不显示（与改动前完全一致，绝不空屏/破图）。
    this._ensureAssets();
    try {
      const A = window.LxAssets;
      let box = q("#lx-car-box");
      const model = (d && d.model) || c.model_name || "";
      if (A && model) {
        if (!box) {
          box = document.createElement("div");
          box.id = "lx-car-box";
          box.style.cssText =
            "display:flex;justify-content:center;color:var(--lx-t3);margin:2px 0 10px;";
          this.prepend(box);
        }
        if (box.dataset.model !== model) {
          box.dataset.model = model;
          box.innerHTML = A.carImageHtml({ modelName: model });
        }
      }
    } catch (_) { /* 资源层不可用 → 忽略 */ }

    // 昵称 / 型号
    const nick = c.nickname || (d && d.name_by_user) || (d && d.name) || "—";
    q("#v-name").textContent = nick;
    q("#v-model").textContent = (d && d.model) || c.model_name || nick;

    // 车架号
    const vin = (d && d.serial_number) || c.vin
      || ((this._hass && this._hass.states && this._eid("battery"))
          ? "" : "");
    q("#v-vin").textContent = vin || "—";

    // ★ 2026-10-14：车机版本 / OTA（对齐官方 —— OTA 与软件版本都属车辆设置类二级页）
    // 本卡没有 _st 助手（那是首页卡的），用局部 S() 取状态
    const S = (id) => (id && this._hass && this._hass.states) ? this._hass.states[id] : null;
    const swEid = this._eid("head_unit_ver") || this._eid("ota_version");
    const swSt = swEid ? S(swEid) : null;
    q("#v-sw").textContent = (swSt && swSt.state && !["unknown", "unavailable"].includes(swSt.state))
      ? String(swSt.state) : "—";
    const oV = S(this._eid("ota_version"));
    const oS = S(this._eid("ota_status"));
    const oP = S(this._eid("ota_progress"));
    const ok = (x) => x && x.state && !["unknown", "unavailable"].includes(x.state);
    const ver = ok(oV) ? String(oV.state) : "";
    const pg = oP ? parseFloat(oP.state) : NaN;
    q("#v-ota").textContent = ok(oS)
      ? (String(oS.state) + (ver ? " · " + ver : "") + (pg > 0 && pg < 100 ? " " + Math.round(pg) + "%" : ""))
      : (ver || "—");

    // 配置等级 / 辅助驾驶（从「车辆配置」实体属性读）
    const cfgEid = this._eid("vehicle_cfg");
    const cfg = cfgEid && this._hass.states[cfgEid];
    if (cfg) {
      const a = cfg.attributes || {};
      q("#v-cfg").textContent = a["配置等级"] || cfg.state || "—";
      q("#v-ad").textContent = a["辅助驾驶"] || "—";
    } else {
      q("#v-cfg").textContent = "—";
      q("#v-ad").textContent = "—";
    }
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangVehicleInfoPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "车辆信息（二级页）",
  description: "车辆昵称/车牌/型号/车架号/软件版本/配置等级",
  preview: true,
});
})();

/* ===================== lixiang-app-home.js ===================== */
(function () {

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


/**
 * lixiang-app-home v3 —— 车控首页（严格对齐 App 截图 1260×2844 @3x = 420×948pt）
 *
 * 依据：实测截图 + 真实接口数据
 *   · 顶部：理想L6 | 162km 89% · 800km | 已驻车
 *   · 3D 车模：双态（展开大图 / 收起右上角缩略图）
 *   · 圆按钮 8 个（两排 ×4）：车锁/车窗/尾门/授权驾驶
 *                              直线召唤/寻车/充电口盖/后视镜加热
 *   · 收起箭头
 *   · 卡片行1：空调卡 | 位置卡
 *   · 卡片行2：本月陪伴里程+折线图 | 剩余电量 / 哨兵模式
 *   · 入口：车辆健康 | 任务大师 / 车辆信息 | 情景模式 / 车辆设置
 *   （★ 2026-10-12 按车主指示移除「服务专家」与「理想AD学习平台」）
 *   · 图标用 _lisa 粗线版
 */

const CARD_TAG = "lixiang-app-home";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
// ═══ ★ 卡片拖拽排序（2026-10-20）══════════════════════════════════
//   目标：允许用户在【卡片内部】拖动 .row2 里的卡片（空调 / 位置 / 里程 /
//        电量 / 哨兵）自由换位，顺序持久化到 localStorage。
//   设计要点：
//     · 只用原生 HTML5 drag & drop，不引第三方库（卡片要尽量轻）。
//     · 【长按 350ms 才进入拖拽】—— 否则会与卡片自身的点击冲突
//       （点空调卡要跳空调页，点位置卡要跳地图页）。
//     · 拖动时给占位提示；松手按新顺序写回 DOM 并保存。
//     · 提供 lxClearOrder()，用户拖乱后可恢复默认。
const LX_DRAG_STORE = "lx_apphome_order";
const LX_DRAG_HOLD_MS = 350;

/** 取当前实例的 localStorage（shadow DOM / 多实例下不依赖全局）。 */
function lxStore(row) {
  try {
    const win = (row && row.ownerDocument && row.ownerDocument.defaultView) || window;
    return win.localStorage || null;
  } catch (e) { return null; }
}

function lxLoadOrder(row) {
  try {
    const st = lxStore(row);
    if (!st) return null;
    const raw = st.getItem(LX_DRAG_STORE);
    if (!raw) return null;
    const arr = JSON.parse(raw);
    return Array.isArray(arr) && arr.length ? arr : null;
  } catch (e) { return null; }
}

function lxSaveOrder(ids, row) {
  try {
    const st = lxStore(row);
    if (st) st.setItem(LX_DRAG_STORE, JSON.stringify(ids));
  } catch (e) {}
}

function lxClearOrder(row) {
  try {
    const st = lxStore(row);
    if (st) st.removeItem(LX_DRAG_STORE);
  } catch (e) {}
}

/** 按已保存顺序重排某个 .row2 里的卡片；无保存则保持原样。 */
function lxApplyOrder(row) {
  const order = lxLoadOrder(row);
  if (!order || !row) return false;
  const cards = Array.from(row.querySelectorAll(":scope > .card"));
  if (!cards.length) return false;
  const byId = new Map(cards.map((c) => [c.id, c]));
  let touched = false;
  for (const id of order) {
    const el = byId.get(id);
    // 必须仍在 DOM 里（车型可能不支持该卡），否则跳过
    if (el) { row.appendChild(el); touched = true; }
  }
  return touched;
}

/** 给一个 .row2 容器挂上拖拽能力。 */
function lxEnableDragSort(row) {
  if (!row || row.__lxDrag) return;
  row.__lxDrag = true;
  let holdTimer = null;
  let drag = null;          // { card, x0, y0, dx, dy, placeholder, moved }

  const clearHold = () => {
    if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
  };

  // 拖动中：记录位移（★ 只在已进入拖动模式后才更新，不取消计时）
  const onMove = (ev) => {
    if (!drag) return;
    const dx = ev.clientX - drag.x0;
    const dy = ev.clientY - drag.y0;
    if (!drag.moved) {
      // 超过 6px 才认定为"拖动"（避免轻微抖动误判）
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
      drag.moved = true;
      drag.card.classList.add("lx-dragging");
      row.classList.add("lx-drop-active");
    }
    drag.dx = dx;
    drag.dy = dy;
    drag.card.style.transform = `translate(${dx}px, ${dy}px) scale(1.02)`;

    // ★ 找当前悬停的卡（允许跨 .row2 —— 两张卡区间可互换）
    //   ★ 用 row.ownerDocument 而非裸 document：shadow DOM / 多实例下更稳
    const doc = row.ownerDocument || document;
    const over = doc.elementFromPoint(ev.clientX, ev.clientY);
    const card = over && over.closest && over.closest(".card");
    if (!card || card === drag.card) return;
    const host = card.closest(".row2");
    if (!host) return;
    const box = card.getBoundingClientRect();
    const after = (ev.clientX - box.left) > box.width / 2;
    host.insertBefore(drag.card, after ? card.nextSibling : card);
    drag.host = host;
  };

  const onUp = () => {
    clearHold();
    if (!drag) return;
    const card = drag.card;
    const moved = drag.moved;
    // 复位视觉
    card.style.transform = "";
    card.classList.remove("lx-dragging");
    row.classList.remove("lx-drop-active");
    card.removeAttribute("draggable");
    drag = null;

    if (moved) {
      const ids = Array.from(row.querySelectorAll(":scope > .card"))
        .map((c) => c.id).filter(Boolean);
      lxSaveOrder(ids, row);
      const scope = row.closest(".root") || row.parentElement;
      if (scope && scope.querySelectorAll) {
        scope.querySelectorAll(".row2").forEach((r) => { if (r !== row) lxApplyOrder(r); });
      }
      try { navigator.vibrate && navigator.vibrate(8); } catch (e) {}
    }
  };

  row.addEventListener("pointerdown", (ev) => {
    if (ev.button != null && ev.button !== 0) return;
    const card = ev.target.closest(".card");
    if (!card || !row.contains(card)) return;
    clearHold();
    holdTimer = setTimeout(() => {
      holdTimer = null;
      drag = { card, host: row, x0: ev.clientX, y0: ev.clientY, dx: 0, dy: 0, moved: false };
      card.setAttribute("draggable", "false");   // ★ 禁掉原生拖拽，交给我们自己
      card.style.willChange = "transform";
      try { navigator.vibrate && navigator.vibrate(12); } catch (e) {}
    }, LX_DRAG_HOLD_MS);
  });

  // ★★ 关键修正：pointermove/up 绑在【window】上
  //    · 拖动时手指可能移出卡片区 → 只有 window 能持续收到事件
  //    · pointermove 不再 clearHold（那会导致永远拖不起来）
  window.addEventListener("pointermove", onMove, { passive: true });
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointercancel", onUp);
}

function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖
const __fontFallback = BUILTIN_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }

  lixiang-app-home { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-app-home { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  /* 2026-10-12：兜底 —— 长内容不得撑破视口（车主："手机上右边溢出"）。
     真正修复是把 grid 列改成 minmax(0,1fr)；这里再加一道保险。
     ★★ 必须 clip，不能 hidden（2026-10-13 实测）：overflow-x:hidden 会把
        overflow-y 计算成 auto → lixiang-app-home/.root 成为滚动容器 → 里面的
        .head{position:sticky} 被困住，「抬头固定」直接失效（滚动后抬头消失）。
        clip 同样裁剪但【不创建滚动容器】。别再改回 hidden。 */
  lixiang-app-home { display:block; max-width:100%; overflow-x:clip; }
  .wrap > *, .row2 > *, .entries > *, .quick > * { min-width:0; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:14px; overflow-x:clip;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif;
    -webkit-tap-highlight-color:transparent; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  /* ★ 2026-10-09（用户要求）：抬头固定 —— 滚动时头部（车型/续航/状态）不再消失。
     · .head 粘顶；粘顶后收紧成单行 + 隐藏缩略 3D，避免固定头部占掉半屏
     · ★★ 避让 HA 顶栏：HA 的顶栏是 position:fixed 覆盖在内容之上的
       （窄屏尤其明显，内容会滑到顶栏下面）。若只写 top:0，我们的抬头会
       **被 HA 顶栏盖住**（用户反馈："抬头还是会被遮挡"）。
       所以粘顶位置取 --lx-head-top，由 JS 按实测布局算出：
         · 滚动容器顶边在视口顶端（=顶栏覆盖式布局）→ 需要避让 --header-height
         · 顶栏被 HA 自动隐藏时（窄屏下滚）→ 归零，否则会留一条空白
         · 滚动容器顶边已在顶栏之下（桌面布局）→ 归零，不需要避让 */
  .head { position:sticky; top:var(--lx-head-top, 0px); z-index:30; background:var(--lx-bg);
          padding:8px 20px 0;
          transition:top .18s ease, box-shadow .2s, padding .2s, background .2s; }
  .root.stuck .head { padding-bottom:8px; border-bottom:1px solid var(--lx-line);
          box-shadow:0 6px 16px rgba(0,0,0,.06); }
  .root.stuck .head .hrow { align-items:center; }
    /* ★ 2026-10-13：这里原为 baseline —— 与右侧 96px 高的小车图同排时，
       基线对齐会把标题压到小车图底边（左上留一大块空白，看着像被遮挡）。
       标题/续航之间的基线对齐由 .hleft 自己负责，这一层用 center。 */
  .root.stuck .head .hleft { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
  .root.stuck .head .title { font-size:18px; line-height:1.25; }
  .root.stuck .head .ranges { margin-top:0; gap:10px; }
  .root.stuck .head .parked { margin-top:0; font-size:12px; }
  /* 插枪徽标（插电时显示） */
  /* ★ 头部徽标：告警（琥珀）/ 哨兵（蓝） */
  .badge { display:inline-flex; align-items:center; gap:3px; margin-left:6px;
           vertical-align:middle; font-size:11px; padding:2px 7px; border-radius:8px; }
  .badge img { width:12px; height:12px; }
  .badge.warn { color:#8A5300; background:rgba(232,163,60,.16); }
  .badge-sentry { color:#0A58F6; background:rgba(10,88,246,.10); }
  /* ★ 地图卡拍照按钮（官方 HomeControlMapPhoto） */
  .loc .map .shot { position:absolute; right:8px; top:50%; transform:translateY(-50%);
                    width:34px; height:34px; border-radius:50%; background:#fff; border:0;
                    display:flex; align-items:center; justify-content:center; cursor:pointer;
                    box-shadow:0 2px 8px rgba(16,20,28,.2); padding:0; }
  .loc .map .shot img { width:18px; height:18px; }
  /* ★ 空调卡座椅插图（官方布局：右下角、不抢文字） */
  .ac .seatart { position:absolute; right:-6px; bottom:-10px; width:104px; height:110px;
                      opacity:.9; pointer-events:none; }
  .plug { display:inline-flex; align-items:center; gap:3px; margin-left:8px;
          vertical-align:middle; font-size:11px; padding:2px 7px; border-radius:8px;
          color:#0A7B3E; background:rgba(10,123,62,.10); }
  .plug img { width:12px; height:12px; display:block; }
  .plug b { font-weight:500; }
  [data-theme="dark"] .plug { color:#30D158; background:rgba(48,209,88,.14); }
  /* ★★ 2026-10-12 删除 '.root.stuck .head .mini { display:none }'：
     它与「上滑收起成大图旁边的小图」的设计**直接冲突**，而且优先级更高
     （3 个类 vs '.root.collapsed3d .mini' 只有 2 个类）——
     结果是**一滚动小图就消失**，车主反馈「标题抬头固定做的不是很好」。
     现在粘顶时保留小图（这才是 App 的行为）。 */
  .hrow { display:flex; align-items:flex-start; gap:10px; }
  .hleft { flex:1; min-width:0; }
  .title { font-size:25px; font-weight:600; letter-spacing:.2px; line-height:1.15; }
  .ranges { display:flex; align-items:baseline; gap:14px; margin-top:8px; flex-wrap:wrap; }
  .rg { display:flex; align-items:baseline; gap:4px; }
  .rg img { width:17px; height:17px; transform:translateY(2px); }
  .rg .v { font-family:"LxNum",sans-serif; font-size:17px; font-weight:600; }
  .rg .v.na { color:var(--lx-t3); font-size:15px; }
  .rg .u { font-size:12px; color:var(--lx-t3); }
  .parked { font-size:14px; color:var(--lx-t3); margin-top:5px; }
  .mini { width:150px; height:96px; flex:0 0 auto; border-radius:12px;
          overflow:hidden; display:none; align-items:center; justify-content:center;
          cursor:pointer; transition:transform .15s; }
  .mini:hover { transform:scale(1.03); }
  .mini iframe { width:100%; height:100%; border:0; }
  .mini img { width:100%; height:100%; object-fit:contain; }
  .root.collapsed3d .mini { display:flex; }

  .big3d { margin:8px 20px 0; border-radius:18px; overflow:hidden;
           background:linear-gradient(175deg,#FBFBFD 0%,#F1F1F5 100%);
           height:0; opacity:0; transition:height .3s cubic-bezier(.25,.8,.25,1), opacity .2s; }
  /* 展开态：由 .root 上的 .expanded3d 类控制（不用 :not() 避免优先级陷阱）*/
  .root.expanded3d .big3d { height:270px; opacity:1; }
  .root.expanded3d { --lx-3d-h: 260px; }
  .big3d iframe { width:100%; height:100%; border:0; display:block; }
  .big3d, .big3d iframe { touch-action:none; }
  /* ★ 2026-10-14：车图缩到 84% 宽、居中 → 两侧各有约 8% 留白，
     胎压标签放进留白里（车主："胎压还在车子上"）。 */
  /* 必须 display:block —— 否则 img 是行内元素，margin:auto 不居中（实测左侧 0 留白） */
  .big3d img { display:block; width:84%; margin:0 auto; height:100%; object-fit:contain; object-position:50% 62%; }

  /* minmax(0,1fr)：裸 1fr 的默认 min-width:auto 会让长内容撑破容器 → 手机右侧溢出 */
  .quick { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:6px;
           padding:18px 12px 0; }
  /* ★ 车型无快捷功能时的空态（2026-10-11） */
  .qempty { grid-column:1/-1; padding:22px 10px; text-align:center;
            color:var(--lx-t3,#9A9A9A); font-size:13px; }
  .q { display:flex; flex-direction:column; align-items:center; gap:8px;
       min-height:52px; padding:6px 0 4px; border-radius:16px; cursor:pointer;
       position:relative; transition:background .15s; }
  .q:hover { background:var(--lx-card); }
  .q:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .q .c { width:56px; height:56px; border-radius:50%; background:var(--lx-bg);
          border:1.5px solid var(--lx-line); display:flex; align-items:center;
          justify-content:center; transition:transform .13s, border-color .18s, box-shadow .18s; }
  .q:hover .c { border-color:#D8D8DC; box-shadow:0 2px 10px rgba(0,0,0,.06); }
  .q:active .c { transform:scale(.9); }
  .q .c img { width:28px; height:28px; pointer-events:none; }
  .q .n { font-size:12px; color:var(--lx-t2); line-height:1.1; }
  /* ★ 2026-10-14 官方同款：激活 = 实心深色圆（配官方白色 *_on_* 图标）；
     未激活 = 空心圆（配深色线稿图标）。原来是"蓝圈+浅蓝底"，与官方不一致。 */
  .q.on .c { border-color:#1b1f27; background:#1b1f27; box-shadow:0 2px 10px rgba(16,20,28,.22); }
  .q.on .n { color:#111418; font-weight:600; }
  .q.busy .c { border-color:var(--lx-blue); }
  .q .sp { position:absolute; top:16px; width:26px; height:26px; border-radius:50%;
           border:2.5px solid rgba(10,88,246,.2); border-top-color:var(--lx-blue);
           animation:spin .7s linear infinite; display:none; }
  .q.busy .sp { display:block; }
  .q.busy .c img { opacity:.25; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .q.dim { opacity:.35; cursor:not-allowed; }
  .q.dim:hover { background:transparent; }
  .q .sub { position:absolute; bottom:-2px; font-size:9px; color:var(--lx-blue);
            opacity:0; transition:opacity .2s; white-space:nowrap; }
  .q.done .sub { opacity:1; }

  .chev { display:flex; justify-content:center; padding:10px 0 2px; cursor:pointer; }
  .chev img { width:22px; height:22px; opacity:.55; transition:transform .25s; }
  .root.collapsed3d .chev img { transform:rotate(180deg); }
  /* ★ 2026-10-16 车主（两次澄清后定稿）：
       「小箭头不是收齐车模的功能，是展开和收齐快捷键的功能。
         比如有车可能有 8 个快捷，那么小箭头就可以展开更多。
         车模是上滑收起，下拉展开。」
     → 默认只显示**第一行 4 个**快捷键；按小箭头展开「更多」（全部可用项），
       再按收起。车模完全不归它管 —— 车模只由滚动（上滑收起/下拉展开）驱动；
       右上角小车图是车模自己的开关。
     → 可用项 ≤4 时箭头无意义，_renderQuick 里会把它藏起来。 */
  .root:not(.quick-open) .quick > .q:nth-child(n+5) { display:none; }
  .root.quick-open .chev img { transform:rotate(180deg); }

  .wrap { padding:12px 20px 0; display:grid; gap:12px; }
  .row2 { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
  .card { background:var(--lx-card); border-radius:18px; padding:16px;
          cursor:pointer; transition:transform .13s, box-shadow .18s; position:relative; }
  .card:hover { box-shadow:0 3px 14px rgba(0,0,0,.07); }
  .card:active { transform:scale(.985); }
  .card:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .card .lbl { font-size:13px; color:var(--lx-t3); }
  /* ★ 2026-10-12：卡片高度对齐 App。
     从车主截图量得：温度卡/位置卡约 180x183（**近正方形**）、里程卡约 180x213。
     此前写死 150px → 卡片偏扁（比 App 矮约 20%）。改用 clamp 随视口缩放，
     窄屏不过高、宽屏不过矮。 */
  .ac { min-height:clamp(168px, 46vw, 200px); display:flex; flex-direction:column;
        justify-content:space-between; 
             position:relative; overflow:hidden; }
  .ac .temp { font-family:"LxNum"; font-size:30px; font-weight:600; line-height:1.1; }
  .ac .temp sup { font-size:15px; font-weight:500; }
  .ac .target { font-size:11.5px; color:var(--lx-t3); margin-top:3px; }
  /* 风扇：右上角标（不占布局空间）*/
  .ac .fan { position:absolute; right:14px; top:14px; width:34px; height:34px;
             border-radius:50%; background:var(--lx-bg); display:flex;
             align-items:center; justify-content:center;
             box-shadow:0 1px 4px rgba(0,0,0,.06); }
  .ac .fan img { width:18px; height:18px; }
  /* ★ 2026-10-14 官方同款：空调开启时风扇 **蓝底 + 白图标 + 转动**。
     官方资源本就是配套的：ic_home_fan_off = 深灰(浅底)、ic_home_fan_on = 纯白(蓝底)。 */
  .ac .fan.on { background:var(--lx-blue); box-shadow:0 2px 10px rgba(10,88,246,.35); }
  .ac .fan.on img { animation:spin 1.6s linear infinite; }
  .ac .fan.spin img { animation:spin 1.6s linear infinite; }
  /* 功能 chip：单行等分，不换行 */
  .ac .acrow { display:flex; gap:5px; margin-top:10px; }
  .ac .chip { flex:1; display:inline-flex; align-items:center; justify-content:center;
              gap:3px; font-size:10.5px; padding:5px 2px; border-radius:8px;
              background:var(--lx-bg); color:var(--lx-t3);
              border:1px solid var(--lx-line); transition:.2s; white-space:nowrap; }
  .ac .chip img { width:12px; height:12px; opacity:.7; flex:0 0 auto; }
  .ac .chip.on { background:rgba(10,88,246,.08); border-color:var(--lx-blue);
                 color:var(--lx-blue); }
  .ac .chip.on img { opacity:1; }
  .loc { min-height:clamp(168px, 46vw, 200px); display:flex; flex-direction:column;
         overflow:hidden; }
  .loc .map { flex:1; border-radius:12px; background:#E8EEF4; overflow:hidden;
              position:relative; min-height:clamp(96px, 26vw, 120px); }
  .loc .map iframe { width:100%; height:100%; border:0; }
  /* ── 自建地图（高德瓦片，免 key/免登录）── */
  .loc .map .tiles { position:absolute; inset:0; overflow:hidden; cursor:pointer; }
  .loc .map .tiles img { position:absolute; width:256px; height:256px;
                         user-select:none; pointer-events:none; }
  /* 车标：小车图形（对齐 App），小尺寸表达"车辆位置" */
  .loc .map .puck { position:absolute; width:18px; height:18px; margin:-9px 0 0 -9px;
                    display:flex; align-items:center; justify-content:center;
                    pointer-events:none; z-index:3; }
  .loc .map .puck img { width:18px; height:18px;
                        filter:drop-shadow(0 1px 3px rgba(0,0,0,.4)); }
  .loc .map .ph { position:absolute; inset:0; display:flex; flex-direction:column;
                  align-items:center; justify-content:center; text-align:center;
                  font-size:11px; color:var(--lx-t3); line-height:1.5; padding:0 12px; }
  .loc .addr { display:flex; align-items:flex-start; gap:6px; margin-top:10px; }
  .loc .addr img { width:15px; height:15px; flex:0 0 auto; margin-top:2px; }
  .loc .addr span { font-size:12.5px; color:var(--lx-t2); line-height:1.4;
                    display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
                    overflow:hidden; }
  /* 里程卡比上排略高（App 约 213px）—— 右列是「电量 + 哨兵」两张堆叠 */
  .mile { min-height:clamp(196px, 54vw, 232px); }
  .mile .big { font-family:"LxNum","Licium"; font-size:30px; font-weight:600; line-height:1.1; }
  .mile .big small { font-size:14px; font-weight:500; color:var(--lx-t2); margin-left:3px; }
  .mile .cap { font-size:13px; color:var(--lx-t3); margin-top:4px; }
  .mile .chart { margin-top:10px; height:46px; position:relative; }
  .mile .chart::after { content:""; position:absolute; left:0; right:0; bottom:0;
                        height:1px; background:var(--lx-line); }
  .mile .chart svg { width:100%; height:100%; display:block; }
  /* ★ 柱状图（对齐 App）：每个数据点一根等宽柱子 */
  #sparkbars rect { fill:#9A9AA0; }
  #sparkbars rect[data-zero] { fill:transparent; }     /* 0 值不画柱子（不留脏点） */
  #sparkgrid line { stroke:var(--lx-line); stroke-width:0.4; }
  .mile .axis { display:flex; justify-content:space-between; font-size:10px;
                color:var(--lx-t3); margin-top:3px; }
  .batt .row { display:flex; align-items:center; gap:9px; }
  /* 充电中的剩余时间（App 同款：小字 + 闪电） */
  .batt .batt-remain { display:flex; align-items:center; gap:4px; margin-top:6px;
                       font-size:12px; color:var(--lx-t2); }
  .batt .batt-remain .ic { font-size:11px; }
  .batt .row img { width:26px; height:26px; }
  .batt .big { font-family:"LxNum","Licium"; font-size:28px; font-weight:600; line-height:1.05; }
  .batt .big small { font-size:15px; font-weight:500; color:var(--lx-t2); }
  .sentry { display:flex; align-items:center; gap:12px; min-height:76px; }
  .sentry img { width:26px; height:26px; }
  .sentry .t { font-size:15px; }
  .sentry .s { font-size:12px; color:var(--lx-t3); margin-top:3px; }
  .sentry.on .t { color:var(--lx-blue); }

  .entries { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
  .entry { background:var(--lx-card); border-radius:18px; padding:16px;
           display:flex; align-items:center; gap:12px; cursor:pointer;
           min-height:64px; transition:transform .13s, box-shadow .18s; }
  .entry:hover { box-shadow:0 3px 14px rgba(0,0,0,.07); }
  .entry:active { transform:scale(.985); }
  .entry:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .entry img.ic { width:24px; height:24px; flex:0 0 auto; }
  .entry .tx { min-width:0; }
  .entry .nm { font-size:15px; line-height:1.2; }
  .entry .sd { font-size:12px; color:var(--lx-t3); margin-top:3px; }

  .big { background:var(--lx-card); border-radius:18px; padding:18px 16px; }
  .divider { height:1px; background:var(--lx-line); margin:16px 0; }

  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           white-space:nowrap; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.err { background:rgba(200,40,40,.92); }
  .toast.ok { background:rgba(28,150,70,.92); }

  /* ── 键盘可达：统一焦点样式（无障碍）── */
  [role="button"]:focus-visible, .card:focus-visible, .entry:focus-visible,
  .row.click:focus-visible, .m:focus-visible, .yhead:focus-visible,
  .year .yhead:focus-visible, button:focus-visible, input:focus-visible {
    outline: 2px solid var(--lx-blue, #0A58F6);
    outline-offset: 2px;
    border-radius: 8px;
  }
  /* 尊重「减少动态效果」偏好 */
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
  }

  /* ── 低电量告警 ── */
  .lowbat { margin:8px 20px 0; padding:11px 14px; border-radius:12px;
            display:flex; align-items:center; gap:9px; font-size:12.5px;
            background:rgba(255,149,0,.1); color:#B36B00; line-height:1.45; }
  .lowbat.crit { background:rgba(255,59,48,.1); color:#C0271D; }
  .lowbat img { width:17px; height:17px; flex:0 0 auto; }
  .lowbat b { font-family:"LxNum"; font-size:14px; }
  /* 电量数字着色 */
  .rg .v.low { color:#FF9500; }
  .rg .v.crit { color:#FF3B30; }
  /* 3D 加载中/失败占位 */
  .big3d .ph { position:absolute; inset:0; display:flex; flex-direction:column;
               align-items:center; justify-content:center; gap:8px;
               font-size:12px; color:var(--lx-t3); }
  .big3d { position:relative; }
  /* ★ 2026-10-14：胎压叠在车图四个轮子旁（车主要求）。
     位置由 JS 按"车图实际渲染区域"计算（见 _layoutTires），不用百分比硬套盒子，
     因为车图是 object-fit:contain + object-position:50% 62%，并不铺满盒子。 */
  .big3d .tires { position:absolute; inset:0; pointer-events:none; }
  .big3d .tp { position:absolute; transform:translate(-50%,-50%); padding:1px 5px;
               border-radius:8px; background:#0d1828cc; border:1px solid #ffffff1f;
               font-size:11px; font-weight:600; color:#eaf1fb; white-space:nowrap; }
  /* ★ 官方同款二次确认弹框 */
  .cfm { position:fixed; inset:0; z-index:99; background:rgba(16,20,28,.45);
         display:flex; align-items:center; justify-content:center; padding:24px; }
  .cfm-box { width:100%; max-width:340px; background:#fff; border-radius:20px;
             padding:24px 20px 16px; box-shadow:0 18px 50px rgba(10,14,22,.28); }
  .cfm-text { font-size:16px; line-height:1.55; color:#111418; text-align:center; font-weight:500; }
  .cfm-row { display:flex; gap:12px; margin-top:22px; }
  .cfm-row button { flex:1; height:46px; border-radius:23px; font-size:16px; font-weight:600;
                    border:1px solid #e3e6ea; background:#fff; color:#111418; cursor:pointer; }
  .cfm-row .cfm-yes { background:#1b1f27; border-color:#1b1f27; color:#fff; }
  .cfm-rem { display:flex; align-items:center; justify-content:center; gap:6px;
             margin-top:14px; font-size:13px; color:#6b7480; }
  .big3d .tp small { font-size:9px; font-weight:400; opacity:.75; margin-left:1px; }
  .big3d .tp.low { background:#4a3410cc; border-color:#e8b96b55; color:#f2c98a; }
  .big3d .ph .spin2 { width:22px; height:22px; border-radius:50%;
               border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
               animation:spin .8s linear infinite; }

    /* ── 手机断点（≤480px，容器查询）──────────────────────────────
       ★ 2026-10-14：v1.5.7 的提交说明声称加过这段，但 diff 里只改了 11 张
         页面卡，app-home **从未真正加上** —— 断点一直不存在。
         同时 container-type 必须挂在 .root（真实元素）上：
         light DOM 里写在 lixiang-app-home 上的 container-type 不生效，容器查询不会触发。 */
    @container (max-width: 480px) {
      /* ★ 2026-10-14 车主："为什么下面是一列了？"
         官方在手机宽度：下方两张卡**并排**、入口瓦片**一行两个**、
         快捷按钮**一行 4 个**。原来这里把 .row2/.entries 收成一列是我定错了。
         全部移除，只在极窄（≤330px）才收。 */
      .head { padding-left:14px; padding-right:14px; }
      .wrap { padding-left:14px; padding-right:14px; }
      /* ★ 2026-10-16 车主（截图）：「车模都右上角了，中间车模地方空着了，没收起来」
         原来是 ".big3d, .root.expanded3d .big3d { height:188px }" —— 裸 .big3d
         把收起态的 height:0 盖掉了，于是收起后仍占 188px 空白。
         收起态就该完全塌陷，所以这里只留展开态选择器。 */
      .root.expanded3d .big3d { height: 188px; }
      .mini { width:118px; height:78px; }
    }

    /* ★ 2026-10-14：快捷键只在**很窄**时才收成 2 列。
       原来写在 ≤480px 里 —— 容器查询修好后（v1.5.10）它在 460~490px 的
       desktop 栏里也命中，车主反馈"一行只有 2 个"。App 本体在 420pt 仍是 4 列，
       所以阈值下调到 400px（约等于手机竖屏可用宽度以下）。 */
      /* ★ 2026-10-20：330px → 340px（按官方截图对齐，18px 余量）
         维护者反馈「其他用户是一列，我们是两列」。
         最强证据 = 官方 App 手机宽度实测（容器 ≈358px）：
         快捷 4 个 / 两卡并排 / 瓦片 2 个 —— 全部保持多列。
         而旧阈值 330px【本该低于 358px】却仍让 358 落在阈值之下，
         于是 .quick 收 2 列、.row2 收 1 列 ⇒ 看起来「一列」。
         ⇒ 340px 保证 358px 宽度不命中，与官方一致。 */
    /* ── ★ 卡片拖拽排序（2026-10-20）────────────────────────────
       长按 350ms 抓起某张卡 → 拖到目标位置松手 → 顺序保存。
       · .lx-dragging  被拖起的卡：半透明 + 抬起阴影（跟手）
       · .lx-dragover  悬停位置：插入线提示（比方块更轻，不遮挡内容） */
    .card.lx-dragging {
      opacity:.72; transform:scale(.985);
      filter:drop-shadow(0 6px 16px rgba(0,0,0,.22));
      cursor:grabbing;
    }
    .card.lx-dragging * { pointer-events:none; }
    /* 拖拽中的插入提示线 */
    .row2.lx-drop-active { position:relative; }
    .row2.lx-drop-active::after {
      content:""; position:absolute; inset:0; pointer-events:none;
      outline:2px dashed rgba(0,114,255,.35); outline-offset:2px;
      border-radius:12px;
    }
    /* 触屏上禁止长按选中/放大镜，否则会跟拖拽打架 */
    .row2 > .card { -webkit-user-select:none; user-select:none;
                    -webkit-touch-callout:none; }

    @container (max-width: 340px) {
      .quick { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .row2 { grid-template-columns: minmax(0,1fr); }
      .entries { grid-template-columns: minmax(0,1fr); }
    }
`;

// ★ 2026-10-11 车型适配：QUICK 是数据表，但**不再无条件全部渲染** ——
//   渲染前先问 _supports(it)：该功能对应的实体在这台车上不存在 → 整块不显示。
//   理由：之前不支持的车也会出现入口，点了只提示"该功能尚未接入"（体验差，
//   而且用户会以为集成坏了）。实体存在性由**服务端能力门控**决定，不是前端猜车型。
const QUICK = [
  // ★ 2026-10-14 车主（两次澄清）：
  //   1) "所有的按键变化都是这样的" → 2) "我说的是空心圆和实心圆的变化"。
  //   即状态用**圆圈**表达：未激活 = 空心圆 + 深色线稿图标；
  //   激活 = **实心深色圆** + 白色图标（官方图资本来就是配套的：
  //   *_off_* 是深色线稿、*_on_* 是纯白，正好配实心圆）。
  //   标签默认保持动作名；仅官方截图已证实的「授权驾驶 → 已授权」带 onName。
  { key:"lock",   name:"车锁",   off:"ic_home_lock_off_lisa.png",      on:"ic_home_lock_open_lisa.png" },
  { key:"window", name:"车窗",   off:"ic_home_window_off_lisa.png",    on:"ic_home_window_on_lisa.png" },
  { key:"trunk",  name:"尾门",   off:"ic_home_tail_w_off_2025.png",    on:"ic_home_tail_w_on_2025.png" },
  // ★ 2026-10-09：授权驾驶是【动作】（button，cmdKey=remoteVehAuth），
  //   可执行实体与状态显示实体分开：auth=动作，stateField=授权状态。
  // ★ 2026-10-14 对照官方 App「车控」页截图修正：
  //   官方在这里的按钮是 8 个（4×2），第 4 个在**已授权**时标签变成「已授权」+ 实心黑圆。
  //   也就是说：状态**要**显示，但**标签必须跟着变** —— 只高亮而不改标签，
  //   用户看到的就是"授权驾驶一直开着"（车主的疑问）。
  // 官方 I18N（VehicleHomeControl）：authorization=授权驾驶 / alreadyAuthorization=已授权 /
  // alreadyStart=已启动 / dismiss=不再提醒 → 授权按钮有**两态**且动作前要**二次确认**。
  // ★ 2026-10-17 车主：「已授权怎么一直显示？app 上显示是授权驾驶」
  //   根因：我们用 `Vehicle.Provision.Authorize.State`（binary_sensor.车辆授权）
  //   当"是否已授权"的依据 —— 那个是**这台车与账号的绑定关系，长期为 on**，
  //   于是标签永远变「已授权」。
  //   官方包证据：它用的是 **LXVehicleBLEConnectState**（'bleConnected'/
  //   'bleConnectionStatus'，共 55/78 处引用）—— **蓝牙连接状态**，一次性的，
  //   下车/断连就失效；我们集成**没有** BLE 信号，无法复现。
  //   → 拿不到真实依据就不假装有：去掉 onName，始终显示官方动作名「授权驾驶」。
  //   （点击下发不受影响 —— 它本来就是动作按钮 remoteVehAuth。）
  //   同样去掉 stateField（原本指向 binary_sensor.车辆授权）：没有真实 BLE 依据时
  //   **连圆点也不该常亮**（官方只有 bleConnected 为真才高亮）。
  { key:"auth",   name:"授权驾驶", startedName:"已启动",
    confirm:"请在 2 分钟内上车并踩下刹车踏板，下车后请远程上锁。",
    remember:true,
    off:"ic_home_authorization_off_lisa.png",  on:"ic_home_authorization_on_lisa.png" },
  { key:"summon", name:"直线召唤", unsupported:true, note:"命令走 JOB 通道，HTTP 不可达",
    off:"ic_home_parkingout_off_lisa.png",     on:"ic_home_parkingout_on_lisa.png" },
  { key:"find",   name:"寻车",       off:"ic_summon_lisa.png",                  on:"ic_summon_lisa.png" },
  // optimMs：充电盖开合需数秒、状态回读慢 → 乐观值多留一会儿
  { key:"port",   name:"充电口盖", optimMs:12000,
    off:"ic_home_chrgporlid_off_lisa.png",     on:"ic_home_chrgporlid_on_lisa.png" },
  // optimMs：后视镜加热是 App 侧 660s 长命令，VSS 回读更慢
  { key:"mirror", name:"后视镜加热", optimMs:60000,
    off:"ic_home_rearmirroheat_off_lisa.png",  on:"ic_home_rearmirroheat_on_lisa.png" },
];

const FALLBACK = {
  "ic_home_tail_w_off_2025.png":"ic_home_tail_off_2025.png",
  "ic_home_tail_w_on_2025.png":"ic_home_tail_on_2025.png",
};

class LixiangAppHome extends HTMLElement {

  /** 让元素键盘可达（无障碍）：role/tabindex/aria-label + Enter/Space */
  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault(); e.stopPropagation(); handler(e);
      }
    });
  }

  /**
   * 自动绑定实体（用户不用手填 90 个 ID）。
   *   配置：vin（可选）—— 留空则认领第一辆理想车
   *   手填字段仍然优先（向后兼容）
   */
  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) {
        out = new AB(this._hass, this._config || {}).resolve() || {};
      }
    } catch (e) { /* 引擎不可用时退回手填 */ }
    // ★ 只有非空结果才缓存：hass.entities 未就绪时返回 {} ，
    //   若缓存会导致永久空绑定（真实踩过的坑）
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  /** 取实体：手填配置 > 自动发现 */
  _eid(field) {
    const c = this._config || {};
    const manual = c[field];
    if (typeof manual === "string" && manual.includes(".")) return manual;
    return (this._autoBind() || {})[field] || null;
  }

  /** 嵌套组（quick / switches / numbers …）也支持自动发现 */
  _eidIn(group, key) {
    const c = this._config || {};
    const m = (c[group] || {})[key];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[key] || null;
  }

  /**
   * 该快捷功能在这台车上是否可用（车型适配的第一道门）。
   * ★ 判据 = **实体是否真实存在**（服务端已按车型能力门控），
   *   前端不猜车型、不维护车型→功能的映射表。
   * @param {boolean} warmup 首帧可能还没拿到全部实体 → 放宽，避免闪烁
   */
  _supports(def, warmup) {
    // 明确标注"集成暂未支持"的（如直线召唤走 JOB 通道）→ 不显示，
    // 避免给用户一个必然失败的入口。
    if (def.unsupported) return false;
    const eid = this._eidIn("quick", def.key);
    if (!eid) return false;
    if (this._st(eid)) return true;
    // 首帧/刷新瞬间实体表可能未就绪：只要配置里**声明过**就先渲染，等回读再隐藏
    if (warmup) {
      const cfgMap = (this._config || {}).quick || {};
      return typeof cfgMap[def.key] === "string" || !!(cfgMap[def.key] || {}).entity;
    }
    return false;
  }

  /**
   * 车型识别（读 HA 设备注册表，避免硬编码）。
   * 返回 {name, model, series}
   */
  _detectModel() {
    if (this._modelCache !== undefined) return this._modelCache;
    const c = this._config || {};
    if (c.model_name) {
      this._modelCache = { name: c.model_name, model: c.model_name,
                           series: this._seriesOf(c.model_name) };
      return this._modelCache;
    }
    const h = this._hass;
    let out = null;
    if (h && h.devices) {
      const vin = c.vin || "";
      for (const d of Object.values(h.devices)) {
        const isLi = (d.manufacturer || "").includes("理想")
          || JSON.stringify(d.identifiers || []).includes("lixiang");
        if (!isLi) continue;
        if (vin && !JSON.stringify(d.identifiers || []).includes(vin)) continue;
        const mdl = d.model || d.name || "";
        out = { name: d.name || mdl, model: mdl, series: this._seriesOf(mdl) };
        break;
      }
    }
    this._modelCache = out;
    return out;
  }

  /** 车系代号（L6/L7/L8/L9/MEGA/i8） */
  _seriesOf(text) {
    const m = String(text || "").match(/(MEGA|L[6-9]|i[6-9]|ONE)/i);
    return m ? m[1].toUpperCase() : "";
  }

  /** 车型能力（优先实体属性「车型能力」，其次按车系兜底） */
  _modelCaps() {
    if (this._capsCache) return this._capsCache;
    const h = this._hass;
    let caps = null;
    if (h) {
      const probe = this._eid("battery") || this._eid("month_km");
      if (probe && h.states[probe] && h.states[probe].attributes["车型能力"]) {
        caps = h.states[probe].attributes["车型能力"];
      }
      if (!caps) {
        for (const id of Object.keys(h.states)) {
          if (id.indexOf("li_auto") < 0 && id.indexOf("li_xiang") < 0) continue;
          const a = h.states[id].attributes || {};
          if (a["车型能力"]) { caps = a["车型能力"]; break; }
        }
      }
    }
    if (caps && Object.keys(caps).length) { this._capsCache = caps; return caps; }
    // 兜底：按车系推断（保守，宁可多显示也不误隐藏）
    const series = (this._detectModel() || {}).series || "";
    const base = { 三排座椅: false, 冰箱: false, 侧滑门: false, 空气悬架: false };
    const by = { L6: {}, L7: { 冰箱: true }, L8: { 三排座椅: true, 冰箱: true },
                 L9: { 三排座椅: true, 冰箱: true, 空气悬架: true },
                 MEGA: { 三排座椅: true, 冰箱: true, 侧滑门: true, 空气悬架: true } };
    this._capsCache = Object.assign({}, base, by[series] || {});
    return this._capsCache;
  }

  setConfig(config) {
    if (!config) throw new Error("配置不能为空");
    this._config = config;
    // 资源路径可覆盖（用户把图标/字体放别处时）
    if (config.icon_base) __iconBase = config.icon_base;
    if (config.font_base) __fontBase = config.font_base; this._busy = {}; this._optim = {}; this._built = false;
  }
  set hass(hass) { this._hass = hass; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 22; }

  disconnectedCallback() {
    if (this._scrollCleanups) {
      for (const fn of this._scrollCleanups) { try { fn(); } catch (e) {} }
      this._scrollCleanups = null;
    }
    if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; }
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
  }

  /** 当前滚动量。
   *  ★ 2026-10-09：HA 里滚动常常发生在【外层容器】而不是文档
   *  （此时 window.scrollY 恒为 0）——所以优先读 scroll 事件目标的 scrollTop。
   *  scroll 不冒泡，但带 capture 的监听能收到子容器的 scroll 事件。 */
  _scrollTopOf(ev) {
    const t = ev && ev.target;
    if (t && t.nodeType === 1 && typeof t.scrollTop === "number") return t.scrollTop;
    return window.scrollY || document.documentElement.scrollTop || 0;
  }

  /** 真正的滚动祖先（没有则返回文档滚动元素）。 */
  _scrollRoot() {
    let n = this.parentElement || (this.getRootNode && this.getRootNode().host) || null;
    while (n && n.nodeType === 1) {
      const cs = getComputedStyle(n);
      if (/(auto|scroll|overlay)/.test(cs.overflowY) && n.scrollHeight > n.clientHeight + 2) return n;
      n = n.parentElement || (n.getRootNode && n.getRootNode().host) || null;
    }
    return document.scrollingElement || document.documentElement;
  }

  /** 抬头粘顶位置（px）—— 避开 HA 固定顶栏。
   *
   *  HA 的顶栏（`app-header`）是 position:fixed 覆盖在内容之上，高度由
   *  `--header-height` 给出（实测 56px）。两种布局：
   *    · 覆盖式（窄屏/移动端）：滚动容器顶边 = 视口顶端（0）
   *      → 抬头若只写 top:0 会被顶栏盖住（用户实测："抬头被遮挡"）→ 下移一个顶栏高度
   *    · 预留式（宽屏桌面）：滚动容器顶边已在顶栏之下（≈56）
   *      → 它的 top:0 本来就等于顶栏底边 → 不能下移，否则会露出空白
   *  两种情形用「滚动容器顶边 vs --header-height」自动区分，不用猜屏宽。
   */
  _headTopOffset() {
    try {
      const docEl = document.documentElement;
      const hh = parseFloat(getComputedStyle(docEl).getPropertyValue("--header-height")) || 0;
      if (!hh) return 0;                                     // 非 HA 环境（如卡片预览）不避让
      const sc = this._scrollRoot();
      const isDoc = !sc || sc === docEl || sc === document.body ||
                    sc === document.scrollingElement;
      const scTop = isDoc ? 0 : Math.round(sc.getBoundingClientRect().top);
      return scTop < hh - 2 ? Math.round(hh) : 0;            // 覆盖式才避让
    } catch (e) {
      return 0;
    }
  }

  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id); return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }
  /**
   * 实体是否处于"开"状态。
   * ★ 2026-10-14 修复（车主："授权驾驶为什么一直显示开着"）：
   *   原实现 `["…","1"].some(x => v.includes(x))` 会把**任何含 1 的状态**判成开 ——
   *   button 实体的状态是时间戳（如 2026-10-14T07:14:35+00:00，含 "1"），
   *   于是「授权驾驶」永远显示为开着。
   *   现在：先排掉明确的"关"、动作型实体（button）与时间戳状态，再做包含判断。
   */
  _on(id) {
    const s = this._st(id);
    if (!s) return false;
    const v = String(s.state == null ? "" : s.state).trim().toLowerCase();
    if (!v) return false;
    // 明确的"关/无效"值
    if (["off","closed","0","false","no","none","unknown","unavailable","idle","standby"].includes(v)) return false;
    // 动作型实体没有开/关语义（状态是"最后一次动作时间"）
    if (String(id).split(".")[0] === "button") return false;
    if (/^\d{4}-\d{2}-\d{2}t/.test(v)) return false;              // 时间戳状态
    if (v === "1") return true;                                      // 精确的 1 才算开
    // climate 域没有 "on" 状态：cool/heat/auto/dry/fan_only 都算"开着"
    if (["cool", "heat", "heat_cool", "auto", "dry", "fan_only"].includes(v)) return true;
    return ["on","open","opening","unlocked","locked","home","playing","true","yes","detected",
            "开启","已开启","已锁定","已连接","已解锁","在线"].some((x) => v.includes(x));
  }
  _online() {
    const s = this._st(this._config.online); if (!s) return true;
    return !["离线","off","unavailable","unknown"].some(v => String(s.state).includes(v));
  }
  /** 二次确认弹框（官方样式：白卡 + 取消/确定 + 不再提醒）。resolve {ok, remember} */
  _confirm(opts) {
    return new Promise((resolve) => {
      const old = this.querySelector(".cfm"); if (old) old.remove();
      const d = document.createElement("div");
      d.className = "cfm";
      d.innerHTML = `<div class="cfm-box" role="dialog" aria-modal="true">
          <div class="cfm-text">${opts.text}</div>
          <div class="cfm-row">
            <button type="button" class="cfm-no">取消</button>
            <button type="button" class="cfm-yes">确定</button>
          </div>
          ${opts.remember ? '<label class="cfm-rem"><input type="checkbox">不再提醒</label>' : ""}
        </div>`;
      this.appendChild(d);
      const box = d.querySelector(".cfm-rem input");
      const done = (ok) => {
        const remember = !!(box && box.checked);
        d.remove();
        resolve({ ok, remember });
      };
      d.querySelector(".cfm-no").addEventListener("click", () => done(false));
      d.querySelector(".cfm-yes").addEventListener("click", () => done(true));
      d.addEventListener("click", (e) => { if (e.target === d) done(false); });
      const y = d.querySelector(".cfm-yes"); if (y && y.focus) y.focus();
    });
  }

  /** 「不再提醒」是否已勾选并记住 */
  _noAsk(key) {
    try { return localStorage.getItem("lx_noask_" + key) === "1"; } catch (e) { return false; }
  }
  _setNoAsk(key, on) {
    try { on ? localStorage.setItem("lx_noask_" + key, "1") : localStorage.removeItem("lx_noask_" + key); } catch (e) { /* 隐私模式禁用存储 */ }
  }

  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2400);
  }
  _img(name) { return `${__iconBase}/${FALLBACK[name] || name}`; }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const c = this._config;
    const root = document.createElement("div");
    root.className = "root" + (c.car_default_collapsed ? " collapsed3d" : " expanded3d");
    root.dataset.theme = c.theme || "light";
    root.innerHTML = `
      <div class="head" id="head">
        <div class="hrow">
          <div class="hleft">
            <div class="title" id="t">理想汽车</div>
            <div class="ranges">
              <span class="rg"><img src="${__iconBase}/ic_home_electricity.webp" onerror="__lxIconFallback(this)" alt="">
                <span class="v" id="v-range">—</span><span class="u">km</span>
                <span class="v" id="v-soc" style="margin-left:6px">—</span><span class="u">%</span></span>
              <span class="rg" id="rg-fuel"><img src="${__iconBase}/ic_home_oil.webp" onerror="__lxIconFallback(this)" alt="">
                <span class="v" id="v-fuel">—</span><span class="u">km</span></span>
            </div>
            <div class="parked" id="v-status">—</div>
            <!-- ★ 2026-10-12：插电标识。App 在【插枪时】才显示充电桩
                 （车主两次截图对比确认）；我们用徽标表达同一信息，
                 且放在头部 —— 3D 展开/收起都能看到。 -->
            <span class="plug" id="v-plug" style="display:none" role="status">
              <img src="${__iconBase}/icon_charge_lighting.webp" alt="" onerror="this.style.display='none'">
              <b id="v-plug-t">充电枪已插入</b>
            </span>
            <!-- ★ 2026-10-14 对齐官方顶部徽标（HomeControlHeaderWarning / HeaderSentry） -->
            <span class="badge warn" id="v-badge-warn" style="display:none" role="status">
              <img src="${__iconBase}/src_assets_images_vehicle_header_ic_home_warning.png" alt="" onerror="this.style.display='none'">
              <b id="v-badge-warn-t">告警</b>
            </span>
            <span class="badge badge-sentry" id="v-badge-sentry" style="display:none" role="status">
              <img src="${__iconBase}/src_assets_images_vehicle_header_ic_home_sentry.png" alt="" onerror="this.style.display='none'">
              <b>哨兵</b>
            </span>
          </div>
          <div class="mini" id="mini" role="button" tabindex="0" aria-label="展开车辆 3D"></div>
        </div>
      </div>
      <div class="lowbat" id="lowbat" style="display:none" role="alert" aria-live="polite">
        <img src="${__iconBase}/ic_home_battery.webp" onerror="__lxIconFallback(this)" alt="">
        <span id="lowbat-t"></span>
      </div>
      <div class="big3d" id="big3d">
        <div class="ph" id="b3ph"><div class="spin2"></div><div>车辆 3D 加载中…</div></div>
        <div class="tires" id="tires" style="display:none">
          <div class="tp" data-k="lf"></div><div class="tp" data-k="rf"></div>
          <div class="tp" data-k="lr"></div><div class="tp" data-k="rr"></div>
        </div>
      </div>
      <div class="quick" id="quick" role="group" aria-label="快捷操作"></div>
      <div class="chev" id="chev" role="button" tabindex="0" aria-expanded="false" aria-label="展开更多快捷按键">
        <img src="${__iconBase}/ic_home_pulldown.png" onerror="__lxIconFallback(this)" alt="">
      </div>
      <div class="wrap">
        <div class="row2">
          <div class="card ac" id="c-ac" role="button" tabindex="0">
            <!-- ★ 2026-10-14 对齐官方：空调卡右下角的座椅插图（官方包内无可复用位图，自绘 SVG） -->
            <svg class="seatart" viewBox="0 0 120 128" aria-hidden="true">
              <defs><linearGradient id="lxseat" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#e9edf3"/></linearGradient></defs>
              <path d="M34 12h30c7 0 12 6 12 13l-3 44H37l-3-44c0-7 5-13 12-13z" fill="url(#lxseat)" stroke="#d7dde6" stroke-width="1"/>
              <rect x="30" y="72" width="58" height="14" rx="7" fill="url(#lxseat)" stroke="#d7dde6" stroke-width="1"/>
              <path d="M28 92h62c4 0 7 3 7 7v14c0 4-3 7-7 7H28c-4 0-7-3-7-7v-14c0-4 3-7 7-7z" fill="url(#lxseat)" stroke="#d7dde6" stroke-width="1"/>
              <rect x="40" y="20" width="18" height="4" rx="2" fill="#dde3ea"/>
              <rect x="40" y="30" width="18" height="4" rx="2" fill="#dde3ea"/>
              <rect x="40" y="40" width="18" height="4" rx="2" fill="#dde3ea"/>
            </svg>
            <div class="temp"><span id="v-room">—</span><sup>°C</sup></div>
            <div class="target">目标温度 <span id="v-target">—</span>°C</div>
            <div class="acrow" id="acrow">
              <span class="chip" id="ch-seat"><img src="${__iconBase}/ic_home_seat_heating3.webp" alt="" onerror="this.style.visibility='hidden'"><b id="ch-seat-t">座椅加热</b></span>
              <span class="chip" id="ch-fan"><img src="${__iconBase}/ic_home_fan_on.webp" onerror="__lxIconFallback(this)" alt=""><b id="ch-fan-t">吹风</b></span>
              <span class="chip" id="ch-defrost"><img src="${__iconBase}/ic_home_ice_cool.webp" onerror="__lxIconFallback(this)" alt=""><b id="ch-defrost-t">除雪除霜</b></span>
            </div>
            <div class="fan" id="fan"><img src="${__iconBase}/ic_home_fan_off.webp" onerror="__lxIconFallback(this)" alt=""></div>
          </div>
          <div class="card loc" id="c-loc" role="button" tabindex="0">
            <div class="map" id="map">
              <div class="tiles" id="hm-tiles"></div>
              <div class="puck" id="hm-puck" style="display:none">
                <img src="${__iconBase}/icon_car_loc.webp" onerror="__lxIconFallback(this)" alt="车辆位置"></div>
              <!-- ★ 2026-10-14 对齐官方 HomeControlMapPhoto：地图卡上的拍照按钮 -->
              <button type="button" class="shot" id="hm-shot" aria-label="远程拍照" style="display:none">
                <img src="${__iconBase}/ic_home_photo.png" onerror="__lxIconFallback(this)" alt="">
              </button>
            </div>
            <div class="addr"><img src="${__iconBase}/icon_vehicle_my_location.webp" alt="" onerror="this.style.display='none'">
              <span id="v-addr">定位获取中…</span></div>
          </div>
        </div>
        <div class="row2">
          <div class="card mile" id="c-mile" role="button" tabindex="0">
            <div class="big"><span id="v-mile">—</span><small>km</small></div>
            <div class="cap">本月陪伴里程</div>
            <!-- ★ 2026-10-12：折线 → 柱状图（对齐 App —— 车主截图里是柱状图 + 网格线） -->
            <div class="chart"><svg id="spark" viewBox="0 0 100 40" preserveAspectRatio="none">
              <g class="grid" id="sparkgrid" aria-hidden="true">
                <line x1="0" y1="10" x2="100" y2="10"></line>
                <line x1="0" y1="22" x2="100" y2="22"></line>
                <line x1="0" y1="34" x2="100" y2="34"></line>
              </g>
              <g id="sparkbars"></g></svg></div>
            <div class="axis"><span>01</span><span>08</span><span>15</span><span>22</span><span>29</span></div>
          </div>
          <div style="display:grid; gap:12px; grid-template-rows:1fr auto;">
            <div class="card batt" id="c-batt" role="button" tabindex="0">
              <div class="row"><img src="${__iconBase}/ic_home_battery.webp" onerror="__lxIconFallback(this)" alt="">
                <div><div class="big"><span id="v-batt">—</span><small>%</small></div>
                <div class="lbl" style="margin-top:2px">剩余电量</div></div></div>
              <!-- ★ 2026-10-11：充电中显示剩余时间（对齐 App「剩余2小时25分钟」）。
                   非充电态隐藏。数据源：charge_remain_time（ChargeSurplusTime/min） -->
              <div class="batt-remain" id="batt-remain" style="display:none">
                <span class="ic">⚡</span><span id="v-remain">—</span>
              </div>
            </div>
            <div class="card sentry" id="c-sentry" role="button" tabindex="0">
              <img src="${__iconBase}/ic_home_sentry.png" alt="" onerror="this.style.visibility='hidden'">
              <div><div class="t">哨兵模式</div><div class="s" id="v-sentry">—</div></div>
            </div>
          </div>
        </div>
        <div class="entries">
          <div class="entry" id="e-health" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_health.webp" onerror="__lxIconFallback(this)" alt="">
            <div class="tx"><div class="nm">车辆健康</div></div></div>
          <div class="entry" id="e-task" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_control_off_lisa.png" alt="" onerror="this.src='${__iconBase}/ic_home_control.webp'">
            <div class="tx"><div class="nm">任务大师</div></div></div>
          <div class="entry" id="e-key" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_bluetooth.webp" onerror="__lxIconFallback(this)" alt="">
            <!-- ★ 2026-10-12：原为「钥匙管理 / 未连接」——
                 ① 名称与页面内容（车辆信息）不符，车主据此误判「显示的设置的内容」；
                 ② 「未连接」来自 _eid("key_connected")，但该绑定键根本不存在，
                    所以永远显示假状态。现改为「车辆信息」+ 真实车型副标题。 -->
            <div class="tx"><div class="nm">车辆信息</div><div class="sd" id="v-key">—</div></div></div>
          <div class="entry" id="e-scene" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_scene_mode_lisa.png" alt="" onerror="this.src='${__iconBase}/ic_home_control.webp'">
            <div class="tx"><div class="nm">情景模式</div></div></div>
          <div class="entry" id="e-setting" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_control.webp" onerror="__lxIconFallback(this)" alt="">
            <div class="tx"><div class="nm">车辆设置</div></div></div>
        </div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    // ★ 2026-10-20：卡片拖拽排序初始化（长按 350ms 抓起 → 自由换位 → 记住顺序）
    //   · 先应用已保存的顺序，再给每个 .row2 挂拖拽能力。
    //   · 两处调用：首屏渲染 + 后续重渲染（车型/主题变化会重写 DOM）。
    try {
      root.querySelectorAll(".row2").forEach((r) => lxApplyOrder(r));
      root.querySelectorAll(".row2").forEach((r) => lxEnableDragSort(r));
      this.__lxDragBound = true;
    } catch (e) { /* 拖拽是增强功能，失败不影响主功能 */ }

    // ★ 2026-10-09（用户要求）：抬头固定。
    //   .head 用 position:sticky 粘顶；这里判断"是否已粘顶"以收紧头部。
    //   ⚠️ 用真实滚动量判断，不用 IntersectionObserver：
    //     HA 的滚动常发生在外层滚动容器里（视口 root 的 IO 会误判为"仍可见"），
    //     而 scroll 事件带 capture 能拿到容器，事件目标就是那个容器的 scrollTop。
    this._scrollCleanups = this._scrollCleanups || [];
    {
      // 浏览器可能恢复上次滚动位置：初始就按当前滚动量定"已粘顶"
      const y0 = this._scrollTopOf(null);
      let stuck = y0 > 4, lastY = y0, lastTop = null;
      const applyHeadTop = () => {
        const top = this._headTopOffset();
        if (top === lastTop) return;
        lastTop = top;
        root.style.setProperty("--lx-head-top", top + "px");
        root.dataset.headTop = String(top);   // 诊断可见：实际避让了多少 px
      };
      const onStuck = (ev) => {
        const y = this._scrollTopOf(ev);
        if (Math.abs(y - lastY) < 2) return;      // 抖动过滤
        lastY = y;
        const next = y > 4;
        if (next !== stuck) { stuck = next; root.classList.toggle("stuck", stuck); }
        applyHeadTop();
      };
      applyHeadTop();                       // 首屏先算一次
      window.addEventListener("scroll", onStuck, { passive: true });
      document.addEventListener("scroll", onStuck, { passive: true, capture: true });
      const onResize = () => applyHeadTop();
      window.addEventListener("resize", onResize, { passive: true });
      this._scrollCleanups.push(() => {
        window.removeEventListener("scroll", onStuck);
        document.removeEventListener("scroll", onStuck, { capture: true });
        window.removeEventListener("resize", onResize);
      });
    }

    const b3 = this.querySelector("#big3d"), mini = this.querySelector("#mini");
    // ★★★ 2026-10-12：车模改为**官方静态图**（放弃自建 3D）。
    //
    // 为什么放弃 3D（实测结论，别再重走）：
    //   1. 官方 AssetBundle 里**没有车门外覆件** —— 92 个网格里只有
    //      Door_*（材质="车门内_金属/内饰底绒_侧面"，即内衬），
    //      没有前/后保险杠、车门外壳。下载的官方包与本地包 md5 完全一致，
    //      所以不是导出错误，是素材本身如此。
    //   2. 成本高：转出来的 GLB 61 MB，手机每次清缓存都要重下。
    //   3. 颜色拿不到：7 个 CarPaint_* 材质共用同一张贴图、_BaseColor 全 [1,1,1]，
    //      车漆色不在模型里。
    //
    // 现在的方案（零人工配置）：
    //   GET /lixiang_auto/car-image.json → {modelId, colorCode, static:"/lixiang_car/…"}
    //   ★ colorCode 与车型配置里的 vertical[].key 是同一套（实测 colorCode=FA9）
    //   ★ 图是 p.ampmake.com 明文直链，后端按需下载并缓存，卡片直接 <img> 引用。
    //
    // 保留项：car_3d / car_iframe 配置项仍识别（显式传 car_3d:true 时走旧 3D 路径），
    //         但默认关闭 —— 以后若模型问题解决，改一个默认值即可恢复。
    const FALLBACK = c.car_image || __iconBase + "/icon_car_loc.webp";
    const still = `<img src="${FALLBACK}" alt="车辆">`;
    const useLegacy3d = c.car_3d === true;      // 默认不再走 3D

    if (useLegacy3d) {
      // ---- 旧 3D 路径（保留，默认不启用）----
      let DEFAULT_3D = "/lixiang_auto/lixiang-3d/index.html"
                     + "?minimal=1&model=/local/lixiang-3d/carmodel.glb";
      if (c.car_iframe) DEFAULT_3D = c.car_iframe;
      const frame = (title, extra) =>
        `<iframe src="${DEFAULT_3D}" title="${title}" loading="lazy" ${extra}
           sandbox="allow-scripts allow-same-origin allow-pointer-lock"></iframe>`;
      const f3 = document.createElement("iframe");
      f3.src = DEFAULT_3D; f3.title = "车辆 3D"; f3.loading = "lazy";
      f3.setAttribute("sandbox", "allow-scripts allow-same-origin allow-pointer-lock");
      b3.appendChild(f3);
      mini.innerHTML = frame("车辆 3D 缩略图", 'scrolling="no"');
    } else {
      // ---- 官方静态车模图（默认）----
      b3.innerHTML = still; mini.innerHTML = still;
      this._loadCarImage(b3, mini, FALLBACK);
    }

  /// 拉取官方车模图（★ 2026-10-12）。
  ///
  /// 后端返回 {model_id, color_code, vertical:{static, cached, key}}，
  /// 车型与车漆色都由服务器给，**用户无需任何配置**。
    // ★ 2026-10-16 车主：「是快捷下面的小三角箭头。这个键应该是快捷按键更多显示，
    //   不是隐藏和展示车模的地方。」
    //   → 拆成两个互不相干的开关：
    //     · #chev  = 快捷按键更多/收起（quick-compact：只留第一行 4 个）
    //     · #mini  = 车模 3D 的收起/展开（右上角小车图，它才是车模自己的开关）
    const toggle3d = () => {
      this._userToggled = true;    // 用户手动操作后，停止自动跟随
      const collapsed = !root.classList.contains("collapsed3d");
      root.classList.toggle("collapsed3d", collapsed);
      root.classList.toggle("expanded3d", !collapsed);
      try { localStorage.setItem("lx_3d_collapsed", collapsed ? "1" : "0"); } catch (e) {}
    };
    const toggleQuick = () => {
      const open = !root.classList.contains("quick-open");
      root.classList.toggle("quick-open", open);
      const chev = this.querySelector("#chev");
      if (chev) {
        chev.setAttribute("aria-label", open ? "收起快捷按键" : "展开更多快捷按键");
        chev.setAttribute("aria-expanded", open ? "true" : "false");
      }
    };
    const bind = (el, fn) => {
      if (!el) return;
      el.addEventListener("click", e => { e.stopPropagation(); fn(); });
      el.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); fn(); }
      });
    };
    bind(this.querySelector("#chev"), toggleQuick);   // 小三角 → 快捷按键更多/收起
    bind(this.querySelector("#mini"), toggle3d);      // 右上小车图 → 车模收起/展开

    // ★ 上拉自动收起 3D（对齐 App 交互）
    //   App 用滚动驱动：页面下滑 → 3D 收起；回到顶部 → 3D 展开
    //   ★ 2026-10-09：改为读【事件目标】的 scrollTop —— HA 的滚动常在外层容器里，
    //     只看 window.scrollY（恒为 0）会导致这里永不触发。
    if (c.car_scroll_collapse !== false) {
      const THRESHOLD = Number(c.car_scroll_threshold || 60);
      let lastY = 0, scheduled = false;
      const apply = (ev) => {
        scheduled = false;
        const y = this._scrollTopOf(ev);
        if (Math.abs(y - lastY) < 4) return;
        lastY = y;
        const collapsed = root.classList.contains("collapsed3d");
        if (y > THRESHOLD && !collapsed && !this._userToggled) {
          root.classList.add("collapsed3d"); root.classList.remove("expanded3d");
          try { localStorage.setItem("lx_3d_collapsed", "1"); } catch (e) {}
        } else if (y <= 8 && collapsed && !this._userToggled) {
          root.classList.remove("collapsed3d"); root.classList.add("expanded3d");
          try { localStorage.setItem("lx_3d_collapsed", "0"); } catch (e) {}
        }
      };
      // 不用 rAF（无头/后台标签下可能被节流），直接同步执行 + 微任务合并
      const onScroll = (ev) => apply(ev);   // 直接执行（scroll 本身已节流）
      window.addEventListener("scroll", onScroll, { passive: true });
      document.addEventListener("scroll", onScroll, { passive: true, capture: true });
      this._scrollCleanups = this._scrollCleanups || [];
      this._scrollCleanups.push(() => {
        window.removeEventListener("scroll", onScroll);
        document.removeEventListener("scroll", onScroll, { capture: true });
      });
    }

    const q = this.querySelector("#quick");
    // ★ 车型适配：只渲染这台车**真实支持**的功能
    const warmup = !this._hass || !Object.keys(this._hass.states || {}).length;
    // ★ 2026-10-14：网格渲染抽成独立方法（可重复调用）。
    //   原来这段直接写在 _build() 里，且**一旦 avail 为空就 return** ——
    //   首帧实体未就绪时会把后面「入口卡片接线」整段跳过，且 _build 只跑一次，
    //   导致**入口永远点不动**（车主反馈"下面的都无法操作"）。
    this._renderQuick(warmup);

    this._wireNav();

    // ★ 2026-10-12：车主指示移除「服务专家」与「理想AD学习平台」两个入口

    this._built = true;
  }




  /** 渲染快捷键网格（可重复调用：首帧实体未就绪时先占位，实体到位后自动重建） */
  _renderQuick(warmup) {
    const q = this.querySelector("#quick");
    if (!q) return;
    const avail = QUICK.filter(it => this._supports(it, warmup));
    // 已渲染过同样数量的按钮 → 无需重建（避免丢掉点击态/焦点）
    if (q.querySelector(".q") && q.dataset.shown === String(avail.length)
        && avail.every(it => q.querySelector(`.q[data-key="${it.key}"]`))) return;
    q.dataset.shown = String(avail.length);
    // ★ 2026-10-16：快捷项 ≤4（一行）时没有"更多"可展开 → 藏掉小箭头
    const chevEl = this.querySelector("#chev");
    if (chevEl) chevEl.style.display = avail.length > 4 ? "" : "none";
    q.replaceChildren();
    if (!avail.length) {
      q.innerHTML = '<div class="qempty">该车型暂无可用快捷功能</div>';
      return;
    }
    avail.forEach(it => {
      const d = document.createElement("div");
      d.className = "q"; d.dataset.key = it.key;
      d.setAttribute("role", "button"); d.setAttribute("tabindex", "0");
      d.setAttribute("aria-label", it.name);
      d.innerHTML = `<div class="c"><img src="${this._img(it.off)}" alt="" onerror="__lxIconFallback(this)"></div>
                     <div class="n">${it.name}</div><div class="sp"></div><div class="sub"></div>`;
      d.addEventListener("click", () => this._tap(it.key));
      d.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this._tap(it.key); }
      });
      q.appendChild(d);
    });
  }

  /** 入口卡片接线（幂等：只接一次，元素在 _build 后不再替换） */
  _wireNav() {
    if (this._navWired) return;
    this._navWired = true;
    const c = this._config;
    const nav = c.nav || {};
    const go = p => { if (!p) return; lxNavigate(this, p); };
    const wire = (sel, path, moreKey) => {
      const el = this.querySelector(sel); if (!el) return;
      const act = () => path ? go(path) : this._more(moreKey);
      el.addEventListener("click", act);
      el.addEventListener("keydown", e => {
        if (e.key==="Enter"||e.key===" ") { e.preventDefault(); act(); }
      });
    };
    wire("#c-mile", nav.energy || "/lixiang/energy");
    // ★ 新页面入口（2026-10-02 补齐）
    wire("#c-ac", nav.climate || "/lixiang/climate");
    wire("#c-loc", nav.location || "/lixiang/location");
    wire("#c-batt", nav.charge || "/lixiang/charge");
    wire("#t", nav.vinfo || "/lixiang/vinfo");
    wire("#e-key", nav.vinfo || "/lixiang/vinfo");
    wire("#e-task", nav.task || "/lixiang/task");
    wire("#e-scene", nav.scene || "/lixiang/scene");
    // 2026-10-12 修复（车主："车辆设置二级页面错误"）：这两行此前没有默认路径。
    // nav.setting / nav.health 未配置时是 undefined → go(undefined) → if (!p) return
    // → 点击完全没反应。与其他入口一致，补上默认路径。
    wire("#e-health", nav.health || "/lixiang/health");
    wire("#e-setting", nav.setting || "/lixiang/setting");
    // ★ 地图卡拍照按钮（官方 HomeControlMapPhoto）
    const shotEl = this.querySelector("#hm-shot");
    if (shotEl) {
      const shoot = async () => {
        const pe = this._eid("btn_photo");
        if (!pe) { this._toast("远程拍照未接入", "err"); return; }
        if (!this._online()) { this._toast("车辆离线，操作不可用", "err"); return; }
        try {
          await this._hass.callService("button", "press", { entity_id: pe });
          this._toast("已发送拍照", "ok");
        } catch (e) { this._toast("拍照失败：" + ((e && e.message) || "未知"), "err"); }
      };
      this._a11y(shotEl, "远程拍照", shoot);
      shotEl.addEventListener("click", shoot);
    }

    // 哨兵卡：点击直接切换（可控制），键盘同样支持
    const senEl = this.querySelector("#c-sentry");
    if (senEl) {
      const act = async () => {
        const eid = this._eid("sentry");
        if (!eid) { this._toast("哨兵模式未接入", "err"); return; }
        if (!this._online()) { this._toast("车辆离线，操作不可用", "err"); return; }
        const on = this._on(eid);
        try {
          await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: eid });
          this._toast(on ? "哨兵模式已关闭" : "哨兵模式已开启", "ok");
        } catch (e) { this._toast("切换失败：" + ((e && e.message) || "未知"), "err"); }
      };
      this._a11y(senEl, "切换哨兵模式", act);
      senEl.addEventListener("click", act);
    }
  }

  /** 胎压 → {v, unit}：实体单位是 kPa 时换算成 bar（与「车辆健康」页同一规则） */
  _tireVal(field) {
    const v = this._num(this._eid(field));
    const st = this._st(this._eid(field));
    const u = String(((st && st.attributes) || {}).unit_of_measurement || "").toLowerCase();
    if (v === null) return null;
    if (u.includes("kpa")) return { v: v / 100, unit: "bar" };
    if (u.includes("psi")) return { v: v / 14.5038, unit: "bar" };
    if (u.includes("bar")) return { v, unit: "bar" };
    return { v, unit: u || "" };
  }

  /** 把四个胎压值写到车图上（车头朝左的俯视图：车头在左端，车左侧在下方） */
  _applyTires() {
    const box = this.querySelector("#big3d");
    if (!box) return;
    // ★ 车图加载时会重写 #big3d 的 innerHTML，静态模板里的浮层会被冲掉
    //   → 这里按需创建（幂等），保证浮层始终在。
    let layer = box.querySelector(".tires");
    if (!layer) {
      layer = document.createElement("div");
      layer.className = "tires";
      layer.id = "tires";
      layer.style.display = "none";
      layer.innerHTML = '<div class="tp" data-k="lf"></div><div class="tp" data-k="rf"></div>'
        + '<div class="tp" data-k="lr"></div><div class="tp" data-k="rr"></div>';
      box.appendChild(layer);
    }
    const MAP = { lf: "tire_lf", rf: "tire_rf", lr: "tire_lr", rr: "tire_rr" };
    let any = false;
    for (const [k, field] of Object.entries(MAP)) {
      const el = layer.querySelector(`.tp[data-k="${k}"]`);
      if (!el) continue;
      const p = this._tireVal(field);
      if (p === null) { el.style.display = "none"; continue; }
      const bad = p.v > 0 && (p.v < 2.0 || p.v > 2.9);
      el.style.display = "";
      const num = bad && p.v < 2.0 ? p.v.toFixed(2) : p.v.toFixed(1);
      // ★ 带上单位（车主："另外确实单位"）
      el.innerHTML = `<b>${num}</b><small> ${p.unit}</small>`;
      el.classList.toggle("low", !!bad);
      el.title = `${({lf:"左前",rf:"右前",lr:"左后",rr:"右后"})[k]} ${num} ${p.unit}`;
      any = true;
    }
    layer.style.display = any ? "" : "none";
    if (any) this._layoutTires();
  }

  /** 按车图**实际渲染区域**摆放（车图 contain + object-position:50% 62%，不铺满盒子） */
  _layoutTires() {
    const box = this.querySelector("#big3d");
    const layer = box && box.querySelector(".tires");
    if (!box || !layer) return;
    const bw = box.clientWidth, bh = box.clientHeight;
    // 车图（object-fit:contain + object-position:50% 62%）的实际渲染区域
    let ox = 0, oy = 0, cW = bw, cH = bh;
    const img = box.querySelector("img");
    if (img && img.naturalWidth) {
      const r = img.getBoundingClientRect(), br = box.getBoundingClientRect();
      const ar = img.naturalHeight / img.naturalWidth;
      cH = Math.min(r.height, r.width * ar); cW = cH / ar;
      ox = r.left - br.left + (r.width - cW) / 2;
      oy = r.top - br.top + (r.height - cH) * 0.62;
    }
    // ★ 2026-10-14 车主纠正：车是**横放**的，四个轮子在车的**上下两条边**上，
    //   标签要贴在各自车轮的上/下侧 —— 不是放在卡片左右两端（车头/车尾）。
    //   实测轮心：纵向 x≈28.4% / 71.4%（前/后），横向 y≈29% / 71%（车的右侧在上、左侧在下）。
    //   车体轮廓占图高的 8%~92%，所以上排标签放车顶边之上、下排放车底边之下。
    const xF = ox + cW * 0.284;      // 前轮
    const xR = ox + cW * 0.714;      // 后轮
    const yT = oy + cH * 0.08 - 15;  // 车顶边之上（标签半高 + 间隙）
    const yB = oy + cH * 0.92 + 15;  // 车底边之下
    const POS = {
      rf: [xF, yT], rr: [xR, yT],    // 上排 = 车的右侧（右前 / 右后）
      lf: [xF, yB], lr: [xR, yB],    // 下排 = 车的左侧（左前 / 左后）
    };
    for (const [k, [px, py]] of Object.entries(POS)) {
      const el = layer.querySelector(`.tp[data-k="${k}"]`);
      if (!el) continue;
      el.style.left = Math.round(px) + "px";
      el.style.top = Math.round(py) + "px";
      el.style.right = "auto";
    }
  }

  /// 失败时保留占位图（不显示破图）。
  async _loadCarImage(b3, mini, fallback) {
    // ★ 2026-10-16 修「车图时有时无」：
    //   ① 先用**上次成功的 URL**（localStorage）→ 秒出；JSON 拿不到时也不至于退回 20×20 占位图标
    //   ② JSON 失败**重试一次**（1.5s 后），仍失败且无缓存 → 5s 后再试一轮（网络恢复自动出图）
    //   ③ <img> onerror **带 ?v= 重试一次**（破掉浏览器可能缓存的坏响应）
    const CK = "lx_car_img_v1";
    const hit = (() => { try { const o = JSON.parse(localStorage.getItem(CK) || "{}"); return o && o.src ? o : null; } catch (e) { return null; } })();
    const applySrc = (src, key) => {
      const put = (box) => {
        if (!box) return;
        const img = box.querySelector("img");
        if (!img) return;
        if (img.dataset.lxReal === "1" && img.getAttribute("src") === src) return;
        img.dataset.lxReal = "1";
        delete img.dataset.lxRetried;
        img.onload = () => { img.style.opacity = "1"; delete img.dataset.lxRetried; };
        img.onerror = () => {
          if (img.dataset.lxRetried === "1") { img.style.opacity = "0"; return; }   // 两次都失败 → 先藏，下轮再试
          img.dataset.lxRetried = "1";
          const bust = src + (src.indexOf("?") >= 0 ? "&" : "?") + "v=" + Date.now();
          setTimeout(() => { img.src = bust; }, 600);
        };
        img.style.opacity = "1";
        img.src = src;
        img.alt = "车辆 " + (key || "");
        img.style.objectFit = "contain";
      };
      put(b3); put(mini);
      if (b3) {
        const _im = b3.querySelector("img");
        if (_im) _im.addEventListener("load", () => this._layoutTires(), { once: true });
        this._layoutTires();
      }
    };
    if (hit) applySrc(hit.src, hit.key);                 // ① 缓存优先
    let data = null;
    for (let i = 0; i < 2 && !data; i++) {                // ② 拉 JSON（失败重试一次）
      try {
        const resp = await fetch("/lixiang_auto/car-image.json", { cache: "no-store" });
        if (resp.ok) data = await resp.json();
      } catch (err) { /* 静默：占位图已在 DOM 里 */ }
      if (!data && i === 0) await new Promise((r) => setTimeout(r, 1500));
    }
    if (!data || !data.ok || !data.vertical) {
      if (!hit) setTimeout(() => { if (this.isConnected) this._loadCarImage(b3, mini, fallback); }, 5000);
      return;
    }
    // ★ 横版优先（官方竖图逆时针旋转 90° 派生，车头朝左）—— 横容器不再"车小如邮票"
    const src = (data.horizontal && data.horizontal.static) || data.vertical.static || "";
    if (!src) return;                     // 还没缓存好 → 保持占位，下次刷新再来
    if (!hit || hit.src !== src) applySrc(src, data.color_code);   // ③ 只在变化时重设，避免闪
    try { localStorage.setItem(CK, JSON.stringify({ src, key: data.color_code || "", t: Date.now() })); } catch (e) {}
  }
  _more(key) {
    const eid = (this._config.more || {})[key];
    if (eid) {
      this.dispatchEvent(new CustomEvent("hass-more-info",
        { bubbles:true, composed:true, detail:{ entityId: eid } }));
    } else this._toast("该功能尚未接入");
  }

  async _tap(key) {
    if (this._busy[key]) return;
    const c = this._config;
    const eid = this._eidIn("quick", key);
    const el = this.querySelector(`.q[data-key="${key}"]`);
    const def = QUICK.find(x => x.key === key);
    if (!eid) {
      this._toast(`${def.name} ${def.note || "尚未接入"}`, "err");
      return;
    }
    if (!this._online()) { this._toast("车辆离线，操作不可用", "err"); return; }
    // ★ 官方同款：这类动作执行前要二次确认（可勾选"不再提醒"）
    if (def.confirm && !this._noAsk(key)) {
      const r = await this._confirm({ text: def.confirm, remember: def.remember });
      if (!r.ok) return;
      if (r.remember) this._setNoAsk(key, true);
    }
    const s = this._hass.states[eid];
    if (!s) { this._toast("实体不存在", "err"); return; }

    this._busy[key] = true; el.classList.add("busy");
    const dom = eid.split(".")[0];
    try {
      if (key === "find") {
        await this._hass.callService("button","press",{entity_id:eid});
      } else if (dom === "lock") {
        const unlocked = ["unlocked","已解锁","开锁"].some(v => String(s.state).includes(v));
        await this._hass.callService("lock", unlocked ? "lock" : "unlock", { entity_id: eid });
        this._optim[key] = !unlocked;
      } else if (dom === "cover") {
        // ★ 2026-10-09 修复：cover 域【没有】open/close 服务，
        //   正确服务名是 open_cover / close_cover（此前调用必然失败）。
        const opened = ["open","opening","on","开启","已连接"].some(v => String(s.state).includes(v));
        await this._hass.callService("cover", opened ? "close_cover" : "open_cover", { entity_id: eid });
        this._optim[key] = !opened;
      } else if (dom === "switch") {
        // ★ 2026-10-09 修复：switch 域没有 open/close，只有 turn_on/turn_off。
        const on = ["on","open","开启","true"].some(v => String(s.state).includes(v));
        await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: eid });
        this._optim[key] = !on;
      } else if (dom === "select") {
        const opts = (s.attributes && s.attributes.options) || [];
        const cur = opts.indexOf(s.state);
        const next = opts[(cur + 1) % opts.length];
        await this._hass.callService("select","select_option",{entity_id:eid, option:next});
        this._toast(`${def.name} → ${next}`, "ok");
      } else if (dom === "button") {
        await this._hass.callService("button","press",{entity_id:eid});
      } else if (dom === "binary_sensor" || dom === "sensor") {
        // 只读实体：不能控制，明确告知
        this._toast(`${def.name} 为只读状态，无法远程控制`, "err");
        return;
      } else {
        await this._hass.callService("homeassistant","toggle",{entity_id:eid});
      }
      const sub = el.querySelector(".sub");
      if (sub) sub.textContent = "✓ 已执行";
      el.classList.add("done");
      setTimeout(() => el.classList.remove("done"), 2400);
      this._toast(`${def.name} 已执行`, "ok");
      this._applyQuick();
      const ttl = (def && def.optimMs) || 3500;
      setTimeout(() => { delete this._optim[key]; this._applyQuick(); }, ttl);
    } catch (err) {
      this._toast(`${def.name} 失败：${(err && err.message) || "未知"}`, "err");
    } finally {
      delete this._busy[key]; el.classList.remove("busy");
    }
  }

  _applyQuick() {
    const c = this._config, offline = !this._online();
    QUICK.forEach(it => {
      const el = this.querySelector(`.q[data-key="${it.key}"]`);
      if (!el) return;
      const eid = this._eidIn("quick", it.key);
      // stateField：动作类按钮（如授权驾驶 = button）用另一个实体显示状态。
      // ★ 配了 stateField 但解析不到（该车没有这个实体）时必须返回 null ——
      //   回退到动作实体本身会让 button 的时间戳状态被当成"开着"（真实踩过的坑）。
      const stateEid = it.stateField ? (this._eid(it.stateField) || null) : eid;
      let active = false; const missing = !eid || !this._st(eid);
      if (stateEid && this._st(stateEid)) {
        if (it.key in this._optim) active = this._optim[it.key];
        else if (it.key === "lock") {
          const v = String((this._st(stateEid) || {}).state || "");
          active = ["unlocked","已解锁"].some(x => v.includes(x));
        } else active = this._on(stateEid);
      }
      el.className = "q" + (active ? " on" : "") + ((missing || offline) ? " dim" : "")
                   + (this._busy[it.key] ? " busy" : "");
      // ★ 2026-10-14 官方逻辑：授权按钮有**两态** ——
      //   车辆已启动（非驻车）→ 已启动；已授权 → 已授权；否则 授权驾驶。
      //   （官方 I18N：alreadyAuthorization='已授权' / alreadyStart='已启动'）
      const nameEl = el.querySelector(".n");
      if (nameEl && it.onName) {
        let want = active ? it.onName : it.name;
        if (it.startedName) {
          const stTxt = String(this._txt(this._eid("status")) || "");
          const started = !!stTxt && !/驻车|P\s*档|park/i.test(stTxt);
          if (started) { want = it.startedName; active = true; }
        }
        if (nameEl.textContent !== want) nameEl.textContent = want;
      }
      el.setAttribute("aria-pressed", active ? "true" : "false");
      // 未接入的按钮：把原因写在下面（例如"集成暂未支持"），避免用户反复点
      const sub = el.querySelector(".sub");
      if (sub && missing && it.note) sub.textContent = it.note;
      const img = el.querySelector("img");
      if (img) {
        // ★ 2026-10-14：只在目标变化时赋值，并清掉回退标记 ——
        //   __lxIconFallback 带 dataset.lxFb 一次性保护；若每次都重新赋 /local 值，
        //   回退救回来的内置图标会被再次写坏且不再回退 → 永久破图。
        const want = this._img(active ? it.on : it.off);
        if (img.getAttribute("src") !== want) {
          delete img.dataset.lxFb;
          img.src = want;
        }
      }
    });
  }

  /** 本月每日里程 —— **柱状图**（对齐 App；此前是折线）。
   *  每根柱子等宽，高度按当月最大值归一；0 值不画柱子。
   */
  _spark() {
    const el = this.querySelector("#sparkbars"); if (!el) return;
    // 优先用服务拉取的日明细（属性常因 recorder 未落库而为空）
    let cached = this._dailyCache;
    const s = this._st(this._config.mile_chart || this._config.month_km);
    let vals = null;
    if (Array.isArray(cached) && cached.length) {
      vals = cached.map(r => Number(r.mileage) || 0);
    }
    if (!vals && s && s.attributes) {
      for (const k of ["month_daily","daily_list"]) {
        const raw = s.attributes[k];
        if (Array.isArray(raw) && raw.length) { vals = raw.map(r => Number(r.mileage) || 0); break; }
      }
    }
    if (!vals || !vals.length) { el.innerHTML = ""; return; }
    const max = Math.max.apply(null, vals.concat([1]));
    const n = vals.length;
    const step = 100 / n;                       // 每根柱子占的横向槽位
    const bw = Math.max(step * 0.62, 0.9);      // 柱宽（留间隙）
    el.innerHTML = vals.map((v, i) => {
      const val = Number(v) || 0;
      const h = (val / max) * 34;               // 柱高（底部留 6 给坐标轴）
      const x = i * step + (step - bw) / 2;
      const y = 40 - h - 2;
      const zero = val <= 0 ? ' data-zero="1"' : "";
      return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${bw.toFixed(2)}" `
           + `height="${Math.max(h, 0.6).toFixed(2)}"${zero}></rect>`;
    }).join("");
  }

  _update() {
    if (!this._built) return;
    const c = this._config, q = s => this.querySelector(s);

        // 标题：手填 > 自动识别的车型 > 兜底
    const _mdl = this._detectModel();
    const _title = this._config.title
      || (_mdl && (_mdl.series ? `理想${_mdl.series}` : (_mdl.model || _mdl.name)))
      || "理想汽车";
    q("#t").textContent = _title;
    if (_mdl) q("#t").setAttribute("title", `${_title}（自动识别）`);
    const rg = this._num(this._eid("range_elec")), soc = this._num(this._eid("battery")), fu = this._num(this._eid("range_fuel"));
    const vR = q("#v-range"), vS = q("#v-soc");
    vR.textContent = rg == null ? "—" : Math.round(rg);
    vR.className = "v" + (rg == null ? " na" : "");
    vS.textContent = soc == null ? "—" : soc;
    vS.className = "v" + (soc == null ? " na" : "");
    const rgf = q("#rg-fuel");
    if (this._eid("range_fuel") && this._st(this._eid("range_fuel"))) {
      rgf.style.display = "";
      q("#v-fuel").textContent = fu == null ? "—" : Math.round(fu);
    } else rgf.style.display = "none";

    q("#v-status").textContent = this._txt(this._eid("status")) || "—";

    // ★ 低电量告警（续航/电量异常时醒目提示）
    const lb = q("#lowbat");
    if (lb) {
      const socLow = soc != null && soc <= 20;
      const rngLow = rg != null && rg <= 50;
      if (socLow || rngLow) {
        lb.style.display = "";
        lb.className = "lowbat" + (soc != null && soc <= 10 ? " crit" : "");
        const parts = [];
        if (soc != null && soc <= 20) parts.push(`电量仅 <b>${soc}%</b>`);
        if (rg != null && rg <= 50) parts.push(`剩余续航 <b>${Math.round(rg)}km</b>`);
        q("#lowbat-t").innerHTML = parts.join("，") + "，建议尽快充电";
      } else lb.style.display = "none";
    }
    // 电量数字着色
    const socEl = q("#v-soc");
    if (socEl && soc != null) {
      socEl.className = "v" + (soc <= 10 ? " crit" : (soc <= 20 ? " low" : ""));
    }
    const rgEl = q("#v-range");
    if (rgEl && rg != null) {
      rgEl.className = "v" + (rg <= 30 ? " crit" : (rg <= 50 ? " low" : (rg == null ? " na" : "")));
    }

    const room = this._num(this._eid("room_temp")), tgt = this._num(this._eid("target_temp"));
    q("#v-room").textContent = room == null ? "—" : room.toFixed(1);
    q("#v-target").textContent = tgt == null ? "—" : tgt;
    // ★ 2026-10-14：空调是 climate 域，状态是 cool/heat/auto/fan_only…（**不是 on**），
    //   原来用 _on() 判 → 永远 false → 风扇不转；且图标固定用白色版（浅底上几乎看不见）。
    const acEid = this._eid("ac");
    const acSt = this._st(acEid);
    const acRaw = acSt ? String(acSt.state).toLowerCase() : "";
    const acOn = ["cool", "heat", "heat_cool", "auto", "dry", "fan_only", "on", "开启"]
      .some((x) => acRaw.includes(x));
    const fan = q("#fan");
    if (fan) {
      fan.className = "fan" + (acOn ? " on" : "");
      const fi = fan.querySelector("img");
      const want = this._img(acOn ? "ic_home_fan_on.webp" : "ic_home_fan_off.webp");
      if (fi && fi.getAttribute("src") !== want) { delete fi.dataset.lxFb; fi.src = want; }
    }
    // 功能状态 chip（有实体且开启时点亮；无实体则隐藏）
    const _chip = (sel, eid) => {
      const el = q(sel); if (!el) return;
      if (!eid) { el.style.display = "none"; return; }
      el.style.display = "";
      el.className = "chip" + (this._on(eid) ? " on" : "");
    };
    // ★ 2026-10-14 对齐官方空调页文案（从 index.vehicle.bundle 反汇编提取，共 23 项）：
    //   deicing:'除雪除霜' · rapidCool:'极速制冷' · rapidHeat:'极速制热' · steeringWheelHeat:'方向盘加热'
    //   我们原来写的是 座椅 / 吹风 / 除霜 —— 与官方措辞不一致。
    const seatEid = this._eid("steer_heat");
    _chip("#ch-seat", seatEid || this._eid("ac_fast_hot"));
    const seatT = q("#ch-seat-t");
    if (seatT) seatT.textContent = seatEid ? "方向盘加热" : "极速制热";
    _chip("#ch-fan", this._eid("ac_fast_cold"));
    const fanT = q("#ch-fan-t"); if (fanT) fanT.textContent = "极速制冷";
    _chip("#ch-defrost", this._eid("ac_defrost"));
    const defT = q("#ch-defrost-t"); if (defT) defT.textContent = "除雪除霜";

    // 地址：device_tracker 的 attributes 里可能有 address / 也支持坐标回退
    let addr = null;
    const dt = this._st(this._eid("tracker"));
    if (dt && dt.attributes) {
      addr = dt.attributes.address || dt.attributes.friendly_name && dt.attributes.address;
      if (!addr && dt.attributes.latitude != null) {
        addr = `${Number(dt.attributes.latitude).toFixed(4)}, ${Number(dt.attributes.longitude).toFixed(4)}`;
      }
    }
    if (!addr) {
      const sv = this._txt(this._eid("address"));
      addr = (sv && !/^\d+$/.test(String(sv))) ? sv : "暂无定位";
    }
    q("#v-addr").textContent = addr;
    // ★ 2026-10-03：自建地图（高德瓦片，免 key/免登录）。
    //   原 iframe（uri.amap.com/marker）在 iframe 里会弹登录页。
    this._drawHomeMap(
      dt && dt.attributes ? dt.attributes.latitude : null,
      dt && dt.attributes ? dt.attributes.longitude : null);

    q("#v-mile").textContent = (mk => mk == null ? "—" : mk)(this._num(this._eid("month_km")));
    q("#v-batt").textContent = soc == null ? "—" : soc;

    // ★ 2026-10-11：充电中显示「剩余2小时25分钟」（对齐 App）。
    //   判据：ChargeSurplusTime(剩余充电时间) > 0 —— 无需依赖额外的充电状态实体。
    //   非充电态（无该实体 / 值为 0 / 未知）→ 整行隐藏，不留空位。
    const rmEl = q("#batt-remain");
    if (rmEl) {
      const rmRaw = this._txt(this._eid("remain_time"));
      const rmMin = Number(rmRaw);
      if (rmRaw && Number.isFinite(rmMin) && rmMin > 0) {
        rmEl.style.display = "";
        const _h = Math.floor(rmMin / 60), _m = Math.round(rmMin % 60);
        q("#v-remain").textContent =
          (_h ? _h + "小时" : "") + (_m ? _m + "分钟" : (_h ? "整" : "—"));
      } else {
        rmEl.style.display = "none";
      }
    }

    const sen = this._eid("sentry") ? this._on(this._eid("sentry")) : false;
    const senEl = q("#c-sentry"); if (senEl) senEl.className = "card sentry" + (sen ? " on" : "");
    q("#v-sentry").textContent = this._eid("sentry") ? (sen ? "已激活" : "未激活") : "未接入";

    // ★ 插电标识（对齐 App：插枪时才有充电桩/插枪提示）。
    //   交流枪与直流枪任一插入即显示；都没有则整块隐藏（不留空隙）。
    const plugEl = q("#v-plug");
    if (plugEl) {
      const acGun = this._on(this._eid("ac_gun"));
      const dcGun = this._on(this._eid("dc_gun"));
      if (acGun || dcGun) {
        plugEl.style.display = "";
        const pt = q("#v-plug-t");
        if (pt) pt.textContent = (dcGun ? "直流快充" : "交流慢充") + " · 充电枪已插入";
      } else {
        plugEl.style.display = "none";
      }
    }

    // 副标题显示车型（真实数据）；拿不到就留空，不再显示假状态
    const vk = q("#v-key");
    if (vk) {
      const cfg = this._txt(this._eid("vehicle_cfg"));
      vk.textContent = cfg ? String(cfg).slice(0, 10) : "";
    }

    // ★ 2026-10-14：首帧实体未就绪时网格是空的 —— 实体到位后重建
    if (!this.querySelector("#quick .q")) this._renderQuick(false);
    this._applyQuick(); this._spark();
    this._applyTires();
    // ★ 2026-10-14 对齐官方顶部徽标：告警（胎压告警任一）/ 哨兵（开启时）
    const wEl = this.querySelector("#v-badge-warn");
    if (wEl) {
      const wids = ["warn_lf", "warn_rf", "warn_lr", "warn_rr"]
        .map((k) => this._eid(k)).filter(Boolean);
      const won = wids.filter((id) => this._on(id)).length;
      wEl.style.display = won ? "" : "none";
      const wt = this.querySelector("#v-badge-warn-t");
      if (wt) wt.textContent = won > 1 ? `告警 ${won}` : "胎压告警";
    }
    const sBEl = this.querySelector("#v-badge-sentry");
    if (sBEl) {
      const se = this._eid("sentry");
      sBEl.style.display = (se && this._on(se)) ? "" : "none";
    }
    const shotBEl = this.querySelector("#hm-shot");
    if (shotBEl) shotBEl.style.display = this._eid("btn_photo") ? "" : "none";
    if (!this._tireResize) {
      this._tireResize = () => this._layoutTires();
      window.addEventListener("resize", this._tireResize);
    }
    this._fetchDaily();
  }

  /** 拉当月日明细（折线图用）—— 必须带 year/month，无参只返回年列表 */
  async _fetchDaily() {
    if (this._dailyCache || this._fetchingDaily || !this._hass) return;
    this._fetchingDaily = true;
    try {
      const now = new Date();
      const r = await this._hass.callService(
        "lixiang_auto", "get_travel",
        { year: now.getFullYear(), month: now.getMonth() + 1 },
        undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const dl = first && first.data && first.data.dailyList;
      if (Array.isArray(dl) && dl.length) {
        this._dailyCache = dl.map((x) => ({
          dayOfMonth: Number(x.dayOfMonth) || 0,
          mileage: Number(x.mileage) || 0,
        })).sort((a, b) => a.dayOfMonth - b.dayOfMonth);
        this._spark();
      }
    } catch (e) { /* 折线图非关键路径，静默 */ }
    finally { this._fetchingDaily = false; }
  }
  // ── 自建地图（高德瓦片）────────────────────────────────────────────
  /** WGS84 → GCJ-02（大陆偏移 300~600m）。 */
  _wgs2gcj(lat, lon) {
    const a = 6378245.0, ee = 0.00669342162296594323;
    if (lon < 72.004 || lon > 137.8347 || lat < 0.8293 || lat > 55.8271) return [lat, lon];
    const tfLat = (x, y) => {
      let r = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
      r += (20*Math.sin(y*Math.PI) + 40*Math.sin(y/3*Math.PI)) * 2/3;
      r += (160*Math.sin(y/12*Math.PI) + 320*Math.sin(y*Math.PI/30)) * 2/3;
      return r;
    };
    const tfLon = (x, y) => {
      let r = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
      r += (20*Math.sin(x*Math.PI) + 40*Math.sin(x/3*Math.PI)) * 2/3;
      r += (150*Math.sin(x/12*Math.PI) + 300*Math.sin(x/30*Math.PI)) * 2/3;
      return r;
    };
    const dLat0 = tfLat(lon - 105, lat - 35), dLon0 = tfLon(lon - 105, lat - 35);
    const radLat = lat / 180 * Math.PI;
    let magic = Math.sin(radLat); magic = 1 - ee*magic*magic;
    const sm = Math.sqrt(magic);
    const dLat = (dLat0 * 180) / ((a * (1 - ee)) / (magic * sm) * Math.PI);
    const dLon = (dLon0 * 180) / (a / sm * Math.cos(radLat) * Math.PI);
    return [lat + dLat, lon + dLon];
  }

  _llToTile(lat, lon, z) {
    const n = 2 ** z;
    return [(lon + 180) / 360 * n,
            (1 - Math.log(Math.tan(lat*Math.PI/180) + 1/Math.cos(lat*Math.PI/180)) / Math.PI) / 2 * n];
  }

  /** 首页迷你地图：车辆居中，铺满容器。 */
  _drawHomeMap(la, lo) {
    const box = this.querySelector("#hm-tiles");
    const wrap = this.querySelector("#map");
    const puck = this.querySelector("#hm-puck");
    if (!box || !wrap) return;
    // ★ 车标位置【每次都更新】—— 不能放在"位置没变就 return"之后，
    //   否则第二次渲染就直接 return，车标永远停在 display:none。
    if (la == null || lo == null) {
      if (puck) puck.style.display = "none";
      return;
    }
    const [glat, glon] = this._wgs2gcj(Number(la), Number(lo));
    const key = `${glat.toFixed(6)},${glon.toFixed(6)}`;
    const _W0 = wrap.clientWidth || 180, _H0 = wrap.clientHeight || 90;
    if (puck) {
      puck.style.display = "";
      puck.style.left = _W0 / 2 + "px";
      puck.style.top = _H0 / 2 + "px";
    }
    if (box.dataset.pt === key) return;          // 瓦片不重绘（仅更新车标）
    box.dataset.pt = key;
    const z = 15;                                 // 首页小图：看大致位置
    const W = wrap.clientWidth || 180, H = wrap.clientHeight || 90;
    const [cxE, cyE] = this._llToTile(glat, glon, z);
    const cxI = Math.floor(cxE), cyI = Math.floor(cyE);
    const offX = (cxE - cxI) * 256, offY = (cyE - cyI) * 256;
    const cpx = W / 2, cpy = H / 2;
    const x0 = cxI - Math.ceil((cpx - offX) / 256);
    const x1 = cxI + Math.ceil((W - cpx + offX) / 256);
    const y0 = cyI - Math.ceil((cpy - offY) / 256);
    const y1 = cyI + Math.ceil((H - cpy + offY) / 256);
    const n = 2 ** z;
    const frag = [];
    for (let tx = x0; tx <= x1; tx++) {
      for (let ty = y0; ty <= y1; ty++) {
        if (tx < 0 || ty < 0 || tx >= n || ty >= n) continue;
        const left = cpx - offX + (tx - cxI) * 256;
        const top = cpy - offY + (ty - cyI) * 256;
        const s2 = (tx + ty) % 4 + 1;
        frag.push(`<img src="https://webrd0${s2}.is.autonavi.com/appmaptile`
                + `?lang=zh_cn&size=1&scale=1&style=8&x=${tx}&y=${ty}&z=${z}"`
                + ` style="left:${Math.round(left)}px;top:${Math.round(top)}px" alt="">`);
      }
    }
    box.innerHTML = frag.join("");
  }

}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangAppHome);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "理想车控首页（v3 · 对齐 App）",
  description: "8 圆按钮 · 双态 3D · 空调/位置/里程/电量/哨兵 · 各页入口",
  preview: true,
});
})();

/* ===================== lixiang-charge-page.js ===================== */
(function () {

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


/**
 * lixiang-charge-page  —— 充电（二级页）
 *
 * ★ 结构对齐里程能耗页（App 同款）：
 *   顶栏 → 实时状态卡 → 本月统计 → 按月折叠（年→月）→ 明细 → 充电设置
 *
 * 数据源（全部实测可用）：
 *   实时状态 → VSS 实体（charging_status / limit / mode / appointment / guns）
 *   历史统计 → lixiang_auto.get_charge 服务（按月次数 + 电量）
 *   单次明细 → 同上（startTime / chargingType / chargingCapacity）
 */

const CARD_TAG = "lixiang-charge-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖
const __fontFallback = BUILTIN_FONT_BASE;

const I18N = {
  title: "充电管理",          // ★ 官方标题（不是"充电"）
  status: "充电状态",
  notCharging: "等待充电",   // ★ 官方文案（不是"未充电"）
  charging: "充电中",
  done: "充电完成",        // ★ 官方文案（不是"已充满"）
  power: "充电效率",
  powerKw: "充电功率",
  volt: "输入电压",     // ★ 官方 4 项指标之三
  amp: "输入电流",      // ★ 官方 4 项指标之四  // ★ 官方 4 项指标之二（引擎键名 av = A×V）   // ★ 2026-10-14 官方文案（不是"充电功率"）
  remain: "剩余时间",
  records: "充电记录",        // ★ 官方右上角入口
  remainPrefix: "剩余",       // ★ 官方「剩余2小时7分钟」
      // ★ 2026-10-17 官方 PowerDisplay 文案（Hermes 包 i18n：chargingCalibration1/2）
      //   车刚插枪进入"校准"阶段时 ChargeSurplusTime 会暂时为 0，
      //   官方此刻显示的是"充电校准中，预计5-10分钟"，而不是"剩余0分钟"。
      calibrating: "充电校准中，预计5-10分钟",
  hour: "小时",
  apptEnd: "按时结束",        // ★ 官方文案
  hint: "日常快充建议最高设置为95%，95%以上充电功率较低。",
  footer: "适用于交流充电桩和理想20kW直流充电桩",
  limit: "充电上限",
  mode: "充电模式",
  appt: "预约充电",
  apptTime: "预约时间段",
  acGun: "交流慢充",
  dcGun: "直流快充",
  portCover: "充电口盖",
  coverOpen: "开",
  coverClose: "关",
  coverTapHint: "点开合",
  fault: "充电故障",
  monthKwh: "本月充电量",
  monthTimes: "本月次数",
  totalKwh: "累计充电量",
  history: "充电记录",
  dc: "直流",
  // ★ 2026-10-11：明细标签按充电类型显示（此前只有"直流/交流"两种，
  //   5C/4C 超充被错误地标成了"交流"）
  ctDc: "直流快充",
  ctAc: "交流慢充",
  ct5c: "5C超充",
  ct4c: "4C超充",
  ac: "交流",
  times: "次",
  chargePrefix: "充电",
  noData: "暂无数据",
  loading: "加载中…",
  settings: "充电设置",
  year: "年",
  min: "分钟",
};

/** ★ 2026-10-11：充电类型筛选（对齐 App）。
 *  value 直传服务端 charging_type：0=聚合全部 / 1=DC 直流 / 2=AC 交流 /
 *  "hpc"=理想超充(服务端聚合 5C+4C5C)。 */
const _CTYPES = [
  { value: 0,     label: "全部" },
  { value: 2,     label: "交流慢充" },
  { value: 1,     label: "直流快充" },
  { value: "hpc", label: "理想超充" },
];

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-charge-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-charge-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { container-type:inline-size; position:relative; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:16px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  .topbar { display:flex; align-items:center; height:48px; padding:0 16px; }
  .back { width:24px; height:24px; opacity:.75; cursor:pointer; }
  .topbar h1 { font-size:17px; font-weight:500; margin:0; flex:1; text-align:center; }
  .topbar .r { width:24px; }

  /* ── 实时状态大卡 ── */
  .hero { margin:6px 20px 0; border-radius:18px; padding:16px;
          background:linear-gradient(150deg,var(--lx-card) 0%,var(--lx-bg) 100%); }
  .hero .row1 { display:flex; align-items:center; gap:9px; }
    /* ★ 2026-10-14 官方充电管理页：环形电量表 */
    .ringwrap { position:relative; width:150px; height:150px; margin:14px auto 4px; }
    .ring { width:100%; height:100%; display:block; }
    .ring .rbg { fill:none; stroke:#e8eaee; stroke-width:9; }
    .ring .rfg { fill:none; stroke:var(--lx-green); stroke-width:9; stroke-linecap:round;
                 transform:rotate(-90deg); transform-origin:50% 50%;
                 transition:stroke-dashoffset .5s ease; }
    .ringwrap .bolt { position:absolute; left:50%; top:-13px; width:34px; margin-left:-17px; }
    .ringwrap .rtx { position:absolute; inset:0; display:flex; align-items:center;
                     justify-content:center; font-weight:600; }
    .ringwrap .rtx span { font-size:42px; letter-spacing:-1px; }
    .ringwrap .rtx small { font-size:15px; margin:12px 0 0 3px; }
    .remline { text-align:center; font-size:15px; color:var(--lx-t2); margin:2px 0 12px; }
    /* ★ 2026-10-16：未充电时把空信息收起（见 _update 里的「不充电自动隐藏」）。
       注意 .metrics 是 display:grid，会盖掉 hidden 属性的 display:none，所以显式写一条。 */
    .hero .metrics[hidden], .remline[hidden] { display:none; }
    /* 上限滑杆块（官方） */
    .limitbox { margin:12px 20px 0; background:var(--lx-card); border-radius:18px; padding:16px; }
    .limitbox .lbrow1 { display:flex; align-items:baseline; justify-content:space-between;
                        font-size:16px; font-weight:500; }
    .limitbox .lbrow1 b { font-size:16px; font-weight:600; }
    .limitbox .rng { -webkit-appearance:none; appearance:none; width:100%; height:6px;
                     margin:16px 0 6px; border-radius:3px; background:linear-gradient(
                       to right, var(--lx-green) 0%, var(--lx-green) var(--fill,100%),
                       #e8eaee var(--fill,100%), #e8eaee 100%); outline:none; }
    .limitbox .rng::-webkit-slider-thumb { -webkit-appearance:none; width:20px; height:20px;
                      border-radius:50%; background:#fff; box-shadow:0 1px 4px rgba(0,0,0,.25); }
    .limitbox .rng::-moz-range-thumb { width:18px; height:18px; border:0; border-radius:50%;
                      background:#fff; box-shadow:0 1px 4px rgba(0,0,0,.25); }
    .limitbox .lbrow2 { display:flex; justify-content:space-between; font-size:12px; color:var(--lx-t3); }
    .limitbox .hint { margin-top:12px; font-size:12px; line-height:1.6; color:var(--lx-t3); }
    /* 设置行（预约充电 / 按时结束） */
    .setcard { margin:12px 20px 0; background:var(--lx-card); border-radius:18px; padding:0 16px; }
    .setcard .setrow { display:flex; align-items:center; justify-content:space-between;
                       min-height:56px; border-bottom:1px solid rgba(0,0,0,.05); }
    .setcard .setrow:last-child { border-bottom:0; }
    .setcard .sl { font-size:16px; }
    .setcard .tg { position:relative; width:50px; height:30px; border-radius:15px;
                   background:#dfe3e9; transition:background .2s; cursor:pointer; flex:0 0 auto; }
    .setcard .tg i { position:absolute; top:3px; left:3px; width:24px; height:24px; border-radius:50%;
                     background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.2); transition:left .2s; }
    .setcard .tg.on { background:var(--lx-blue); }
    .setcard .tg.on i { left:23px; }
    .setcard .tmin { border:0; background:transparent; font-size:16px; color:var(--lx-t2);
                     text-align:right; font-family:inherit; }
    .pfoot { margin:14px 20px 26px; text-align:center; font-size:12px; color:var(--lx-t3); }
    .topbar .reclink { margin-left:auto; margin-right:10px; border:0; background:transparent;
                       font-size:15px; color:var(--lx-t1); font-family:inherit; cursor:pointer; }
  .hero .dot { width:9px; height:9px; border-radius:50%; background:var(--lx-t3); }
  .hero .dot.on { background:var(--lx-green); box-shadow:0 0 0 4px rgba(52,199,89,.16); }
  .hero .dot.err { background:var(--lx-red); }
  .hero .st { font-size:16px; font-weight:500; }
  .hero .sub { margin-left:auto; font-size:12px; color:var(--lx-t3); }
  /* 三栏：前两个数值等宽，第三个（模式·文字）给更多空间 */
  /* ★ 2026-10-14 车主："剩余时间下面，一行直接显示四个，跟 app 保持一致"
     官方充电管理页 4 项指标就是【一行四列】（44km/hr · 8.8kW · 24A · 373V）。 */
  .hero .metrics { display:grid; grid-template-columns:repeat(4, minmax(0,1fr));
                   gap:6px; margin-top:14px; }
  .hero .m .v { font-family:"LxNum","Licium"; font-size:21px; font-weight:600;
                white-space:nowrap; }
  .hero .m .v.txt { font-family:"Licium"; font-size:14px; font-weight:500;
                    white-space:normal; line-height:1.25; word-break:break-word; }
  .hero .m .l { white-space:nowrap; }
  .hero .m .v small { font-size:11px; color:var(--lx-t2); margin-left:2px; }
  /* 文字型值（如"低价充电"）用较小字号，避免换行 */
  .hero .m .v.txt { font-size:15px; font-weight:500; font-family:"Licium"; }
  .hero .m .l { font-size:11px; color:var(--lx-t3); margin-top:3px; }
  .hero .bar { height:7px; border-radius:20px; background:var(--lx-line);
               overflow:hidden; margin-top:14px; }
  .hero .bar > i { display:block; height:100%; border-radius:20px;
                   background:var(--lx-green); transition:width .45s; }
  .hero .barrow { display:flex; align-items:center; gap:10px; margin-top:12px; }
  .hero .barrow .p { font-family:"LxNum"; font-size:13px; font-weight:600; min-width:42px;
                     text-align:right; }
  .hero .barrow .lb { font-size:11px; color:var(--lx-t3); min-width:56px; }

  /* ── 统计三栏 ── */
  .stat3 { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; padding:14px 20px 0; }
  .st { background:var(--lx-card); border-radius:14px; padding:12px 10px; text-align:center; }
  .st .v { font-family:"LxNum","Licium"; font-size:20px; font-weight:600; }
  .st .v small { font-size:11px; color:var(--lx-t2); margin-left:2px; }
  .st .l { font-size:11px; color:var(--lx-t3); margin-top:5px; }

  /* ── 枪/盖状态胶囊 ── */
  .pills { display:flex; gap:8px; padding:14px 20px 0; flex-wrap:wrap; }
  .pill { display:inline-flex; align-items:center; gap:6px; font-size:12px;
          padding:6px 12px; border-radius:20px; background:var(--lx-card); color:var(--lx-t2); }
  .pill .d { width:6px; height:6px; border-radius:50%; background:var(--lx-t3); }
  .pill.on .d { background:var(--lx-green); }
  .pill.warn .d { background:var(--lx-orange); }
  /* ★ 2026-10-09：充电口盖胶囊可点开合（switch cpCtrl 实车实测可用）*/
  .pill.act { cursor:pointer; -webkit-tap-highlight-color:transparent; }
  .pill.act:hover { background:var(--lx-line); }
  .pill.act:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .pill.busy { opacity:.55; }
  .pill.ro { opacity:.75; }
  .pill .hint { font-size:10px; color:var(--lx-t3); }

  /* ★ 2026-10-09 新增：本卡片此前没有 toast 能力（无 .toast 元素/方法），
     而充电口盖开合必须给出明确反馈（下发中/失败原因），故补齐。 */
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:80%; text-align:center; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }

  /* ── 记录（年折叠）── */
  .sect { padding:18px 20px 0; }
  /* ★ 2026-10-11：充电类型筛选（对齐 App 的「全部/交流慢充/直流快充/理想超充」）*/
  .ctabs { display:flex; gap:22px; padding:2px 16px 0; overflow-x:auto;
           -webkit-overflow-scrolling:touch; }
  .ctab { font-size:14px; color:var(--lx-t3); padding:9px 0 11px; cursor:pointer;
          white-space:nowrap; position:relative; transition:color .15s; }
  .ctab:hover { color:var(--lx-t2); }
  .ctab.on { color:var(--lx-t1); font-weight:600; }
  .ctab.on::after { content:""; position:absolute; left:0; right:0; bottom:5px;
                    height:2.5px; border-radius:2px; background:var(--lx-blue); }
  .rec .tag.hpc { color:#B45309; background:rgba(180,83,9,.10); }
  @media (prefers-color-scheme: dark) {
    .rec .tag.hpc { color:#FBBF24; background:rgba(251,191,36,.14); }
  }
  .sect h2 { font-size:14px; font-weight:500; margin:0 0 10px; }
  /* ── 年份折叠卡片 ── */
  .year { border-radius:14px; background:var(--lx-card); margin-bottom:10px;
          overflow:hidden; }
  .year .yh { display:flex; align-items:center; min-height:52px; padding:0 16px;
              cursor:pointer; transition:background .15s; }
  .year .yh:hover { background:rgba(0,0,0,.03); }
  .year .yn { font-size:15px; font-weight:600; }
  .year .ys { margin-left:10px; font-size:12px; color:var(--lx-t3); }
  .year .ar { margin-left:auto; color:var(--lx-t3); transition:transform .2s;
              display:inline-block; }
  .year.open .yh .ar { transform:rotate(90deg); }
  /* 年内月份区（折叠） */
  .year .ym { display:none; }
  .year.open .ym { display:block; }

  /* ── 月份行（在年份卡片内，不再是独立卡片） ── */
  .month { border-top:1px solid var(--lx-line); }
  .month .mh { display:flex; align-items:center; min-height:48px; padding:0 16px;
               cursor:pointer; transition:background .15s; }
  .month .mh:hover { background:rgba(0,0,0,.03); }
  .month .mn { font-size:14px; color:var(--lx-t2); white-space:nowrap; min-width:52px; }
  .month .ar { margin-left:6px; color:var(--lx-t3); transition:transform .2s;
               display:inline-block; }
  .month.open .ar { transform:rotate(90deg); }
  /* ★ 内联明细：点开即在该月下方（车主明确要求的交互） */
  .month .md { display:none; padding:0 16px 8px 16px; }
  .month.open .md { display:block; }
  .month .md .rec { display:flex; align-items:center; min-height:40px;
                    border-top:1px dashed var(--lx-line); font-size:13px; }
  .month .md .rec .t { color:var(--lx-t2); min-width:104px; }
  .month .md .rec .tag { font-size:11px; padding:2px 7px; border-radius:6px;
                         color:var(--lx-t3); background:var(--lx-line); margin-right:8px; }
  .month .md .rec .tag.ac { color:#0A7B3E; background:rgba(10,123,62,.10); }
  .month .md .rec .tag.hpc { color:#B45309; background:rgba(180,83,9,.10); }
  .month .md .rec .c { margin-left:auto; font-family:"LxNum"; font-weight:500; }
  .month .md .rec .u { font-size:11px; color:var(--lx-t3); margin-left:3px; }
  .month .mbar { flex:1; height:6px; border-radius:3px; background:var(--lx-line);
                 overflow:hidden; margin:0 10px; min-width:30px; }
  .month .mbar > i { display:block; height:100%; border-radius:3px; background:#2C6BFF;
                     transition:width .3s ease; }
  .month.top .mv { color:var(--lx-t1); font-weight:600; }
  .month.top .mbar > i { background:#1E5AE0; }
  .month .mt { font-size:11px; color:var(--lx-t3); margin-left:8px; min-width:52px;
               text-align:right; white-space:nowrap; }
  .month .mv { font-family:"LxNum"; font-size:14px; font-weight:500; }
  .month .mu { font-size:11px; color:var(--lx-t3); margin-left:3px; }
  .empty { text-align:center; color:var(--lx-t3); font-size:13px; padding:16px 0; }

  /* ── 明细列表 ── */
  .list { padding:0 20px; }
  .listhead { font-size:12px; color:var(--lx-t3); padding:12px 0 6px; }
  .rec { display:flex; align-items:center; padding:10px 0;
         border-bottom:1px solid var(--lx-line); font-size:13px; }
  .rec:last-child { border-bottom:none; }
  .rec .tag { font-size:11px; padding:2px 7px; border-radius:6px;
              background:#EAF1FF; color:var(--lx-blue); margin-right:8px; }
  .rec .tag.ac { background:#E9F7EE; color:#2C9E4B; }
  .rec .t { color:var(--lx-t2); }
  .rec .c { margin-left:auto; font-family:"LxNum"; font-weight:500; }
  .rec .u { font-size:11px; color:var(--lx-t3); margin-left:3px; }

  /* ── 键盘可达：统一焦点样式（无障碍）── */
  [role="button"]:focus-visible, .card:focus-visible, .entry:focus-visible,
  .row.click:focus-visible, .m:focus-visible,
  button:focus-visible, input:focus-visible {
    outline: 2px solid var(--lx-blue, #0A58F6);
    outline-offset: 2px;
    border-radius: 8px;
  }
  /* 尊重「减少动态效果」偏好 */
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
  }

  /* ── 刷新按钮 ── */
  .refresh { width:30px; height:30px; border-radius:50%; display:flex;
             align-items:center; justify-content:center; cursor:pointer;
             transition:background .15s, transform .3s; }
  .refresh:hover { background:var(--lx-card); }
  .refresh:active { transform:scale(.9); }
  .refresh img { width:17px; height:17px; opacity:.6; }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }
  /* ── 状态提示（错误/空态）── */
  .state { text-align:center; padding:20px 16px; }
  .state .t { font-size:13.5px; color:var(--lx-t2); }
  .state .d { font-size:11.5px; color:var(--lx-t3); margin-top:6px; line-height:1.55; }
  .state .retry { display:inline-block; margin-top:12px; font-size:13px;
                  color:var(--lx-blue); cursor:pointer; padding:6px 16px;
                  border-radius:10px; background:rgba(10,88,246,.07); }
  .state .retry:hover { background:rgba(10,88,246,.12); }

  /* ── 下拉刷新 ── */
  .ptr { position:absolute; left:0; right:0; top:0; height:0; overflow:hidden;
         display:flex; align-items:center; justify-content:center;
         transition:height .2s ease; pointer-events:none; }
  .ptr .sp { width:20px; height:20px; border-radius:50%;
             border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
             animation:lspin .8s linear infinite; }
  .ptr .tx { font-size:11.5px; color:var(--lx-t3); margin-left:8px; }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      /* 官方在手机宽度也是【一行四列】，不压成两行 */
      .hero .metrics { grid-template-columns: repeat(4, minmax(0,1fr)); gap:4px; }
      .hero .m .v { font-size:19px; }
      .hero .m .v small { font-size:10px; margin-left:1px; }
      .hero .m .l { font-size:10.5px; }
      .stat3 { grid-template-columns: minmax(0,1fr) minmax(0,1fr); }
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangChargePage extends HTMLElement {

  /* ── 自动绑定（与 app-home 同一引擎，用户不用手填实体 ID）── */
  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) {
        out = new AB(this._hass, this._config || {}).resolve() || {};
      }
    } catch (e) { /* 引擎不可用时退回手填 */ }
    // ★ 只有非空结果才缓存：hass.entities 未就绪时返回 {} ，
    //   若缓存会导致永久空绑定（真实踩过的坑）
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  /** 取实体：手填配置 > 自动发现 */
  _eid(field) {
    const c = this._config || {};
    const manual = c[field];
    if (typeof manual === "string" && manual.includes(".")) return manual;
    return (this._autoBind() || {})[field] || null;
  }

  /** 嵌套组也支持自动发现 */
  _eidIn(group, key) {
    const c = this._config || {};
    const m = (c[group] || {})[key];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[key] || null;
  }

  /**
   * 让元素键盘可达（无障碍）。
   * 用法：this._a11y(el, "车锁", handler)
   */
  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        handler(e);
      }
    });
  }
  setConfig(config) {
    this._config = config || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base;
    this._openYears = new Set();
    this._selMonth = null;
    this._years = null;
    // ★ 充电类型筛选：默认 0=全部（聚合 4 种类型，与 App 一致）
    if (this._ctIdx === undefined) { this._ctIdx = 0; }
    if (this._ctype === undefined) { this._ctype = _CTYPES[0].value; }
    this._monthRecords = null;
    this._built = false;
  }
  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    this._update();
  }
  getCardSize() { return 16; }

  disconnectedCallback() {
    // 清理定时器与监听，避免卡片被移除后仍持有引用（内存泄漏）
    if (this._tt) { clearTimeout(this._tt); this._tt = null; }
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
    if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; }
    this._fetching = false;
    this._fetchingYears = false;
  }

  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown", "unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id); return s ? s.state : null; }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style");
    st.textContent = STYLE; this.appendChild(st);
    const c = this._config;
    const root = document.createElement("div");
    root.className = "root";
    root.dataset.theme = c.theme || "light";
    root.innerHTML = `
      <div class="ptr" id="ptr"><div class="sp"></div><div class="tx">下拉刷新</div></div>
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="返回">
        <h1>${I18N.title}</h1>
        <button class="reclink" id="go-records" type="button">${I18N.records}</button>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新数据">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="" style="transform:rotate(-90deg)">
        </div>
      </div>
      <div class="hero">
        <div class="row1">
          <span class="dot" id="dot"></span>
          <span class="st" id="st">—</span>
          <span class="sub" id="sub"></span>
        </div>
        <!-- ★ 2026-10-14 对齐官方「充电管理」页：环形电量表（SOC + 绿弧 + 闪电） -->
        <div class="ringwrap">
          <svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
            <circle class="rbg" cx="60" cy="60" r="52"></circle>
            <circle class="rfg" id="ring-arc" cx="60" cy="60" r="52"></circle>
          </svg>
          <img class="bolt" src="${__iconBase}/ic_home_lightning.png" onerror="__lxIconFallback(this)" alt="">
          <div class="rtx"><span id="ring-soc">—</span><small>%</small></div>
        </div>
        <div class="remline" id="rem-text">—</div>
        <div class="metrics">
          <div class="m"><div class="v"><span id="m-power">—</span><small id="u-power">km/hr</small></div>
            <div class="l">${I18N.power}</div></div>
        <div class="m"><div class="v"><span id="m-pw">—</span><small>kW</small></div>
          <div class="l">${I18N.powerKw}</div></div>
        <div class="m"><div class="v"><span id="m-amp">—</span><small id="u-amp">A</small></div>
          <div class="l">${I18N.amp}</div></div>
        <div class="m"><div class="v"><span id="m-volt">—</span><small id="u-volt">V</small></div>
          <div class="l">${I18N.volt}</div></div>
        </div>
      </div>
      <!-- ★ 2026-10-14 对齐官方：充电上限可拖滑杆 + 提示原文 -->
      <div class="limitbox">
        <div class="lbrow1"><span>${I18N.limit}</span><b id="limitp">—</b></div>
        <input class="rng" type="range" id="limit-range" min="50" max="100" step="1" value="100"
               aria-label="${I18N.limit}">
        <div class="lbrow2"><span id="limit-min">50%</span><span id="limit-max">100%</span></div>
        <div class="hint">${I18N.hint}</div>
      </div>
      <div class="setcard">
        <div class="setrow"><span class="sl">${I18N.appt}</span>
          <span class="tg" id="tg-appt" role="switch" tabindex="0" aria-checked="false"><i></i></span></div>
        <div class="setrow"><span class="sl">${I18N.apptEnd}</span>
          <input class="tmin" type="time" id="end-time" aria-label="${I18N.apptEnd}"></div>
      </div>
      <div class="pfoot">${I18N.footer}</div>
      <div class="stat3">
        <div class="st"><div class="v"><span id="m-mode">—</span></div>
            <div class="l">${I18N.mode}</div></div>
        <div class="st"><div class="v"><span id="s-month">—</span><small>kWh</small></div>
          <div class="l">${I18N.monthKwh}</div></div>
        <div class="st"><div class="v"><span id="s-times">—</span><small>${I18N.times}</small></div>
          <div class="l">${I18N.monthTimes}</div></div>
        <div class="st"><div class="v"><span id="s-total">—</span><small>kWh</small></div>
          <div class="l">${I18N.totalKwh}</div></div>
      </div>
      <div class="pills">
        <span class="pill" id="p-ac"><span class="d"></span>${I18N.acGun} <b id="v-ac">—</b></span>
        <span class="pill" id="p-dc"><span class="d"></span>${I18N.dcGun} <b id="v-dc">—</b></span>
        <span class="pill" id="p-cover" role="button" tabindex="0"
              aria-label="${I18N.portCover} ${I18N.coverTapHint}"><span class="d"></span>${I18N.portCover} <b id="v-cover">—</b></span>
        <span class="pill" id="p-appt"><span class="d"></span>${I18N.appt} <b id="v-appt">—</b></span>
        <span class="pill" id="p-fault"><span class="d"></span>${I18N.fault} <b id="v-fault">—</b></span>
      </div>
      <div class="ctabs" id="ctabs" role="tablist"
           aria-label="${I18N.history}${I18N.chargeType}">
        ${_CTYPES.map((c, i) => `<span class="ctab${i === 0 ? " on" : ""}" role="tab"
            data-ct="${i}" tabindex="0"
            aria-selected="${i === 0 ? "true" : "false"}">${c.label}</span>`).join("")}
      </div>
      <div class="sect">
        <h2>${I18N.history}</h2>
        <div id="years"><div class="empty">${I18N.loading}</div></div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const _bk = this.querySelector("#back");
    this._a11y(_bk, "返回", () => _bk.click());
    _bk.addEventListener("click", () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    });
    // ★ 2026-10-14 官方充电管理页：上限滑杆 / 预约开关 / 按时结束 / 记录入口
    const rng = this.querySelector("#limit-range");
    if (rng) {
      rng.addEventListener("change", async () => {
        const eid = this._eid("limit_num");
        if (!eid) { this._toast("充电上限不可设置", "err"); return; }
        const v = Number(rng.value);
        try {
          await this._hass.callService("number", "set_value", { entity_id: eid, value: v });
          this._toast("充电上限已设为 " + v + "%", "ok");
        } catch (err) { this._toast("设置失败：" + ((err && err.message) || "未知"), "err"); }
      });
    }
    const tgEl = this.querySelector("#tg-appt");
    if (tgEl) {
      const flip = async () => {
        const eid = this._eid("appt_sw");
        if (!eid) { this._toast("预约充电不可用", "err"); return; }
        const st = this._hass && this._hass.states ? this._hass.states[eid] : null;
        const on = !!(st && st.state === "on");
        try {
          await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: eid });
          tgEl.classList.toggle("on", !on);
          tgEl.setAttribute("aria-checked", !on ? "true" : "false");
          this._toast(I18N.appt + (on ? "已关闭" : "已开启"), "ok");
        } catch (err) { this._toast("操作失败：" + ((err && err.message) || "未知"), "err"); }
      };
      this._a11y(tgEl, I18N.appt, flip);
      tgEl.addEventListener("click", flip);
    }
    const teEl = this.querySelector("#end-time");
    if (teEl) {
      teEl.addEventListener("change", async () => {
        const eid = this._eid("end_time");
        if (!eid || !teEl.value) { this._toast("按时结束不可设置", "err"); return; }
        try {
          await this._hass.callService("time", "set_value", { entity_id: eid, time: teEl.value + ":00" });
          this._toast(I18N.apptEnd + " " + teEl.value, "ok");
        } catch (err) { this._toast("设置失败：" + ((err && err.message) || "未知"), "err"); }
      });
    }
    const rec = this.querySelector("#go-records");
    if (rec) {
      const go = () => {
        const t = this.querySelector("#ctabs") || this.querySelector("#years");
        if (t && t.scrollIntoView) t.scrollIntoView({ behavior: "smooth", block: "start" });
      };
      this._a11y(rec, I18N.records, go);
      rec.addEventListener("click", go);
    }
    // ★ 2026-10-11：充电类型筛选绑定（漏了这行就只是"画了不响应"）
    this._bindCTypes();
    const rf2 = this.querySelector("#refresh");
    const doRefresh2 = () => this._refreshAll();
    this._a11y(rf2, "刷新数据", doRefresh2);
    rf2.addEventListener("click", doRefresh2);

    // ★ 2026-10-09：充电口盖胶囊可点开合（switch cpCtrl，实车实测可用）
    const pcv = this.querySelector("#p-cover");
    if (pcv) {
      const doCover = () => this._toggleCover();
      this._a11y(pcv, `${I18N.portCover} ${I18N.coverTapHint}`, doCover);
      pcv.addEventListener("click", doCover);
    }

    
    // ── 下拉刷新（触摸手势，对齐 App）──
    (() => {
      const ptr = this.querySelector("#ptr");
      const rootEl = this.querySelector(".root");
      if (!ptr || !rootEl) return;
      let startY = 0, pulling = false, dist = 0;
      const TH = 64;
      rootEl.addEventListener("touchstart", (e) => {
        if (window.scrollY > 4) return;
        startY = e.touches[0].clientY; pulling = true; dist = 0;
      }, { passive: true });
      rootEl.addEventListener("touchmove", (e) => {
        if (!pulling) return;
        dist = e.touches[0].clientY - startY;
        if (dist > 0 && window.scrollY <= 4) {
          const h = Math.min(dist * 0.55, 70);
          ptr.style.height = h + "px";
          ptr.querySelector(".tx").textContent = h >= TH * 0.5 ? "松开刷新" : "下拉刷新";
        }
      }, { passive: true });
      rootEl.addEventListener("touchend", () => {
        if (!pulling) return;
        pulling = false;
        const h = parseFloat(ptr.style.height) || 0;
        if (h >= TH * 0.5) {
          ptr.style.height = "44px";
          ptr.querySelector(".tx").textContent = "刷新中…";
          Promise.resolve(this._refreshAll()).finally(() => {
            setTimeout(() => { ptr.style.height = "0px"; }, 500);
          });
        } else {
          ptr.style.height = "0px";
        }
        dist = 0;
      }, { passive: true });
    })();

    this._built = true;
  }

  /** ★ 2026-10-14 时长格式化：官方「剩余2小时7分钟」（不是 185 min）。 */
  _fmtDur(minutes) {
    const t = Math.max(0, Math.round(Number(minutes) || 0));
    const h = Math.floor(t / 60), m = t % 60;
    if (h <= 0) return m + I18N.min;
    if (m === 0) return h + I18N.hour;
    return h + I18N.hour + m + I18N.min;
  }

  /** ★ 2026-10-14 上限滑杆：范围取 number 实体的 min/max（官方页显示 80%–100%）。 */
  _syncLimitSlider(lim) {
    const r = this.querySelector("#limit-range");
    if (!r) return;
    const st = this._hass && this._hass.states ? this._hass.states[this._eid("limit_num")] : null;
    const a = (st && st.attributes) || {};
    const mn = Number.isFinite(Number(a.min)) ? Number(a.min) : 50;
    const mx = Number.isFinite(Number(a.max)) ? Number(a.max) : 100;
    r.min = String(mn); r.max = String(mx);
    const v = lim == null ? mx : Math.max(mn, Math.min(mx, lim));
    if (document.activeElement !== r) r.value = String(Math.round(v));
    const pct = mx > mn ? ((v - mn) / (mx - mn)) * 100 : 100;
    r.style.setProperty("--fill", pct + "%");
    const la = this.querySelector("#limit-min"), lb = this.querySelector("#limit-max");
    if (la) la.textContent = mn + "%";
    if (lb) lb.textContent = mx + "%";
  }

  /** 轻提示（★ 2026-10-09 新增：充电口盖开合需要"已下发/失败原因"的明确反馈） */
  _toast(msg, kind) {
    const t = this.querySelector(".toast");
    if (!t) return;
    t.textContent = msg;
    t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2600);
  }

  /** ★ 2026-10-09：开合充电口盖（switch 域，cmdKey=cpCtrl；实车实测可用）。
   *  不可控时（旧版本 / 车型无此实体）给出明确说明，不静默失败。 */
  async _toggleCover() {
    const sw = this._eid("port");
    if (!sw) {
      this._toast(`${I18N.portCover}控制未接入（仅显示状态）`, "err");
      return;
    }
    const st = this._st(sw);
    if (!st) { this._toast("实体不存在", "err"); return; }
    if (this._coverBusy) return;
    const on = ["on", "open", "opening", "开启", "true"].some(
      (v) => String(st.state).includes(v));
    this._coverBusy = true;
    const el = this.querySelector("#p-cover");
    if (el) el.classList.add("busy");
    try {
      await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: sw });
      // 开合需要数秒，服务端状态回读更慢 → 用 12s 乐观值
      this._coverOptim = !on; this._coverOptimUntil = Date.now() + 12000;
      this._toast(`${I18N.portCover}${on ? "关闭" : "开启"}指令已下发`, "ok");
      this._update();
      setTimeout(() => { this._coverOptim = null; this._update(); }, 12000);
    } catch (e) {
      this._toast(`${I18N.portCover}操作失败：` + ((e && e.message) || "未知"), "err");
    } finally {
      this._coverBusy = false;
      if (el) el.classList.remove("busy");
    }
  }

  /** 手动刷新 */
  async _refreshAll() {
    const rf = this.querySelector("#refresh");
    if (rf) rf.classList.add("spin");
    this._years = null; this._monthRecords = null; this._fetching = false;
    this._error = null;
    try {
      await this._fetchStats();
      if (this._selMonth) await this._fetchMonth(this._selMonth.year, this._selMonth.month);
    } finally {
      if (rf) rf.classList.remove("spin");
      this._renderYears(); this._renderList();
    }
  }

  /** ★ 2026-10-09：充电口盖胶囊 = 可点开合（有 switch 时）+ 状态显示。
   *  状态优先取可控制的 switch（cpCtrl），无则退到只读 binary_sensor（旧版本）。 */
  _updateCover() {
    const q = (s) => this.querySelector(s);
    const sw = this._eid("port");
    const ro = this._eid("port_cover");
    let on = null;
    if (this._coverOptim != null && Date.now() < (this._coverOptimUntil || 0)) {
      on = this._coverOptim;                       // 乐观值（开合需数秒）
    } else {
      const src = (sw && this._st(sw)) ? sw : ro;
      const v = this._txt(src);
      if (v != null) {
        on = ["on", "open", "opening", "开启", "true"].some(
          (x) => String(v).includes(x));
      }
    }
    const val = q("#v-cover");
    if (val) {
      val.textContent = on == null ? "—" : (on ? I18N.coverOpen : I18N.coverClose);
    }
    const el = q("#p-cover");
    if (el) {
      el.className = "pill" + (on === true ? " on" : "")
                   + (sw ? " act" : " ro")
                   + (this._coverBusy ? " busy" : "");
      el.setAttribute("aria-pressed", on === true ? "true" : "false");
      el.title = sw ? `${I18N.portCover}${I18N.coverTapHint}` : "该版本仅支持查看状态";
    }
  }

  /** ★ 2026-10-11：绑定充电类型筛选（切换后重新拉取该类型的统计）。 */
  _bindCTypes() {
    const box = this.querySelector("#ctabs");
    if (!box) return;
    box.querySelectorAll(".ctab").forEach((el) => {
      const i = Number(el.dataset.ct);
      const a = () => this._switchCType(i);
      this._a11y(el, _CTYPES[i] ? _CTYPES[i].label : "筛选", a);
      el.addEventListener("click", a);
      // 键盘可达（role=tab）
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); a(); }
      });
    });
  }

  _switchCType(i) {
    if (!_CTYPES[i] || this._ctIdx === i) return;
    this._ctIdx = i;
    this._ctype = _CTYPES[i].value;
    // 视觉：选中态 + aria
    this.querySelectorAll(".ctab").forEach((el, k) => {
      const on = k === i;
      el.classList.toggle("on", on);
      el.setAttribute("aria-selected", on ? "true" : "false");
    });
    // 数据：清缓存 → 重新拉该类型（_fetchStats 的守卫依赖 _years 为空）
    this._years = null;
    this._selMonth = null;
    this._error = null;
    // ★ 新一轮数据：重置年份展开状态，让其重新默认展开最新年
    this._yearsInited = false;
    this._openYears = new Set();
    const box = this.querySelector("#years");
    if (box) box.innerHTML = `<div class="empty">${I18N.loading}</div>`;
    this._fetchStats();
  }

  async _fetchStats() {
    if (!this._hass || this._years || this._fetching) return;
    this._fetching = true;
    try {
      // ★ 带上当前筛选类型（0=全部聚合 / 1=DC / 2=AC / "hpc"=理想超充）
      const r = await this._hass.callService("lixiang_auto", "get_charge",
        { charging_type: this._ctype }, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const rows = first && first.data;   // [{year, month, chargingTimes, chargingCapacity}]
      if (Array.isArray(rows) && rows.length) {
        // 按年分组
        const byYear = {};
        rows.forEach((x) => {
          const y = String(x.year);
          (byYear[y] = byYear[y] || []).push(x);
        });
        this._years = Object.keys(byYear).sort((a, b) => b - a).map((y) => ({
          year: Number(y),
          months: byYear[y].sort((a, b) => b.month - a.month),
        }));
        const y0 = this._years[0] && this._years[0].year;
        if (y0 != null) this._openYears.add(String(y0));
        this._renderYears();
        // ★ 数据到位 → 补刷顶部「本月次数」（之前只刷记录区，导致它永远停在「—」）
        this._updateStats();
      }
    } catch (e) {
      this._error = (e && e.message) || "网络请求失败";
    } finally { this._fetching = false; }
  }

  async _fetchMonth(year, month) {
    if (!this._hass) return;
    this._monthRecords = null; this._renderList();
    try {
      // ★★ 2026-10-11 修复（与月度统计同类）：
      //   原来手写两次请求，只拉 AC(2) + DC(1) —— **漏掉 5C(3)/4C(4) 超充**，
      //   且**不跟随筛选**（选「理想超充」仍显示全部类型）。
      //   服务端 charging_type=0 会聚合全部 4 种；"hpc" 聚合 3+4。
      //   故一次请求即可，并把当前筛选传下去。
      const r = await this._hass.callService("lixiang_auto", "get_charge",
        { dt: `${year}-${month}`, charging_type: this._ctype }, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const rows = first && first.data;
      if (Array.isArray(rows)) this._monthRecords = rows;
    } catch (e) { /* 静默 */ }
    this._renderList();
  }

  /** 渲染月度列表。
   *
   * ★★ 2026-10-11 结构重构（车主反馈：「点击10月，明细在下面，根本看不到」）：
   *   原先按【年折叠】+ 明细渲染在页面底部的另一个区域（#list）→ 用户点完
   *   要滚到页面下方才看得到，体验很差。
   *   现改为 App 的结构：**扁平月度列表 + 点击月份内联展开明细**。
   *   · 非最新年份显示「2025年8月」前缀（同年只显示「8月」），与 App 一致
   *   · 明细插在该月**下方**，点开即见
   */
  /** 渲染月度列表。
   *
   * 结构演进（两次都由车主反馈驱动）：
   *  ① 原先「按年折叠 + 明细渲染在页面底部」→ 车主："点击10月，明细在下面，根本看不到"
   *     → 改为扁平 + 内联明细
   *  ② 但扁平列表在年份多时会很长 → 车主："充电明细建议按年也折叠"
   *     → **年份折叠 + 月份内联明细**（兼顾：列表短 + 点开即见）
   *
   * 年份头带汇总（月数 / 总次数 / 总电量）；默认展开最新年份。
   */
  _renderYears() {
    const box = this.querySelector("#years");
    if (!box) return;
    const yl = this._years;
    if (!yl || !yl.length) {
      if (this._error) {
        box.innerHTML = `<div class="state"><div class="t">充电记录加载失败</div>
          <div class="d">${this._error}<br>可能是网络波动或车辆服务暂时不可用</div>
          <div class="retry" id="retry2">重新加载</div></div>`;
        const r = box.querySelector("#retry2");
        if (r) { this._a11y(r, "重新加载", () => this._refreshAll());
                 r.addEventListener("click", () => this._refreshAll()); }
      } else if (this._fetching) {
        box.innerHTML = `<div class="state"><div class="t">${I18N.loading}</div>
          <div class="d">正在从车辆获取充电记录…</div></div>`;
      } else {
        box.innerHTML = `<div class="state"><div class="t">暂无充电记录</div>
          <div class="d">车辆尚未产生充电数据</div></div>`;
      }
      return;
    }
    if (!(this._openYears instanceof Set)) this._openYears = new Set();
    // ★★ 2026-10-12 修复（车主："26年好像折叠不了"）：
    //   原写法 `if (!this._openYears.size) add(latest)` 会在**每次渲染**时检查，
    //   于是「折叠唯一展开的年份 → 集合变空 → 重渲染又被自动展开」→ **永远折不上**。
    //   改为【每个数据周期只初始化一次】：切换筛选/重新拉取时才重置。
    const latest = yl[0] && yl[0].year;
    if (!this._yearsInited) {
      this._yearsInited = true;
      if (latest != null) this._openYears.add(String(latest));
    }

    box.innerHTML = yl.map((y) => {
      const months = y.months || [];
      const open = this._openYears.has(String(y.year));
      const totKwh = months.reduce((a, m) => a + (Number(m.chargingCapacity) || 0), 0);
      const totTimes = months.reduce((a, m) => a + (Number(m.chargingTimes) || 0), 0);
      // 条形按【所在年】归一（跨年不可比）
      const mx = Math.max(1, ...months.map((m) => Number(m.chargingCapacity) || 0));
      const rows = months.map((m) => {
        const sel = this._selMonth && this._selMonth.year === y.year
                    && this._selMonth.month === m.month;
        const v = Number(m.chargingCapacity) || 0;
        const w = v > 0 ? Math.max(3, Math.round((v / mx) * 100)) : 0;
        const isTop = v > 0 && v >= mx;
        return `<div class="month${sel ? " open" : ""}${isTop ? " top" : ""}"
                     data-y="${y.year}" data-m="${m.month}">
            <div class="mh" role="button" tabindex="0"
                 aria-expanded="${sel ? "true" : "false"}">
              <span class="mn">${m.month} 月</span>
              <span class="mt">${I18N.chargePrefix || ""}${m.chargingTimes} ${I18N.times}</span>
              <span class="mbar" aria-hidden="true"><i style="width:${w}%"></i></span>
              <span class="mv">${Number(m.chargingCapacity).toFixed(2)}</span>
              <span class="mu">kW·h</span>
              <span class="ar">›</span>
            </div>
            <div class="md" id="md-${y.year}-${m.month}"></div>
          </div>`;
      }).join("");
      if (!months.length) return "";
      return `<div class="year${open ? " open" : ""}" data-year="${y.year}">
          <div class="yh" role="button" tabindex="0" aria-expanded="${open ? "true" : "false"}">
            <span class="yn">${y.year} 年</span>
            <span class="ys">${months.length} 个月 · ${totTimes} ${I18N.times} · ${totKwh.toFixed(1)} kW·h</span>
            <span class="ar">›</span>
          </div>
          <div class="ym">${rows}</div>
        </div>`;
    }).join("");

    // 年份头：折叠/展开
    box.querySelectorAll(".yh").forEach((h) => {
      const wrap = h.parentElement;
      const yy = wrap.dataset.year;
      const toggle = () => {
        if (this._openYears.has(yy)) this._openYears.delete(yy);
        else this._openYears.add(yy);
        this._renderYears();
      };
      this._a11y(h, `${yy} 年 展开/收起`, toggle);
      h.addEventListener("click", toggle);
      h.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    });

    // 月份行：内联展开明细（保留车主认可的交互）
    box.querySelectorAll(".mh").forEach((h) => {
      const wrap = h.parentElement;
      const yy = Number(wrap.dataset.y), mm = Number(wrap.dataset.m);
      const toggle = async () => {
        const isOpen = this._selMonth && this._selMonth.year === yy
                       && this._selMonth.month === mm;
        if (isOpen) {
          this._selMonth = null; this._monthRecords = null;
          wrap.classList.remove("open");
          h.setAttribute("aria-expanded", "false");
          const d = wrap.querySelector(".md"); if (d) d.innerHTML = "";
          return;
        }
        this._selMonth = { year: yy, month: mm };
        box.querySelectorAll(".month.open").forEach((el) => {
          el.classList.remove("open");
          const hh = el.querySelector(".mh");
          if (hh) hh.setAttribute("aria-expanded", "false");
          const dd = el.querySelector(".md"); if (dd) dd.innerHTML = "";
        });
        wrap.classList.add("open");
        h.setAttribute("aria-expanded", "true");
        const container = wrap.querySelector(".md");
        if (container) container.innerHTML = `<div class="empty">${I18N.loading}</div>`;
        await this._fetchMonth(yy, mm);
      };
      this._a11y(h, `${yy} 年 ${mm} 月 充电明细`, toggle);
      h.addEventListener("click", toggle);
      h.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    });
  }

  _renderList() {
    if (!this._selMonth) return;
    const box = this.querySelector(
      `#md-${this._selMonth.year}-${this._selMonth.month}`);
    if (!box) return;
    const rows = this._monthRecords || [];
    if (!rows.length) {
      box.innerHTML = `<div class="empty">${I18N.noData}</div>`;
      return;
    }
    const sorted = rows.slice().sort((a, b) => Number(b.startTime) - Number(a.startTime));
    box.innerHTML = sorted.map((r) => {
      const d = new Date(Number(r.startTime));
      const mm = `${d.getMonth() + 1}月${d.getDate()}日`;
      const hh = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      // ★ 按 chargingType 给出准确类型名（1=DC / 2=AC / 3=5C / 4=4C超充）
      const ct = Number(r.chargingType);
      const _names = { 1: I18N.ctDc, 2: I18N.ctAc, 3: I18N.ct5c, 4: I18N.ct4c };
      const _cls = { 1: "", 2: " ac", 3: " hpc", 4: " hpc" };
      const tagName = _names[ct] || I18N.ctDc;
      return `<div class="rec">
          <span class="t">${mm} ${hh}</span>
          <span class="tag${_cls[ct] !== undefined ? _cls[ct] : ""}">${tagName}</span>
          <span class="c">${Number(r.chargingCapacity).toFixed(2)}</span><span class="u">kW·h</span>
        </div>`;
    }).join("");
  }

  _update() {
    if (!this._built) return;
    const c = this._config, q = (s) => this.querySelector(s);

    // 充电状态
    const stt = this._txt(this._eid("status_charge"));
    const done = this._txt(this._eid("complete"));
    const isCharging = stt && String(stt).includes("充电中");
    const isDone = done && String(done).includes("完成");
    q("#st").textContent = isCharging ? I18N.charging : (isDone ? I18N.done : (stt || "—"));
    q("#dot").className = "dot" + (isCharging ? " on" : "");
    const fault = this._txt(this._eid("fault"));
    if (fault && String(fault) !== "off" && String(fault) !== "正常") {
      q("#dot").className = "dot err";
    }
    // ★ 2026-10-14：状态行已显示「充电中」，这里不再重复一遍（官方页状态由环形表表达）
    q("#sub").textContent = fault && String(fault) !== "off" && String(fault) !== "正常" ? "充电故障" : "";

    // ★ 2026-10-16 车主（截图标注）：「这个信息可否在不充电时自动隐藏起来?」
    //   未充电时 4 项指标恒为「—」（截图：20% · 剩余0分钟 · — km/hr — kW — A — V），
    //   一片空值既占版面又像坏掉 → **只在充电中显示**。
    //   判定复用上面的 isCharging（充电状态含「充电中」），与环形表/闪电同一口径。
    //   ⚠️ 用 style.display 而不是 hidden 属性：`.hero .metrics{display:grid}` 特异性更高，
    //      会盖掉 [hidden] 的默认 display:none（这条坑在仓库里出现过多次）。
    const mBox = q(".hero .metrics");
    if (mBox) mBox.style.display = isCharging ? "" : "none";

    // ★ 2026-10-14 对齐官方：环形电量表（SOC）+ 上限滑杆
    const lim = this._num(this._eid("limit") || this._eid("limit_sensor"));
    const soc = this._num(this._eid("soc"));
    const arc = q("#ring-arc");
    if (arc) {
      const C = 2 * Math.PI * 52;
      const frac = soc == null ? 0 : Math.max(0, Math.min(100, soc)) / 100;
      arc.style.strokeDasharray = C + " " + C;
      arc.style.strokeDashoffset = String(C * (1 - frac));
    }
    const rs = q("#ring-soc");
    if (rs) rs.textContent = soc == null ? "—" : String(Math.round(soc));
    q("#limitp").textContent = lim == null ? "—" : lim + "%";
    this._syncLimitSlider(lim);
    // 预约充电开关 / 按时结束
    const apptEid = this._eid("appt_sw");
    const apptSt = apptEid && this._hass && this._hass.states ? this._hass.states[apptEid] : null;
    const tg0 = q("#tg-appt");
    if (tg0) {
      const on = !!(apptSt && apptSt.state === "on");
      tg0.classList.toggle("on", on);
      tg0.setAttribute("aria-checked", on ? "true" : "false");
      tg0.setAttribute("aria-label", I18N.appt + (on ? "（已开启）" : "（已关闭）"));
    }
    const te0 = q("#end-time");
    if (te0 && document.activeElement !== te0) {
      const tSt = this._hass && this._hass.states[this._eid("end_time")];
      const tv = tSt && tSt.state && /^\d{1,2}:\d{2}/.test(tSt.state) ? tSt.state.slice(0, 5) : "";
      te0.value = tv;
    }

    // 三项
    const p = this._num(this._eid("power")), rm = this._num(this._eid("remain")), md = this._txt(this._eid("mode"));
    q("#m-power").textContent = p == null ? "—" : p;
      // ★ 2026-10-14 单位跟随实体（官方是 km/hr；原来写死 kW 是错的）
      const pSt = this._hass && this._hass.states[this._eid("power")];
      const pU = (pSt && pSt.attributes && pSt.attributes.unit_of_measurement) || "km/hr";
      const uEl = q("#u-power"); if (uEl) uEl.textContent = pU;
    // ★ 2026-10-14 官方格式：「剩余2小时7分钟」（原来显示 185 min）
    const rEl = q("#rem-text");
    if (rEl) {
      rEl.textContent = rm == null ? I18N.remainPrefix + " —" : I18N.remainPrefix + this._fmtDur(rm);
      // ★ 2026-10-17 车主：「剩余充电时间没显示」
      //   实测：正在充电（6.54 kW）但 `剩余充电时间` 实体是 **0**（连续 40 次轮询都是 0）。
      //   官方 Hermes 包证据：App 取的也是
      //     'Vehicle.Powertrain.Battery.ChargeSurplusTime'（还有 remainTime / remainTimeMintueTip）
      //   —— 与我们同一路径，所以 **车此刻就是没给估值**，App 也拿不到。
      //   那就不能显示「剩余0分钟」这种假信息：只在真有时长时才显示。
      const mins = rm == null ? null : Math.max(0, Math.round(Number(rm) || 0));
      // ★ 2026-10-17 按官方 PowerDisplay 分支（Hermes 包还原）：
      //   有值 → 剩余X小时Y分钟 ｜ 充电中但值=0 → "充电校准中，预计5-10分钟"
      //   ｜ 未充电且无值 → 收起
      if (mins && mins > 0) {
        rEl.textContent = I18N.remainPrefix + this._fmtDur(mins);
        rEl.hidden = false;
      } else if (isCharging) {
        rEl.textContent = I18N.calibrating;
        rEl.hidden = false;
      } else {
        rEl.hidden = true;
      }
    }
      // ★ 官方 4 项指标之三/四：输入电压 / 输入电流（单位跟随实体）
      const Sx = (id) => (id && this._hass && this._hass.states) ? this._hass.states[id] : null;
      const vSt = Sx(this._eid("charge_voltage")), aSt = Sx(this._eid("charge_current"));
      const okv = (x) => x && x.state && !["unknown", "unavailable"].includes(x.state);
      q("#m-volt").textContent = okv(vSt) ? vSt.state : "—";
      q("#m-amp").textContent = okv(aSt) ? aSt.state : "—";
      const uv = q("#u-volt"), ua = q("#u-amp");
      if (uv && vSt && vSt.attributes && vSt.attributes.unit_of_measurement) uv.textContent = vSt.attributes.unit_of_measurement;
      if (ua && aSt && aSt.attributes && aSt.attributes.unit_of_measurement) ua.textContent = aSt.attributes.unit_of_measurement;
      q("#m-pw").textContent = this._num(this._eid("charge_power")) == null ? "—" : this._num(this._eid("charge_power"));
    q("#m-mode").textContent = md || "—";
    q("#m-mode").className = "v" + ((md && isNaN(parseFloat(md))) ? " txt" : "");

    this._updateStats();
  }

  /** ★ 2026-10-17 修「本月充电次数没正确显示」
   *
   *  根因（时序）：`_update()` 先跑（此时 _years 还是 null → 本月次数显示「—」），
   *  末尾才 `this._fetchStats()` **不 await**；等月度统计回来后，`_fetchStats()`
   *  只调了 `_renderYears()`（记录区），**没有刷新顶部统计** →
   *  本月次数就一直停在「—」（只有手动点刷新才会好）。
   *
   *  修法：把电量三栏抽成 `_updateStats()`，月度统计到位后单独调它 ——
   *  不整卡重绘（避免连带把车图/滑杆/地图重画一遍）。
   */
  _updateStats() {
    const q = (s) => this.querySelector(s);
    const mk = this._num(this._eid("month_kwh"));
    let tk = this._num(this._eid("month_times"));      // ★ let（下方可能回填）
    const tot = this._num(this._eid("total_kwh"));
    q("#s-month").textContent = mk == null ? "—" : mk;
    if (tk == null && this._years && this._years.length) {
      const y0 = this._years[0];
      const mCur = new Date().getMonth() + 1;
      const hit = (y0.months || []).find((x) => x.month === mCur);
      tk = hit ? Number(hit.chargingTimes) : null;
    }
    if (tk == null && this._years && this._years.length) {
      const cur = new Date().getMonth() + 1;
      const y0 = this._years[0] || {};
      const hit = (y0.months || []).find((x) => Number(x.month) === cur);
      if (hit && hit.chargingTimes != null) tk = hit.chargingTimes;
    }
    q("#s-times").textContent = tk == null ? "—" : tk;
    q("#s-total").textContent = tot == null ? "—" : tot;

    // 胶囊
    const set = (pill, val, eid) => {
      const v = this._txt(eid);
      q(val).textContent = v == null ? "—" : (v === "on" ? "已连接" : (v === "off" ? "未连接" : v));
      const el = q(pill);
      if (el) el.className = "pill" + (v === "on" ? " on" : "");
    };
    set("#p-ac", "#v-ac", this._eid("ac_gun"));
    set("#p-dc", "#v-dc", this._eid("dc_gun"));
    this._updateCover();
    set("#p-appt", "#v-appt", this._eid("appointment"));
    const fv = this._txt(this._eid("fault"));
    q("#v-fault").textContent = fv == null ? "—" : (fv === "off" ? "正常" : fv);
    q("#p-fault").className = "pill" + (fv && fv !== "off" ? " warn" : "");

    this._fetchStats();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangChargePage);

window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "充电（二级页）",
  description: "充电实时状态 + 按月记录（年折叠）+ 单次明细",
  preview: true,
});
})();

/* ===================== lixiang-energy-page.js ===================== */
(function () {

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


/**
 * lixiang-energy-page —— 里程能耗（二级页，对齐 App 真实版）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   顶栏：‹ 里程能耗 查询
 *   「理想L6已经陪伴您800天」（大字）
 *   主卡：环形图（绿=耗电行驶 87% + 蓝=耗油行驶 13%），中心大数字=陪伴里程
 *        底部两项：87% ⚡耗电行驶 | 13% 💧耗油行驶
 *   智驾卡：「已使用智能驾驶 N 天，行驶 N km」
 *          + 两个环形（36% 占总天数 / 14% 占总里程）
 *   免责文案
 *   年份折叠：2026年⌃ / 2025年⌃ / 2024年⌃
 */

const CARD_TAG = "lixiang-energy-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const I18N = {
  title: "里程能耗", query: "查询",
  companion: "已经陪伴您", days: "天",
  partnerKm: "陪伴里程km",
  elec: "耗电行驶", fuel: "耗油行驶",
  adTitle: "已使用智能驾驶", adDrive: "，行驶",
  dayRatio: "占总天数", kmRatio: "占总里程",
  disclaimer: "数据在每次驾驶循环后更新，可能存在延迟，请以车端数据为准。",
  noData: "暂无数据", loading: "加载中…", retry: "重新加载",
  loadFail: "数据加载失败",
};

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-energy-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-energy-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; }
  .back { width:30px; height:30px; opacity:.75; cursor:pointer; }
  .topbar h1 { font-size:18px; font-weight:500; margin:0; flex:1; text-align:center; }
  .qbtn { font-size:15px; color:var(--lx-t1); cursor:pointer; min-width:40px;
          text-align:right; }
  .refresh { width:30px; height:30px; border-radius:50%; display:flex;
             align-items:center; justify-content:center; cursor:pointer; }
  .refresh img { width:17px; height:17px; opacity:.6; transform:rotate(-90deg); }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }

  /* 陪伴语 */
  .hello { font-size:21px; font-weight:500; padding:8px 20px 16px; line-height:1.35; }
  .hello b { font-family:"LxNum"; font-weight:600; }

  /* ── 主卡（环形）── */
  .card { margin:0 16px; background:var(--lx-card); border-radius:20px;
          padding:26px 20px 22px; text-align:center; }
  .ring2 { position:relative; display:inline-block; }
  .ring2 svg { display:block; }
  .ring2 .center { position:absolute; inset:0; display:flex; flex-direction:column;
                   align-items:center; justify-content:center; }
  .ring2 .center .n { font-family:"LxNum"; font-size:44px; font-weight:500;
                      letter-spacing:-1px; line-height:1; }
  .ring2 .center .l { font-size:12.5px; color:var(--lx-t3); margin-top:8px; }
  .legend { display:flex; justify-content:center; gap:44px; margin-top:20px; }
  .lg { text-align:center; }
  .lg .v { font-size:21px; font-weight:500; display:flex; align-items:center;
           justify-content:center; gap:4px; }
  .lg .v img { width:17px; height:17px; }
  .lg .l { font-size:12.5px; color:var(--lx-t3); margin-top:5px; }

  /* ── 智驾卡 ── */
  .adcard { margin:16px 16px 0; background:var(--lx-card); border-radius:20px;
            padding:24px 20px 26px; }
  .adcard .t { font-size:17px; text-align:center; line-height:1.5; }
  .adcard .t b { font-family:"LxNum"; font-weight:600; }
  .rings { display:flex; justify-content:center; gap:52px; margin-top:24px; }
  .ring1 { position:relative; }
  .ring1 .center { position:absolute; inset:0; display:flex; flex-direction:column;
                   align-items:center; justify-content:center; }
  .ring1 .center .n { font-family:"LxNum"; font-size:25px; font-weight:500; }
  .ring1 .center .l { font-size:11.5px; color:var(--lx-t3); margin-top:4px; }

  /* 免责 */
  .note { padding:18px 20px 6px; font-size:12.5px; color:var(--lx-t3);
          line-height:1.65; }

  /* ── 年份折叠 ── */
  .years { padding:6px 20px 0; }
  .year { border-bottom:1px solid var(--lx-line); }
  .year:last-child { border-bottom:none; }
  .yhead { display:flex; align-items:center; padding:17px 0; cursor:pointer; }
  .yhead .yn { font-size:17px; font-weight:500; }
  .yhead .ar { margin-left:auto; font-size:15px; color:var(--lx-t2);
               transition:transform .2s; }
  .year.open .yhead .ar { transform:rotate(180deg); }
  .ymonths { display:none; padding-bottom:8px; }
  .year.open .ymonths { display:block; }
  /* ★ 2026-10-12：改为 block —— .m 现在包着 .mh（行）+ .md（内联明细） */
  .m { display:block; padding:11px 0; }
  .yhead .ys { font-size:12px; color:var(--lx-t3); margin-left:10px; }
  .m .mh { display:flex; align-items:center; width:100%; cursor:pointer; }
  .m .mbar { flex:1; height:6px; border-radius:3px; background:var(--lx-line);
             overflow:hidden; margin:0 10px; min-width:30px; }
  .m .mbar > i { display:block; height:100%; border-radius:3px; background:#2C6BFF;
                 transition:width .3s ease; }
  .m .ar { margin-left:6px; color:var(--lx-t3); font-size:13px; transition:transform .2s; }
  .m.sel .ar { transform:rotate(90deg); }
  .m.top .mv { font-weight:600; color:var(--lx-t1); }
  .m.top .mbar > i { background:#1E5AE0; }
  /* ★ 内联明细（参考充电页）：点月份即在该月下方展开，不再跑到底部 */
  .m .md { display:none; padding:2px 0 8px; }
  .m.sel .md { display:block; }
  .m .mn { font-size:14px; color:var(--lx-t2); }
  .m .mt { font-size:11.5px; color:var(--lx-t3); margin-left:10px; }
  .m .mv { margin-left:auto; font-family:"LxNum"; font-size:14px; font-weight:500; }
  .m .mu { font-size:11px; color:var(--lx-t3); margin-left:3px; }
  .m.sel .mn { color:var(--lx-blue); font-weight:500; }
  .daily { padding:4px 0 8px; }
  .drow { display:flex; align-items:center; gap:8px; padding:7px 0; font-size:12.5px; }
  .drow .dd { color:var(--lx-t2); min-width:44px; }
  .drow .dn { font-family:"LxNum"; font-weight:500; min-width:64px; text-align:right; }
  /* ★ 2026-10-11 迷你条：一眼看出"哪天跑得多"（原来只有数字，要逐行对比） */
  .dbar { flex:1; height:6px; border-radius:3px; background:var(--lx-line,rgba(0,0,0,.06)); overflow:hidden; }
  .dbar > i { display:block; height:100%; border-radius:3px; background:#2C6BFF; }
  .drow.top .dd, .drow.top .dn { color:var(--lx-t1); font-weight:600; }
  .drow.top .dbar > i { background:#34C759; }
  .sortbtn { font-size:12px; color:var(--lx-t3); cursor:pointer; padding:2px 6px;
             border:1px solid var(--lx-line,rgba(0,0,0,.08)); border-radius:7px; }
  .sortbtn.on { color:#2C6BFF; border-color:#2C6BFF; }
  .tabs { display:flex; gap:8px; margin:6px 0 10px; }
  .tab { padding:6px 13px; border-radius:9px; font-size:12px; cursor:pointer;
         background:var(--lx-bg); color:var(--lx-t3); }
  .tab.on { background:rgba(10,88,246,.1); color:var(--lx-blue); font-weight:500; }
  .empty { text-align:center; color:var(--lx-t3); font-size:13px; padding:20px 0; }
  .state { text-align:center; padding:24px 16px; }
  .state .t { font-size:13.5px; color:var(--lx-t2); }
  .state .d { font-size:11.5px; color:var(--lx-t3); margin-top:7px; line-height:1.55; }
  .state .retry { display:inline-block; margin-top:13px; font-size:13px;
                  color:var(--lx-blue); padding:7px 17px; border-radius:10px;
                  background:rgba(10,88,246,.07); cursor:pointer; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  /* 无障碍：键盘焦点可见 */
  [role="button"]:focus-visible, .refresh:focus-visible,
  .yhead:focus-visible, .m:focus-visible, .tab:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangEnergyPage extends HTMLElement {
  setConfig(c) {
    this._config = c || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base; this._openYears = new Set(); this._selMonth = null;
    this._tab = "mileage"; this._built = false;
  }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 20; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id);
             return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    root.innerHTML = `
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="返回">
        <h1>${I18N.title}</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
      </div>

      <div class="hello" id="hello">—</div>

      <!-- 主卡：双段环形 -->
      <div class="card">
        <div class="ring2">
          <svg id="ring2" width="272" height="272" viewBox="0 0 272 272"></svg>
          <div class="center">
            <div class="n" id="c-km">—</div>
            <div class="l">${I18N.partnerKm}</div>
          </div>
        </div>
        <div class="legend">
          <div class="lg">
            <div class="v"><span id="lg-elec-p">—</span><img src="${__iconBase}/ic_home_electricity.webp" onerror="__lxIconFallback(this)" alt=""></div>
            <div class="l">${I18N.elec}</div>
          </div>
          <div class="lg">
            <div class="v"><img src="${__iconBase}/ic_home_oil.webp" onerror="__lxIconFallback(this)" alt=""><span id="lg-fuel-p">—</span></div>
            <div class="l">${I18N.fuel}</div>
          </div>
        </div>
      </div>

      <!-- 智驾卡：两个环形 -->
      <div class="adcard">
        <div class="t" id="ad-text">—</div>
        <div class="rings">
          <div class="ring1">
            <svg id="ring-day" width="118" height="118" viewBox="0 0 118 118"></svg>
            <div class="center"><div class="n" id="c-day">—</div>
              <div class="l">${I18N.dayRatio}</div></div>
          </div>
          <div class="ring1">
            <svg id="ring-km" width="118" height="118" viewBox="0 0 118 118"></svg>
            <div class="center"><div class="n" id="c-km-pct">—</div>
              <div class="l">${I18N.kmRatio}</div></div>
          </div>
        </div>
      </div>

      <div class="note">${I18N.disclaimer}</div>

      <!-- 明细已改为内联到各月份下方（参考充电页），不再有底部 #daily -->
      <div class="years" id="years"><div class="empty">${I18N.loading}</div></div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    const rf = this.querySelector("#refresh");
    const doRf = () => this._refreshAll();
    this._a11y(rf, "刷新", doRf);
    rf.addEventListener("click", doRf);

    this._built = true;
  }

  /** 画环形（支持双段：绿+蓝）*/
  _drawRing(svg, segments, opts) {
    if (!svg) return;
    const o = opts || {};
    const size = o.size || 118, sw = o.stroke || 12;
    const r = (size - sw) / 2, cx = size / 2, cy = size / 2;
    const C = 2 * Math.PI * r;
    const NS = "http://www.w3.org/2000/svg";
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    // 背景环
    const bg = document.createElementNS(NS, "circle");
    bg.setAttribute("cx", cx); bg.setAttribute("cy", cy); bg.setAttribute("r", r);
    bg.setAttribute("fill", "none");
    bg.setAttribute("stroke", o.trackColor || "rgba(0,0,0,.05)");
    bg.setAttribute("stroke-width", sw);
    svg.appendChild(bg);

    // 从顶部开始，顺时针
    let acc = 0;
    segments.forEach((seg) => {
      const frac = Math.max(0, Math.min(1, seg.value || 0));
      if (frac <= 0) { acc += frac; return; }
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", cx); c.setAttribute("cy", cy); c.setAttribute("r", r);
      c.setAttribute("fill", "none");
      c.setAttribute("stroke", seg.color);
      c.setAttribute("stroke-width", sw);
      c.setAttribute("stroke-linecap", "round");
      c.setAttribute("stroke-dasharray", `${frac * C} ${C}`);
      c.setAttribute("stroke-dashoffset", `${-acc * C}`);
      c.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
      svg.appendChild(c);
      acc += frac;
    });
  }

  _refreshAll() {
    const rf = this.querySelector("#refresh");
    if (rf) rf.classList.add("spin");
    this._years = null; this._monthDaily = null; this._fetchingYears = false;
    this._error = null;
    Promise.resolve(this._fetchYears()).finally(() => {
      if (rf) rf.classList.remove("spin");
      this._update();
    });
  }

  async _fetchYears() {
    if (!this._hass || this._years || this._fetchingYears) return;
    this._fetchingYears = true;
    try {
      const r = await this._hass.callService("lixiang_auto", "get_travel", {}, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const yl = first && first.data && first.data.yearEnergyList;
      if (Array.isArray(yl) && yl.length) {
        this._years = yl;
        this._openYears.add(String(yl[0].year));
        this._renderYears();
        const em = (yl[0].monthlyEnergyList || [])[0];
        if (em && em.month != null) this._fetchMonthDaily(yl[0].year, em.month, true);
      }
    } catch (e) { this._error = (e && e.message) || "网络请求失败"; }
    finally { this._fetchingYears = false; }
  }

  async _fetchMonthDaily(year, month, silent) {
    if (!this._hass) return;
    if (!silent) { this._monthDaily = null; this._renderDaily(); }
    try {
      const r = await this._hass.callService("lixiang_auto", "get_travel",
        { year, month }, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const dl = first && first.data && first.data.dailyList;
      if (Array.isArray(dl)) {
        this._monthDaily = dl.map((x) => ({
          dayOfMonth: Number(x.dayOfMonth) || 0,
          mileage: Number(x.mileage) || 0,
          elecEnergy: Number(x.elecEnergy) || 0,
          fuelConsumption: Number(x.fuelConsumption) || 0,
        })).sort((a, b) => a.dayOfMonth - b.dayOfMonth);
      }
    } catch (e) {}
    this._renderDaily();
  }

  _renderYears() {
    const box = this.querySelector("#years");
    if (!box) return;
    const yl = this._years;
    if (!yl || !yl.length) {
      box.innerHTML = this._error
        ? `<div class="state"><div class="t">${I18N.loadFail}</div>
           <div class="d">${this._error}</div>
           <div class="retry" id="retry1">${I18N.retry}</div></div>`
        : `<div class="state"><div class="t">${this._fetchingYears ? I18N.loading : I18N.noData}</div>
           <div class="d">${this._fetchingYears ? "正在获取里程数据…" : "车辆尚未产生行程数据"}</div></div>`;
      const r1 = box.querySelector("#retry1");
      if (r1) { this._a11y(r1, I18N.retry, () => this._refreshAll());
                r1.addEventListener("click", () => this._refreshAll()); }
      return;
    }
    box.innerHTML = yl.map((y) => {
      const ms = (y.monthlyEnergyList || []).filter((m) => Number(m.travelMil) > 0);
      const open = this._openYears.has(String(y.year));
      // 年份汇总（对齐充电页：N 个月 · 总计）
      const tot = ms.reduce((a, m) => a + (Number(m.travelMil) || 0), 0);
      // 条形按【所在年】归一（跨年不可比）
      const mx = Math.max(1, ...ms.map((m) => Number(m.travelMil) || 0));
      const rows = ms.map((m) => {
        const sel = this._selMonth && this._selMonth.year === y.year
                    && this._selMonth.month === m.month;
        const v = Number(m.travelMil) || 0;
        const w = v > 0 ? Math.max(3, Math.round((v / mx) * 100)) : 0;
        const isTop = v > 0 && v >= mx;
        // ★ 每行自带内联明细容器（参考充电页：点开即在该月下方，不再跑到底部）
        return `<div class="m${sel ? " sel" : ""}${isTop ? " top" : ""}"
                     data-y="${y.year}" data-m="${m.month}">
            <div class="mh" role="button" tabindex="0" aria-expanded="${sel ? "true" : "false"}">
              <span class="mn">${m.month} 月</span>
              <span class="mbar" aria-hidden="true"><i style="width:${w}%"></i></span>
              <span class="mv">${Number(m.travelMil).toFixed(1)}</span>
              <span class="mu">km</span>
              <span class="ar">›</span>
            </div>
            <div class="md" id="md-${y.year}-${m.month}"></div>
          </div>`;
      }).join("");
      return `<div class="year${open ? " open" : ""}" data-year="${y.year}">
          <div class="yhead" role="button" tabindex="0" aria-expanded="${open ? "true" : "false"}">
            <span class="yn">${y.year}年</span>
            <span class="ys">${ms.length} 个月 · ${tot.toFixed(1)} km</span>
            <span class="ar">⌃</span></div>
          <div class="ymonths">${rows || '<div class="empty">无记录</div>'}</div>
        </div>`;
    }).join("");

    box.querySelectorAll(".yhead").forEach((h) => {
      const act = () => {
        const y = h.parentElement.dataset.year;
        if (this._openYears.has(y)) this._openYears.delete(y); else this._openYears.add(y);
        this._renderYears();
      };
      this._a11y(h, `${h.parentElement.dataset.year} 年 展开收起`, act);
      h.addEventListener("click", act);
    });
    box.querySelectorAll(".m").forEach((m) => {
      const h = m.querySelector(".mh");
      const act = async () => {
        const yy = Number(m.dataset.y), mm = Number(m.dataset.m);
        const isOpen = this._selMonth && this._selMonth.year === yy
                       && this._selMonth.month === mm;
        if (isOpen) {
          // 再点一次收起
          this._selMonth = null; this._monthDaily = null;
          m.classList.remove("sel");
          if (h) h.setAttribute("aria-expanded", "false");
          const d = m.querySelector(".md"); if (d) d.innerHTML = "";
          return;
        }
        this._selMonth = { year: yy, month: mm };
        // 收起其它已展开的月份
        box.querySelectorAll(".m.sel").forEach((el) => {
          el.classList.remove("sel");
          const hh = el.querySelector(".mh");
          if (hh) hh.setAttribute("aria-expanded", "false");
          const dd = el.querySelector(".md"); if (dd) dd.innerHTML = "";
        });
        m.classList.add("sel");
        if (h) h.setAttribute("aria-expanded", "true");
        const target = m.querySelector(".md");
        if (target) target.innerHTML = `<div class="empty">${I18N.loading}</div>`;
        this._renderDaily(target);          // 先渲染 tabs（带 loading）
        await this._fetchMonthDaily(yy, mm, false);
      };
      this._a11y(h || m, `${m.dataset.y} 年 ${m.dataset.m} 月 明细`, act);
      (h || m).addEventListener("click", act);
    });
  }

  /** 渲染某月「每日」明细。
   *  ★ 2026-10-12：改为**内联**渲染到传入的容器（`box`）—— 参考充电页。
   *    此前渲染到页面底部的 `#daily`，用户点月份后要往下滚才看得到。
   *    `box` 缺省时按「当前选中月份」自动定位容器。
   */
  _renderDaily(box) {
    // ★ 未显式传容器时，自动定位"当前选中月份"的内联容器 ——
    //   这样排序/tabs/重新拉取等旧调用点无需改动即可正确重绘。
    if (!box && this._selMonth) {
      box = this.querySelector(`#md-${this._selMonth.year}-${this._selMonth.month}`);
    }
    if (!box) return;
    if (!this._selMonth) { box.innerHTML = ""; return; }
    const rows = this._monthDaily || [];
    const head = `<div class="tabs">
        <div class="tab${this._tab === "mileage" ? " on" : ""}" data-tab="mileage">每日里程</div>
        <div class="tab${this._tab === "elec" ? " on" : ""}" data-tab="elec">每日耗电</div>
        <div class="tab${this._tab === "fuel" ? " on" : ""}" data-tab="fuel">每日耗油</div>
      </div>
      <div class="sortbtn${this._sort ? " on" : ""}" role="button" tabindex="0"
           aria-label="按数值排序">${this._sort ? "按数值 ↓" : "按日期"}</div>`;
    if (!rows.length) { box.innerHTML = head + `<div class="empty">${I18N.noData}</div>`; this._bindTabs(box); return; }
    const pick = { mileage:"mileage", elec:"elecEnergy", fuel:"fuelConsumption" }[this._tab];
    const unit = this._tab === "mileage" ? "km" : (this._tab === "elec" ? "kWh" : "L");
    // ★ 迷你条以【当月最大值】为基准；排序可选（默认按日期）
    const max = Math.max(...rows.map(r => Number(r[pick]) || 0), 0);
    const list = this._sort
      ? rows.slice().sort((a, b) => (Number(b[pick]) || 0) - (Number(a[pick]) || 0))
      : rows;
    box.innerHTML = head + `<div style="font-size:12px;color:var(--lx-t3);padding:4px 0 6px">
        ${this._selMonth.year}年${this._selMonth.month}月</div>` +
      list.map((r) => {
        const v = Number(r[pick]) || 0;
        const pct = max > 0 ? Math.max(v > 0 ? 3 : 0, Math.round(v / max * 100)) : 0;
        const top = max > 0 && v === max;
        return `<div class="drow${top ? " top" : ""}">
          <span class="dd">${r.dayOfMonth} 日</span>
          <span class="dbar"><i style="width:${pct}%"></i></span>
          <span class="dn">${v ? v + " " + unit : "—"}</span></div>`;
      }).join("");
    this._bindTabs(box);
    this._bindSort(box);
  }

  /** 排序切换（按日期 / 按数值）——★ 2026-10-11 */
  _bindSort(scope) {
    const b = (scope || this).querySelector(".sortbtn");
    if (!b) return;
    const act = () => { this._sort = !this._sort; this._renderDaily(scope); };
    this._a11y(b, b.textContent, act);
    b.addEventListener("click", act);
  }

  _bindTabs(scope) {
    (scope || this).querySelectorAll(".tab").forEach((t) => {
      const act = () => { this._tab = t.dataset.tab; this._renderDaily(scope); };
      this._a11y(t, t.textContent, act);
      t.addEventListener("click", act);
    });
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);

    // 陪伴语：「理想L6已经陪伴您800天」
    const mdl = (window.LixiangAutoBind && this._hass)
      ? (() => {
          const c = this._config || {};
          for (const d of Object.values(this._hass.devices || {})) {
            if ((d.manufacturer || "").includes("理想") ||
                JSON.stringify(d.identifiers || []).includes("lixiang")) {
              const m = String(d.model || d.name || "").match(/(MEGA|L[6-9]|i[6-9])/i);
              return m ? `理想${m[1].toUpperCase()}` : (d.name || "理想汽车");
            }
          }
          return "理想汽车";
        })() : "理想汽车";
    const days = this._num(this._eid("partner_days"));
    q("#hello").innerHTML = days == null
      ? `${mdl}${I18N.companion} — ${I18N.days}`
      : `${mdl}${I18N.companion}<b>${Math.round(days)}</b>${I18N.days}`;

    // 主环：陪伴里程 + 电/油占比
    const km = this._num(this._eid("partner_km"));
    const elecKm = this._num(this._eid("elec_km"));
    const fuelL = this._num(this._eid("fuel_l"));
    q("#c-km").textContent = km == null ? "—" : Math.round(km).toLocaleString();

    // 占比：耗电行驶 vs 耗油（App 用里程/油耗的构成比）
    let elecFrac = 0.87, fuelFrac = 0.13;
    if (elecKm != null && km != null && km > 0) {
      elecFrac = Math.min(1, elecKm / km);
      fuelFrac = Math.max(0, 1 - elecFrac);
    }
    this._drawRing(q("#ring2"), [
      { value: elecFrac, color: "#34C759" },
      { value: fuelFrac, color: "#2C6BFF" },
    ], { size: 272, stroke: 20, trackColor: "rgba(0,0,0,.04)" });
    q("#lg-elec-p").textContent = Math.round(elecFrac * 100) + "%";
    q("#lg-fuel-p").textContent = Math.round(fuelFrac * 100) + "%";

    // 智驾卡
    const adDays = this._num(this._eid("ad_days"));
    const adKm = this._num(this._eid("ad_km"));
    const totalKm = this._num(this._eid("total_km"));
    q("#ad-text").innerHTML = (adDays != null || adKm != null)
      ? `${I18N.adTitle} <b>${adDays == null ? "—" : Math.round(adDays)}</b> 天${I18N.adDrive} <b>${adKm == null ? "—" : Math.round(adKm).toLocaleString()}</b> km`
      : I18N.loading;

    const dayPct = (adDays != null && days != null && days > 0) ? Math.min(1, adDays / days) : 0;
    const kmPct = (adKm != null && totalKm != null && totalKm > 0) ? Math.min(1, adKm / totalKm) : 0;
    this._drawRing(q("#ring-day"), [{ value: dayPct, color: "#2C6BFF" }],
      { size: 118, stroke: 11, trackColor: "rgba(44,107,255,.16)" });
    this._drawRing(q("#ring-km"), [{ value: kmPct, color: "#2C6BFF" }],
      { size: 118, stroke: 11, trackColor: "rgba(44,107,255,.16)" });
    q("#c-day").textContent = Math.round(dayPct * 100) + "%";
    q("#c-km-pct").textContent = Math.round(kmPct * 100) + "%";

    this._fetchYears();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangEnergyPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "里程能耗（二级页）",
  description: "环形图：陪伴里程 + 电/油占比 + 智驾占比 + 年份折叠 + 每日明细",
  preview: true,
});
})();

/* ===================== lixiang-health-page.js ===================== */
(function () {

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


/**
 * lixiang-health-page —— 车辆健康（二级页，对齐 App 真实版）
 *
 * App 实测结构（截图 1260×3112 @3x）：
 *   ① 胎压图：车辆俯视轮廓 + 4 轮（bar + °C），左右分布
 *   ② 「车辆保养」标题 + 5 项保养计划（名称 + 到期条件）
 *
 * 单位：bar（1 bar = 100 kPa）—— App 用 bar
 *
 * 数据源：
 *   ✅ 胎压 4 轮（sensor，kPa → 前端换算 bar）
 *   ✅ 胎温 4 轮
 *   ✅ 火花塞保养（剩余 km）
 *   ⚠️ 空调滤芯/刹车油/冷却液/机油 保养 —— 信号已定义，
 *      但集成对空值未创建实体 → 页面按"无数据"处理
 */

const CARD_TAG = "lixiang-health-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-health-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-tire:#D8D8DC; }
  @media (prefers-color-scheme: dark) {
    lixiang-health-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-tire:#3A3A3E; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:24px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; position:relative; }
  .back { width:34px; height:34px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center; cursor:pointer; }
  .back img { width:18px; height:18px; opacity:.7; }
  .topbar h1 { position:absolute; left:0; right:0; text-align:center;
               font-size:18px; font-weight:500; margin:0; pointer-events:none; }

  /* ── 胎压图 ── */
  .tires { padding:20px 30px 8px; }
  .tv { display:grid; grid-template-columns:1fr 96px 1fr; align-items:center;
        gap:6px; }
  .tcell { text-align:center; }
  .tcell .v { font-family:"LxNum"; font-size:27px; font-weight:500; line-height:1; }
  .tcell .v small { font-size:14px; color:var(--lx-t3); margin-left:4px; font-weight:400; }
  .tcell .t { font-size:14px; color:var(--lx-t3); margin-top:7px; }
  .tcell.warn .v { color:var(--lx-orange); }
  .tcell.bad .v { color:var(--lx-red); }
  /* 车身轮廓 */
  .body { position:relative; height:210px; }
  .body .shell { position:absolute; inset:8px 26px; border:3px solid var(--lx-tire);
                 border-radius:44px 44px 34px 34px; }
  .body .cabin { position:absolute; left:19px; right:19px; top:56px; bottom:34px;
                 background:var(--lx-card); border-radius:20px; }
  .body .wh { position:absolute; width:11px; height:34px; background:var(--lx-tire);
              border-radius:4px; }
  .body .wh.l1 { left:16px; top:34px; }
  .body .wh.r1 { right:16px; top:34px; }
  .body .wh.l2 { left:16px; bottom:34px; }
  .body .wh.r2 { right:16px; bottom:34px; }
  /* 分隔线 */
  .hline { height:1px; background:var(--lx-line); }
  .tvrow { display:grid; grid-template-columns:1fr 96px 1fr; align-items:center; }

  /* ── 保养 ── */
  .sect { padding:34px 16px 0; }
  .sect h2 { font-size:17px; font-weight:500; margin:0 0 14px 4px; }
  .maint { background:var(--lx-card); border-radius:18px; overflow:hidden; }
  .mrow { padding:16px 18px; border-bottom:1px solid var(--lx-line); }
  .mrow:last-child { border-bottom:none; }
  .mrow .n { font-size:16px; }
  .mrow .d { font-size:14px; color:var(--lx-t3); margin-top:7px; }
  .mrow .d.near { color:var(--lx-orange); }
  .mrow .d.over { color:var(--lx-red); }
  .empty { padding:20px 18px; font-size:14px; color:var(--lx-t3); text-align:center; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangHealthPage extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._built = false; }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 18; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    // 保养类实体值是 "剩余 N km" 文本，提取数字
    const m = String(s.state).match(/-?\d+(\.\d+)?/);
    if (!m) return null;
    const n = parseFloat(m[0]); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id);
             return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }
  _on(id) { const v = this._txt(id);
            return v != null && ["on","true","1"].includes(String(v).toLowerCase()); }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    const cell = (id, pos) => `<div class="tcell" id="${id}">
        <div class="v"><span class="p">—</span><small>bar</small></div>
        <div class="t"><span class="tt">—</span>°C</div></div>`;
    root.innerHTML = `
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <h1>车辆健康</h1>
      </div>

      <div class="tires">
        <div class="tv">
          ${cell("c-lf")}
          <div class="body">
            <div class="shell"></div><div class="cabin"></div>
            <div class="wh l1"></div><div class="wh r1"></div>
            <div class="wh l2"></div><div class="wh r2"></div>
          </div>
          ${cell("c-rf")}
        </div>
        <div class="tv" style="margin-top:8px">
          ${cell("c-lr")}
          <div></div>
          ${cell("c-rr")}
        </div>
      </div>

      <div class="sect">
        <h2>车辆保养</h2>
        <div class="maint" id="maint"></div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    this._built = true;
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);

    // 胎压（kPa → bar）+ 胎温
    const setTire = (cellId, pressField, tempField, warnField) => {
      const el = q("#" + cellId); if (!el) return;
      const kpa = this._num(this._eid(pressField));
      const bar = kpa == null ? null : kpa / 100;
      const t = this._num(this._eid(tempField));
      el.querySelector(".p").textContent = bar == null ? "—" : bar.toFixed(1);
      el.querySelector(".tt").textContent = t == null ? "—" : Math.round(t);
      const warn = warnField ? this._on(this._eid(warnField)) : false;
      const bad = bar != null && (bar < 2.0 || bar > 2.9);
      el.className = "tcell" + (bad ? " bad" : (warn ? " warn" : ""));
    };
    setTire("c-lf", "tire_lf", "temp_lf", "warn_lf");
    setTire("c-rf", "tire_rf", "temp_rf", "warn_rf");
    setTire("c-lr", "tire_lr", "temp_lr", "warn_lr");
    setTire("c-rr", "tire_rr", "temp_rr", "warn_rr");

    // 保养列表（App 的 5 项 + 火花塞）
    // 顺序与名称对齐 App 截图「车辆保养」列表
    const ITEMS = [
      ["增程器小保养", "maint_engine_oil"],      // 机油（增程器小保养）
      ["火花塞保养",   "maint_sparkplug"],
      ["空调滤芯保养", "maint_acfilter"],
      ["油液保养",     "maint_brake_oil"],
      ["冷却液保养",   "maint_coolfuild"],
      ["增程器大保养", "maint_engine_level2"],
    ];
    const rows = [];
    ITEMS.forEach(([label, field]) => {
      const eid = this._eid(field);
      const raw = eid ? this._txt(eid) : null;
      if (raw == null) return;
      // 值形态：「剩余 N km」/「YYYY年M月或Nkm后过期」
      let desc = String(raw);
      let cls = "";
      const km = desc.match(/剩余\s*(\d+)\s*km/i);
      if (km) {
        const n = Number(km[1]);
        desc = `剩余 ${n.toLocaleString()} km`;
        if (n < 3000) cls = "near";
      }
      rows.push({ label, desc, cls });
    });

    const box = q("#maint");
    if (!rows.length) {
      box.innerHTML = `<div class="empty">保养数据暂不可用<br>
        <span style="font-size:12px">（集成已定义保养信号，但车辆未上报或该车型不支持）</span></div>`;
    } else {
      box.innerHTML = rows.map(r =>
        `<div class="mrow"><div class="n">${r.label}</div>
         <div class="d ${r.cls}">${r.desc}</div></div>`).join("");
    }
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangHealthPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "车辆健康（二级页）",
  description: "胎压图（bar + 胎温）+ 车辆保养计划",
  preview: true,
});
})();

/* ===================== lixiang-setting-page.js ===================== */
(function () {

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


/**
 * lixiang-setting-page —— 车辆设置（二级页）
 *
 * 数据源（真实可控制实体）：
 *   空调：select.kong_diao_kong_zhi_lei_xing / number.kong_diao_she_ding_wen_du
 *         switch.kong_diao_kuai_su_zhi_re / _zhi_leng / kong_diao_chu_shuang
 *         switch.fang_xiang_pan_jia_re / switch.dian_chi_bao_wen
 *   充电：select.chong_dian_mo_shi / number.chong_dian_shang_xian
 *         switch.yu_yue_chong_dian
 *   安全：switch.shao_bing_mo_shi
 *   操作：button.xun_che / yuan_cheng_qi_dong / shan_deng / ming_di / yuan_cheng_pai_zhao
 */

const CARD_TAG = "lixiang-setting-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖
const __fontFallback = BUILTIN_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-setting-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-setting-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { container-type:inline-size; position:relative; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  .topbar { display:flex; align-items:center; height:48px; padding:0 16px; }
  .back { width:24px; height:24px; opacity:.75; cursor:pointer; }
  .topbar h1 { font-size:17px; font-weight:500; margin:0; flex:1; text-align:center; }
  .topbar .r { min-width:56px; }

  .sec { padding:16px 20px 0; }
  .sec > h2 { font-size:13px; color:var(--lx-t3); font-weight:400; margin:0 0 8px 4px; }
  .box { background:var(--lx-card); border-radius:18px; overflow:hidden; }
  .row { display:flex; align-items:center; gap:12px; padding:14px 16px;
         min-height:54px; border-bottom:1px solid var(--lx-line); }
  .row:last-child { border-bottom:none; }
  .row.click { cursor:pointer; transition:background .15s; }
  .row.click:hover { background:rgba(0,0,0,.03); }
  .row img.ic { width:22px; height:22px; flex:0 0 auto; }
  .row .tx { flex:1; min-width:0; }
  .row .nm { font-size:15px; line-height:1.2; }
  .row .sd { font-size:12px; color:var(--lx-t3); margin-top:3px; }
  .row .val { font-size:14px; color:var(--lx-t2); font-family:"LxNum","Licium"; }
  .row .ar { color:var(--lx-t3); font-size:16px; }
  .row .sw { width:46px; height:28px; border-radius:14px; background:#D8D8DC;
             position:relative; transition:background .2s; flex:0 0 auto; cursor:pointer; }
  .row .sw::after { content:""; position:absolute; top:2px; left:2px; width:24px; height:24px;
             border-radius:50%; background:#fff; transition:transform .2s;
             box-shadow:0 1px 3px rgba(0,0,0,.2); }
  .row .sw.on { background:var(--lx-green); }
  .row .sw.on::after { transform:translateX(18px); }
  .row .sw.dim { opacity:.4; cursor:not-allowed; }
  /* 数值调节 */
  .stepper { display:flex; align-items:center; gap:10px; }
  .stepper button { width:30px; height:30px; border-radius:50%; border:1.5px solid var(--lx-line);
             background:var(--lx-bg); color:var(--lx-t1); font-size:17px; line-height:1;
             cursor:pointer; display:flex; align-items:center; justify-content:center; }
  .stepper button:active { transform:scale(.92); }
  .stepper .n { font-family:"LxNum"; font-size:16px; font-weight:600; min-width:52px; text-align:center; }
  /* 滑块 */
  .sliderwrap { padding:14px 16px 18px; }
  .sliderwrap .lbl { display:flex; justify-content:space-between; font-size:13px;
                     color:var(--lx-t2); margin-bottom:10px; }
  .sliderwrap .lbl b { font-family:"LxNum"; font-weight:600; color:var(--lx-t1); }
  input[type=range] { width:100%; -webkit-appearance:none; height:4px; border-radius:2px;
             background:var(--lx-line); outline:none; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:22px; height:22px;
             border-radius:50%; background:#fff; box-shadow:0 1px 4px rgba(0,0,0,.2);
             border:1px solid var(--lx-line); cursor:pointer; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }

  /* ── 键盘可达：统一焦点样式（无障碍）── */
  [role="button"]:focus-visible, .card:focus-visible, .entry:focus-visible,
  .row.click:focus-visible, .m:focus-visible, .yhead:focus-visible,
  .year .yhead:focus-visible, button:focus-visible, input:focus-visible {
    outline: 2px solid var(--lx-blue, #0A58F6);
    outline-offset: 2px;
    border-radius: 8px;
  }
  /* 尊重「减少动态效果」偏好 */
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
  }

  .refresh { width:30px; height:30px; border-radius:50%; display:flex;
             align-items:center; justify-content:center; cursor:pointer;
             transition:background .15s, transform .3s; }
  .refresh:hover { background:var(--lx-card); }
  .refresh:active { transform:scale(.9); }
  .refresh img { width:17px; height:17px; opacity:.6; }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }

  /* ── 下拉刷新 ── */
  .ptr { position:absolute; left:0; right:0; top:0; height:0; overflow:hidden;
         display:flex; align-items:center; justify-content:center;
         transition:height .2s ease; pointer-events:none; }
  .ptr .sp { width:20px; height:20px; border-radius:50%;
             border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
             animation:lspin .8s linear infinite; }
  .ptr .tx { font-size:11.5px; color:var(--lx-t3); margin-left:8px; }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangSettingPage extends HTMLElement {

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config||{}).resolve() || {};
    } catch(e) {}
    if (out && Object.keys(out).length) this._bindCache = out;   // 空结果不缓存
    return out;
  }
  /** 组内取值：手填 > 自动发现；支持 {entity:...} 形式 */
  _grp(group, key) {
    const c=this._config||{}; const m=(c[group]||{})[key];
    if (typeof m==="string" && m.includes(".")) return m;
    if (m && typeof m==="object" && m.entity) return { ...m, entity: m.entity };
    const auto=(this._autoBind()||{})[key];
    if (!auto) return null;
    // numbers 需要 {entity, step, unit} 结构
    if (group === "numbers") {
      const defs={ac_temp:{step:0.5,unit:"°C"},charge_limit:{step:5,unit:"%"}};
      return { entity: auto, ...(defs[key] || { step: 1, unit: "" }) };
    }
    return auto;
  }
  /**
   * ★ 2026-10-11 数据驱动：页面结构由这张表决定（原来散落在大段 innerHTML 里）。
   * 每行 = [key, 类型, 名称, 图标, 副标题]
   *   类型：sw=开关 / sel=选择 / num=步进 / rng=滑块 / btn=动作
   * 好处：① 新增功能只改这张表；② 区块顺序一目了然；
   *       ③ 「这台车有没有」统一由 `_rowSupported` 判定（实体是否存在），
   *          不再在模板里写一堆 `S.includes(...) ? ... : ""`。
   */
  _sections() {
    return [
      { title: "空调与舒适", rows: [
        ["ac_temp",     "num", "设定温度",   "ic_home_ice_cool.webp"],
        ["ac_fast_hot", "sw",  "快速制热",   "ic_home_ice_cool.webp"],
        ["ac_fast_cold","sw",  "快速制冷",   "ic_home_ice_cool.webp"],
        ["ac_defrost",  "sw",  "前风挡除霜", ""],
        ["steer_heat",  "sw",  "方向盘加热", ""],
        ["batt_warm",   "sw",  "电池保温",   ""],
      ]},
      { title: "充电", rows: [
        ["charge_limit", "rng", "充电上限",   ""],
        ["charge_mode",  "sel", "充电模式",   "ic_home_electricity.webp"],
        ["appointment",  "sw",  "预约充电",   "ic_home_chrgporlid_off_lisa.png"],
      ]},
      { title: "安全与辅助", rows: [
        ["sentry", "sw", "哨兵模式", "ic_home_sentry.png", "离车后监控周围环境"],
      ]},
      { title: "远程操作", rows: [
        ["find",  "btn", "寻车",     "ic_summon_lisa.png"],
        ["start", "btn", "远程启动", "ic_home_control.webp"],
        ["flash", "btn", "闪灯",     "ic_home_lightning.png"],
        ["horn",  "btn", "鸣笛",     "ic_home_dialogue.png"],
        ["photo", "btn", "远程拍照", "ic_home_photo.png"],
      ]},
    ];
  }

  /**
   * 该行在这台车上是否可用（车型适配）。
   * 判据 = 实体存在（服务端已按车型能力门控）；buttons 组另有 btn_ 前缀约定。
   */
  _rowSupported(type, key) {
    if (type === "btn") {
      // buttons 组：配置里写 btn_start / autoBind 里是 start（两种都认）
      return !!(this._grp("buttons", key) || this._grp("buttons", "btn_" + key));
    }
    const group = ({ sw: "switches", sel: "selects", num: "numbers", rng: "numbers" })[type];
    const g = this._grp(group, key);
    if (!g) return false;
    // ★ _grp 的返回形态不统一：switches/selects 给**字符串** entity，
    //   numbers 给 {entity, step, unit}。两种都要认（写错会导致开关整组不显示）。
    const eid = (typeof g === "string") ? g : g.entity;
    return !!(eid && this._st(eid));
  }

  /** 按 SECTIONS 表生成四个区块（★ 替代原来手写的大段 innerHTML）。 */
  _renderSections() {
    const ic = n => (n ? `<img class="ic" src="${__iconBase}/${n}" alt="" onerror="this.style.visibility='hidden'">` : "");
    const row = (key, type, name, icon, sub) => {
      const head = `${ic(icon)}<div class="tx"><div class="nm">${name}</div>${sub ? `<div class="sd">${sub}</div>` : ""}</div>`;
      if (type === "sw")
        return `<div class="row click" data-sw="${key}">${head}<div class="sw" data-swtoggle="${key}"></div></div>`;
      if (type === "sel")
        return `<div class="row click" data-sel="${key}">${head}<div class="val" data-selval="${key}">—</div><div class="ar">›</div></div>`;
      if (type === "num")
        return `<div class="row">${head}<div class="stepper">
          <button data-dec="${key}" aria-label="降低">−</button>
          <span class="n" data-numval="${key}">—</span>
          <button data-inc="${key}" aria-label="升高">+</button></div></div>`;
      if (type === "rng")
        return `<div class="sliderwrap">
          <div class="lbl"><span>${name}</span><b><span data-numval="${key}">—</span>%</b></div>
          <input type="range" min="50" max="100" step="5" data-range="${key}"></div>`;
      return `<div class="row click" data-btn="${key}">${head}<div class="ar">›</div></div>`;
    };
    return this._sections().map(sec => {
      const rows = sec.rows.filter(r => this._rowSupported(r[1], r[0])).map(r => row(...r)).join("");
      if (!rows) return "";                       // ★ 整块都不支持 → 区块也不出现
      return `<div class="sec"><h2>${sec.title}</h2><div class="box">${rows}</div></div>`;
    }).join("");
  }

  _grpKeys(group) {
    const c=this._config||{}; const manual=Object.keys(c[group]||{});
    const auto=this._autoBind()||{};
    const groupKeys={switches:["sentry","ac_fast_hot","ac_fast_cold","ac_defrost","steer_heat","batt_warm","appointment"],
                     numbers:["ac_temp","charge_limit"],
                     selects:["charge_mode"],
                     buttons:["find","btn_start","btn_flash","btn_horn","btn_photo"]}[group]||[];
    const out=new Set(manual);
    groupKeys.forEach(k=>{ if(auto[k]) out.add(k); });
    return [...out];
  }

  /**
   * 让元素键盘可达（无障碍）。
   * 用法：this._a11y(el, "车锁", handler)
   */
  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        handler(e);
      }
    });
  }
  setConfig(config) { this._config = config || {}; this._busy={}; this._built = false; }
  set hass(hass) { this._hass = hass; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 18; }

  disconnectedCallback() {
    // 清理定时器与监听，避免卡片被移除后仍持有引用（内存泄漏）
    if (this._tt) { clearTimeout(this._tt); this._tt = null; }
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
    if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; }
    this._fetching = false;
    this._fetchingYears = false;
  }

  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id); return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }
  _on(id) { const v = this._txt(id); return v != null && ["on","true","1","open"].includes(String(v)); }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const c = this._config;
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = c.theme || "light";

    root.innerHTML = `
      <div class="ptr" id="ptr"><div class="sp"></div><div class="tx">下拉刷新</div></div>
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="返回">
        <h1>车辆设置</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="" style="transform:rotate(-90deg)">
        </div>
      </div>

      ${this._renderSections()}
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const _bk3 = this.querySelector("#back");
    this._a11y(_bk3, "返回", () => _bk3.click());
    _bk3.addEventListener("click", () => {
      const p = (c.nav||{}).back || "/lixiang/app";
      lxNavigate(this, p);
    });

    // 开关
    root.querySelectorAll("[data-swtoggle]").forEach(el => {
      const key = el.dataset.swtoggle;
      const nm = (el.closest(".row") || {}).querySelector
        ? el.closest(".row").querySelector(".nm").textContent : key;
      const act = () => this._toggle(key);
      this._a11y(el, `${nm} 开关`, act);
      el.addEventListener("click", e => { e.stopPropagation(); act(); });
      const row = el.closest("[data-sw]");
      if (row) { this._a11y(row, `${nm} 开关`, act); row.addEventListener("click", act); }
    });
    // 选择项：点击循环
    root.querySelectorAll("[data-sel]").forEach(el => {
      const key = el.dataset.sel;
      const nm = el.querySelector(".nm") ? el.querySelector(".nm").textContent : key;
      const act = () => this._cycle(key);
      this._a11y(el, `${nm} 切换`, act);
      el.addEventListener("click", act);
    });
    // 数值 +/-
    root.querySelectorAll("[data-inc]").forEach(el => {
      const act = () => this._step(el.dataset.inc, +1);
      this._a11y(el, "增加", act); el.addEventListener("click", act);
    });
    root.querySelectorAll("[data-dec]").forEach(el => {
      const act = () => this._step(el.dataset.dec, -1);
      this._a11y(el, "减少", act); el.addEventListener("click", act);
    });
    // 滑块
    root.querySelectorAll("[data-range]").forEach(el => {
      const key = el.dataset.range;
      // 拖动时实时预览数值（不提交）
      el.addEventListener("input", () => {
        const n = this.querySelector(`[data-numval="${key}"]`);
        if (n) n.textContent = el.value;
      });
      // 松手才提交
      el.addEventListener("change", () => this._setNum(key, Number(el.value), true));
    });
    // 按钮
    root.querySelectorAll("[data-btn]").forEach(el => {
      const key = el.dataset.btn;
      const nm = el.querySelector(".nm") ? el.querySelector(".nm").textContent : key;
      const act = () => this._press(key);
      this._a11y(el, nm, act); el.addEventListener("click", act);
    });

    
    // 刷新：重新拉取实体状态
    const _rf = this.querySelector("#refresh");
    const _doRf = () => {
      const el = this.querySelector("#refresh");
      if (el) el.classList.add("spin");
      this._built = this._built;   // 触发 _update
      this._update(); if (this._fetchStats) this._fetchStats();
      setTimeout(() => { if (el) el.classList.remove("spin"); }, 700);
    };
    if (_rf) { this._a11y(_rf, "刷新", _doRf); _rf.addEventListener("click", _doRf); }

    // ── 下拉刷新（触摸手势，对齐 App）──
    (() => {
      const ptr = this.querySelector("#ptr");
      const rootEl = this.querySelector(".root");
      if (!ptr || !rootEl) return;
      let startY = 0, pulling = false, dist = 0;
      const TH = 64;
      rootEl.addEventListener("touchstart", (e) => {
        if (window.scrollY > 4) return;
        startY = e.touches[0].clientY; pulling = true; dist = 0;
      }, { passive: true });
      rootEl.addEventListener("touchmove", (e) => {
        if (!pulling) return;
        dist = e.touches[0].clientY - startY;
        if (dist > 0 && window.scrollY <= 4) {
          const h = Math.min(dist * 0.55, 70);
          ptr.style.height = h + "px";
          ptr.querySelector(".tx").textContent = h >= TH * 0.5 ? "松开刷新" : "下拉刷新";
        }
      }, { passive: true });
      rootEl.addEventListener("touchend", () => {
        if (!pulling) return;
        pulling = false;
        const h = parseFloat(ptr.style.height) || 0;
        if (h >= TH * 0.5) {
          ptr.style.height = "44px";
          ptr.querySelector(".tx").textContent = "刷新中…";
          Promise.resolve(this.this._update()).finally(() => {
            setTimeout(() => { ptr.style.height = "0px"; }, 500);
          });
        } else {
          ptr.style.height = "0px";
        }
        dist = 0;
      }, { passive: true });
    })();

    this._built = true;
  }

  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt); this._tt = setTimeout(() => { t.className = "toast"; }, 2200);
  }

  async _toggle(key) {
    const eid = (this._config.switches || {})[key];
    if (!eid || this._busy[key]) return;
    const s = this._st(eid); if (!s) { this._toast("实体不存在", "err"); return; }
    this._busy[key] = true;
    const dom = eid.split(".")[0];
    const on = this._on(eid);
    try {
      await this._hass.callService(dom, on ? "turn_off" : "turn_on", { entity_id: eid });
      this._toast(on ? "已关闭" : "已开启", "ok");
    } catch (e) { this._toast("操作失败：" + ((e && e.message) || "未知"), "err"); }
    finally { delete this._busy[key]; }
  }

  async _cycle(key) {
    const eid = (this._config.selects || {})[key];
    if (!eid) return;
    const s = this._st(eid); if (!s) return;
    const opts = (s.attributes && s.attributes.options) || [];
    if (!opts.length) return;
    const cur = opts.indexOf(s.state);
    const next = opts[(cur + 1) % opts.length];
    try {
      await this._hass.callService("select", "select_option", { entity_id: eid, option: next });
      this._toast(`${key === "ac_mode" ? "空调类型" : "充电模式"} → ${next}`, "ok");
    } catch (e) { this._toast("设置失败", "err"); }
  }

  async _step(key, dir) {
    const cfg = (this._config.numbers || {})[key];
    if (!cfg) return;
    const eid = typeof cfg === "string" ? cfg : cfg.entity;
    const step = (typeof cfg === "object" && cfg.step) ? cfg.step : 0.5;
    const cur = this._num(eid);
    if (cur == null) return;
    this._setNum(key, +(cur + dir * step).toFixed(1));
  }

  async _setNum(key, value, silent) {
    const cfg = (this._config.numbers || {})[key];
    if (!cfg) return;
    const eid = typeof cfg === "string" ? cfg : cfg.entity;
    const s = this._st(eid); if (!s) return;
    const min = s.attributes && s.attributes.min != null ? s.attributes.min : undefined;
    const max = s.attributes && s.attributes.max != null ? s.attributes.max : undefined;
    let v = value;
    if (min != null && v < min) v = min;
    if (max != null && v > max) v = max;
    try {
      await this._hass.callService("number", "set_value", { entity_id: eid, value: v });
      if (!silent) this._toast(`已设为 ${v}`, "ok");
    } catch (e) { this._toast("设置失败", "err"); }
  }

  async _press(key) {
    const eid = (this._config.buttons || {})[key];
    if (!eid) { this._toast("该功能尚未接入", "err"); return; }
    try {
      await this._hass.callService("button", "press", { entity_id: eid });
      this._toast("已执行", "ok");
    } catch (e) { this._toast("执行失败", "err"); }
  }

  _update() {
    if (!this._built) return;
    const c = this._config, q = s => this.querySelector(s);
    // 开关状态
    this._grpKeys("switches").forEach((k) => { const eid = this._grp("switches", k);
      const el = q(`.sw[data-swtoggle="${k}"]`); if (!el) return;
      const missing = !this._st(eid);
      el.className = "sw" + (this._on(eid) ? " on" : "") + (missing ? " dim" : "");
    });
    // 选择值
    this._grpKeys("selects").forEach((k) => { const eid = this._grp("selects", k);
      const el = q(`[data-selval="${k}"]`); if (!el) return;
      el.textContent = this._txt(eid) || "—";
    });
    // 数值
    this._grpKeys("numbers").forEach((k) => { const cfg = this._grp("numbers", k);
      const eid = typeof cfg === "string" ? cfg : cfg.entity;
      const n = this._num(eid);
      const unit = (typeof cfg === "object" && cfg.unit) ? cfg.unit : (k === "charge_limit" ? "%" : "°C");
      this.querySelectorAll(`[data-numval="${k}"]`).forEach(el => {
        el.textContent = n == null ? "—" : (Number.isInteger(n) ? n : n.toFixed(1)) + (k === "charge_limit" ? "" : unit);
      });
      const rg = q(`input[data-range="${k}"]`);
      if (rg && n != null && document.activeElement !== rg) rg.value = n;
    });
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangSettingPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "车辆设置（二级页）",
  description: "空调/充电/安全/远程操作 —— 全部可控制",
  preview: true,
});
})();

/* ===================== lixiang-scene-page.js ===================== */
(function () {

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


/**
 * lixiang-scene-page —— 情景模式（二级页，对齐 App 真实版）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   只有 4 个模式（不是我之前以为的 10 个）：
 *     ① 宠物模式（大卡，右配图）  「离车后可短暂安置宠物，切勿留儿童在车内。」
 *        + 子按钮「舱内影像」
 *     ② 露营模式（大卡，右配图）  「开启后车辆将保持通电，请注意电量情况。」
 *     ③ 擦车模式（小卡，双列）    「车辆将保持下电、车门解锁，方便清洁车辆。」
 *     ④ 离车不下电（小卡，双列）  「锁车后，空调及娱乐系统可持续使用。」
 *
 * 能力边界：
 *   ⚠️ 集成只能读「场景模式」数值（sensor.scene_mode），无法下发切换
 *      集成的能力表里 remoteSceneMode=支持（需 8.2.0+），但命令未实现
 */

const CARD_TAG = "lixiang-scene-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const MODES = [
  { key: "pet",   name: "宠物模式",   icon: "ic_home_scene_mode_lisa.png",
    desc: "离车后可短暂安置宠物，切勿留儿童在车内。",
    grad: "linear-gradient(135deg,#FFF4E8,#FFE7CC)", big: true,
    sub: { label: "舱内影像", icon: "ic_home_photo.png" } },
  { key: "camp",  name: "露营模式",   icon: "ic_home_lightning.png",
    desc: "开启后车辆将保持通电，请注意电量情况。",
    grad: "linear-gradient(135deg,#FFF8EC,#F5E6C8)", big: true },
  { key: "wash",  name: "擦车模式",   icon: "ic_home_control.webp",
    desc: "车辆将保持下电、车门解锁，方便清洁车辆。",
    grad: "linear-gradient(135deg,#F2F6FF,#E3ECFF)", big: false },
  { key: "keep",  name: "离车不下电", icon: "ic_home_electricity.webp",
    desc: "锁车后，空调及娱乐系统可持续使用。",
    grad: "linear-gradient(135deg,#F0F8FF,#DDEBFF)", big: false },
];

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  lixiang-scene-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-scene-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:22px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; position:relative; }
  .back { width:34px; height:34px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center; cursor:pointer; }
  .back img { width:18px; height:18px; opacity:.7; }
  .topbar h1 { position:absolute; left:0; right:0; text-align:center;
               font-size:18px; font-weight:500; margin:0; pointer-events:none; }
  .refresh { margin-left:auto; width:34px; height:34px; border-radius:50%;
             display:flex; align-items:center; justify-content:center;
             cursor:pointer; position:relative; z-index:2; }
  .refresh img { width:17px; height:17px; opacity:.6; }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }

  /* 大卡 */
  .big { margin:10px 16px 0; background:var(--lx-card); border-radius:20px;
         padding:22px 20px; display:flex; align-items:center; gap:14px;
         position:relative; overflow:hidden; min-height:132px; }
  .big .art { position:absolute; right:0; top:0; bottom:0; width:44%;
              border-radius:0 20px 20px 0; display:flex;
              align-items:center; justify-content:center; }
  .big .art img { width:82px; height:82px; object-fit:contain; opacity:.9; }
  .big .tx { flex:1; min-width:0; position:relative; z-index:2; padding-right:36%; }
  .big .hd { display:flex; align-items:center; gap:8px; }
  .big .hd img { width:22px; height:22px; }
  .big .hd .n { font-size:19px; font-weight:500; }
  .big .d { font-size:14px; color:var(--lx-t2); line-height:1.5; margin-top:9px; }

  /* 双列小卡 */
  .duo { display:grid; grid-template-columns:1fr 1fr; gap:13px;
         margin:13px 16px 0; }
  .small { background:var(--lx-card); border-radius:20px; padding:20px 17px;
           min-height:176px; display:flex; flex-direction:column; }
  .small .hd { display:flex; align-items:center; gap:7px; }
  .small .hd img { width:20px; height:20px; }
  .small .hd .n { font-size:16.5px; font-weight:500; }
  .small .d { font-size:13.5px; color:var(--lx-t2); line-height:1.55;
              margin-top:11px; flex:1; }

  /* 开关 */
  /* ★ 2026-10-11 只读徽标：不用 switch 外形冒充可操作开关（技能 §2）
     此前用开关造型 + switch 语义会让用户以为能点开，点后却只弹提示。 */
  .ro-badge { font-size:11.5px; color:var(--lx-t3); background:var(--lx-card,rgba(0,0,0,.04));
              padding:4px 9px; border-radius:8px; white-space:nowrap; }
  .notice { margin:10px 12px 0; padding:10px 12px; border-radius:12px;
            background:rgba(255,149,0,.10); color:var(--lx-t2); font-size:12px; line-height:1.5; }
  .sw.ro { opacity:.5; cursor:not-allowed; }

  /* 子按钮（宠物模式的舱内影像）*/
  .sub { display:inline-flex; align-items:center; gap:6px; font-size:13px;
         padding:9px 15px; border-radius:20px; background:var(--lx-bg);
         color:var(--lx-t2); margin-top:14px; cursor:pointer; }
  .sub img { width:15px; height:15px; }
  .sub:active { transform:scale(.96); }

  /* 能力提示 */
  .notice { margin:18px 16px 0; padding:13px 15px; border-radius:13px;
            background:rgba(10,88,246,.07); font-size:12.5px; line-height:1.65;
            display:flex; gap:9px; }
  .notice img { width:17px; height:17px; flex:0 0 auto; margin-top:2px; }
  .notice b { color:var(--lx-blue); }

  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:82%; text-align:center; line-height:1.5; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangScenePage extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._built = false; }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 16; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _txt(id) { const s = this._st(id);
             return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";

    const big = MODES.filter(m => m.big).map(m => `
      <div class="big" data-k="${m.key}">
        <div class="art" style="background:${m.grad}">
          <img src="${__iconBase}/${m.icon}" alt="" onerror="this.style.visibility='hidden'"></div>
        <div class="tx">
          <div class="hd"><img src="${__iconBase}/${m.icon}" alt=""
            onerror="this.style.visibility='hidden'"><span class="n">${m.name}</span></div>
          <div class="d">${m.desc}</div>
          ${m.sub ? `<div class="sub" data-sub="${m.key}" role="button" tabindex="0">
            <img src="${__iconBase}/${m.sub.icon}" alt="" onerror="this.style.visibility='hidden'">
            ${m.sub.label}</div>` : ""}
          <div class="ro-badge">需在 App / 车机开启</div>
        </div>
      </div>`).join("");

    const small = MODES.filter(m => !m.big).map(m => `
      <div class="small" data-k="${m.key}">
        <div class="hd"><img src="${__iconBase}/${m.icon}" alt=""
          onerror="this.style.visibility='hidden'"><span class="n">${m.name}</span></div>
        <div class="d">${m.desc}</div>
        <div class="ro-badge">需在 App / 车机开启</div>
      </div>`).join("");

    root.innerHTML = `
      <div class="notice">
        情景模式的**开启/关闭目前只能在本机 App 或车机里操作** ——
        集成的控制通道（LiNdn/JOB）尚未打通，这里只做说明与状态展示。
      </div>
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <h1>情景模式</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
      </div>
      ${big}
      <div class="duo">${small}</div>
      <div class="notice">
        <img src="${__iconBase}/ic_home_control.webp" alt="" onerror="this.style.visibility='hidden'">
        <div><b>当前只能查看、不能切换。</b>情景模式的控制指令走车机内部通道
          （集成的能力表显示本车支持 remoteSceneMode，但命令尚未实现），
          请在理想 App 或车机中开启。</div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    const rf = this.querySelector("#refresh");
    const doRf = () => { rf.classList.add("spin"); this._update(); this._toast("已刷新");
      setTimeout(() => rf.classList.remove("spin"), 900); };
    this._a11y(rf, "刷新", doRf);
    rf.addEventListener("click", doRf);

    // 开关（只读：点击说明）
    // ★ 2026-10-11 整页可点 → 统一说明
    //   （原每个"开关"点了只弹同样的话，且 switch 外形会让人以为能远程开启）
    //   技能 §2：不要用状态冒充开关
    const sceneNote = () => this._toast("情景模式需在理想 App 或车机中开启（集成暂不支持远程切换）");
    // 场景卡片用 data-k 标记（big/small 两类都是）
    this.querySelectorAll("[data-k]").forEach(el => {
      const nm = (MODES.find(m => m.key === el.dataset.k) || {}).name || "该场景";
      this._a11y(el, `${nm} · 查看说明`, sceneNote);
      el.addEventListener("click", sceneNote);
    });

    // 舱内影像
    const sub = this.querySelector("[data-sub]");
    if (sub) {
      const act = () => this._toast("舱内影像需在理想 App 内查看（集成未采集车内摄像头）", null, 3400);
      this._a11y(sub, "舱内影像", act);
      sub.addEventListener("click", act);
    }

    this._built = true;
  }

  _toast(msg, kind, ms) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, ms || 2600);
  }

  _update() {
    if (!this._built) return;
    // 场景模式数值 → 判断哪个模式激活（映射未知时只显示原始值在 title）
    const raw = this._txt(this._eid("scene_mode"));
    // ★ 已知限制（证据等级 **[推断]**，未证实）：情景模式数值 → 具体场景的映射
    //   App 侧只有 ModeState 的 0=未设置/1=已设置，**没有场景枚举**；
    //   此前 4 个开关恒显"关"属于**假状态** → 现不做逐场景判断，
    //   只把原始值挂到 data-scene 供排查。
    // 只读页：不再逐个维护开关状态（原本永远全 false，等于假状态）
    const root = this.querySelector(".root");
    if (root && raw != null) root.setAttribute("data-scene", String(raw));
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangScenePage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "情景模式（二级页）",
  description: "宠物 / 露营 / 擦车 / 离车不下电（4 模式，对齐 App 布局）",
  preview: true,
});
})();

/* ===================== lixiang-climate-page.js ===================== */
(function () {

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


/**
 * lixiang-climate-page —— 空调控制（二级页，对齐 App）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   顶部：‹ | 27°C 车内温度 · 2 优 | ⓘ
 *   主控：− 23.5°C +（超大） / 目标温度
 *   圆按钮 ×4：空调 · 极速制冷 · 极速制热 · 除雪除冰
 *   定时卡：06:55 出发 | 24°C · 法定工作日 [开关]
 *   添加按钮（黑色）
 *
 * 能力边界：
 *   ✅ 温度/空调开关/极速制冷/极速制热/除雪除冰/座椅加热通风
 *   ⚠️ 定时出发 —— 集成无实体（走 JOB 通道），置灰并说明
 */

const CARD_TAG = "lixiang-climate-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf"); font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-climate-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-climate-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  /* ── 顶部状态条（浅灰底）── */
  .top { background:var(--lx-card); padding:8px 16px 12px; }
  .toprow { display:flex; align-items:center; gap:10px; }
  .back { width:32px; height:32px; border-radius:50%; background:var(--lx-bg);
          display:flex; align-items:center; justify-content:center; cursor:pointer;
          flex:0 0 auto; }
  .back img { width:18px; height:18px; opacity:.7; }
  .stat { flex:1; display:flex; justify-content:center; gap:26px; }
  .st { text-align:center; }
  .st .v { font-size:21px; font-weight:500; line-height:1.1; }
  .st .v.good { color:var(--lx-green); }
  .st .l { font-size:11px; color:var(--lx-t3); margin-top:2px; }
  .info { width:32px; height:32px; border-radius:50%; display:flex;
          align-items:center; justify-content:center; cursor:pointer; flex:0 0 auto; }
  .info img { width:17px; height:17px; opacity:.5; }

  /* ── 主控区 ── */
  .main { padding:26px 20px 8px; text-align:center; }
  .dial { display:flex; align-items:center; justify-content:center; gap:22px; }
  .dial button { width:44px; height:44px; border-radius:50%; border:none;
                 background:transparent; color:var(--lx-t1); font-size:30px;
                 line-height:1; cursor:pointer; font-weight:300; }
  .dial button:active { transform:scale(.9); }
  .dial button:disabled { opacity:.3; cursor:not-allowed; }
  .dial .t { font-family:"LxNum"; font-size:52px; font-weight:500;
             letter-spacing:-1px; line-height:1; min-width:130px; }
  .dial .t sup { font-size:22px; font-weight:400; }
  .dial .lbl { font-size:12.5px; color:var(--lx-t3); margin-top:8px; }

  /* ── 4 个圆按钮 ── */
  /* ★ 2026-10-09：由固定 4 列改为自适应（新增第 5 个「后视镜加热」后
     宽屏一行 5 个、窄屏自动换行，图标 54px 不会被压缩）*/
  .modes { display:grid; grid-template-columns:repeat(auto-fit,minmax(64px,1fr)); gap:8px;
           padding:22px 16px 0; }
  /* ★ 2026-10-11 该车型无可用模式时的空态 */
  .mempty { grid-column:1/-1; padding:26px 12px; text-align:center;
            color:var(--lx-t3,#9A9A9A); font-size:13px; }
  .m { display:flex; flex-direction:column; align-items:center; gap:7px;
       cursor:pointer; padding:4px 0; border-radius:14px;
       transition:background .15s; }
  .m:hover { background:var(--lx-card); }
  .m .c { width:54px; height:54px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center;
          transition:transform .13s, background .18s; }
  .m:active .c { transform:scale(.9); }
  .m .c img { width:26px; height:26px; }
  .m .n { font-size:11.5px; color:var(--lx-t2); text-align:center; line-height:1.15; }
  .m.on .c { background:rgba(10,88,246,.1); }
  .m.on .n { color:var(--lx-blue); font-weight:500; }
  .m.busy .c { opacity:.5; }
  .m .sp { position:absolute; width:22px; height:22px; border-radius:50%;
           border:2.5px solid rgba(10,88,246,.2); border-top-color:var(--lx-blue);
           animation:spin .7s linear infinite; display:none; }
  .m.busy .sp { display:block; }
  @keyframes spin { to { transform:rotate(360deg); } }

  /* ── 定时卡（能力边界：只展示）── */
  .sect { padding:22px 16px 0; }
  .sect h2 { font-size:13px; color:var(--lx-t3); font-weight:400;
             margin:0 0 10px 4px; }
  .sched { background:var(--lx-card); border-radius:18px; padding:16px;
           display:flex; align-items:center; gap:12px; margin-bottom:10px; }
  .sched .tm { font-family:"LxNum"; font-size:17px; font-weight:500; }
  .sched .tm small { font-size:12px; color:var(--lx-t3); margin-left:3px;
                     font-family:"Licium"; font-weight:400; }
  .sched .sep { color:var(--lx-line); }
  .sched .tp { font-family:"LxNum"; font-size:17px; font-weight:500; }
  .sched .rule { font-size:11.5px; color:var(--lx-t3); margin-top:4px; }
  .sched .sw { margin-left:auto; width:46px; height:28px; border-radius:14px;
               background:#D8D8DC; position:relative; flex:0 0 auto; }
  .sched .sw::after { content:""; position:absolute; top:2px; left:2px;
               width:24px; height:24px; border-radius:50%; background:#fff;
               box-shadow:0 1px 3px rgba(0,0,0,.2); }
  .sched.ro { opacity:.6; }
  .notice { margin:0 16px; padding:12px 14px; border-radius:12px;
            background:rgba(10,88,246,.07); font-size:12px; line-height:1.55;
            display:flex; gap:9px; }
  .notice b { color:var(--lx-blue); }
  .add { margin:16px; text-align:center; background:#1A1A1A; color:#fff;
         border-radius:26px; padding:15px; font-size:15px; cursor:pointer;
         transition:transform .13s; }
  .add:active { transform:scale(.985); }
  .add.ro { background:#C7C7CC; cursor:not-allowed; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:80%; text-align:center; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangClimatePage extends HTMLElement {
  setConfig(c) {
    this._config = c || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base; this._busy = {}; this._built = false;
  }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 18; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id); return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }
  _on(id) { const v = this._txt(id);
            return v != null && ["on","true","1","open","开启"].some(x => String(v).includes(x)); }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  /** 空调模式定义（★ 提到方法里：便于测试与复用）。 */
  _modes() {
    return [
      { key:"ac",      name:"空调",       icon:"ic_home_fan_on.webp",   kind:"climate", field:"ac" },
      { key:"cool",    name:"极速制冷",   icon:"ic_home_ice_cool.webp", kind:"switch",  field:"ac_fast_cold" },
      { key:"heat",    name:"极速制热",   icon:"ic_home_fan_off.webp",  kind:"switch",  field:"ac_fast_hot" },
      { key:"defrost", name:"除雪除冰",   icon:"ic_home_ice_heat.webp", kind:"switch",  field:"ac_defrost" },
      // ★ 2026-10-09：后视镜加热（switch rmCtrl，实车实测可用）
      { key:"mirror",  name:"后视镜加热", icon:"ic_home_rearmirroheat_on_lisa.png",
        kind:"switch", field:"mirror" },
    ];
  }

  /**
   * 该模式在这台车上是否可用（车型适配）。
   * ★ 判据 = 实体是否存在（服务端已按车型能力门控），与首页/设置页同一套思路。
   *   首帧实体表未就绪时放宽，避免闪烁。
   */
  _modeSupported(m, warmup) {
    const eid = this._eid(m.field || "ac");
    if (!eid) return false;
    if (this._st(eid)) return true;
    if (warmup) return !!(this._config || {})[m.field || "ac"];
    return false;
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    root.innerHTML = `
      <div class="top">
        <div class="toprow">
          <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
            <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="">
          </div>
          <div class="stat">
            <div class="st"><div class="v" id="v-room">—</div><div class="l">车内温度</div></div>
            <div class="st"><div class="v good" id="v-aqi">—</div><div class="l" id="l-aqi">空气</div></div>
          </div>
          <div class="info" id="info" role="button" tabindex="0" aria-label="空调信息">
            <img src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'">
          </div>
        </div>
      </div>

      <div class="main">
        <div class="dial">
          <button id="dec" aria-label="降低温度">−</button>
          <div><div class="t"><span id="v-temp">—</span><sup>°C</sup></div></div>
          <button id="inc" aria-label="升高温度">+</button>
        </div>
        <div class="lbl">目标温度</div>
      </div>

      <div class="modes" id="modes"></div>

      <div class="sect">
        <h2>按时出发</h2>
        <div id="scheds"></div>
      </div>

      <div class="notice">
        <img src="${__iconBase}/ic_home_control.webp" onerror="__lxIconFallback(this)" alt="" style="width:17px;height:17px;flex:0 0 auto;margin-top:1px">
        <div><b>按时出发暂不可用。</b>该功能的控制指令走 LiNdn（JOB）通道，集成尚未打通，
          因此仅能展示、不能新增或修改。请在理想 App 内设置。</div>
      </div>

      <div class="add ro" id="add" role="button" tabindex="0" aria-label="添加定时">添加</div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    // 返回
    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    // 温度 ±
    const step = (d) => this._stepTemp(d);
    this._a11y(this.querySelector("#dec"), "降低温度", () => step(-0.5));
    this._a11y(this.querySelector("#inc"), "升高温度", () => step(+0.5));
    this.querySelector("#dec").addEventListener("click", () => step(-0.5));
    this.querySelector("#inc").addEventListener("click", () => step(+0.5));

    // 模式按钮（★ 2026-10-11 按车型能力过滤：没有的模式整块不出现）
    const box = this.querySelector("#modes");
    const modes = this._modes().filter(m => this._modeSupported(m));
    if (!modes.length) {
      box.innerHTML = '<div class="mempty">该车型暂无可用空调模式</div>';
    } else {
      modes.forEach(m => {
        const d = document.createElement("div");
        d.className = "m"; d.dataset.k = m.key;
        d.innerHTML = `<div class="c" style="position:relative"><img src="${__iconBase}/${m.icon}" alt=""
          onerror="this.src='${__iconBase}/ic_home_fan_on.webp'"><div class="sp"></div></div>
          <div class="n">${m.name}</div>`;
        const act = () => this._tapMode(m);
        this._a11y(d, m.name, act);
        d.addEventListener("click", act);
        box.appendChild(d);
      });
    }

    // 添加按钮（只读）
    const add = () => this._toast("按时出发需在理想 App 内设置（JOB 通道未打通）");
    this._a11y(this.querySelector("#add"), "添加定时", add);
    this.querySelector("#add").addEventListener("click", add);

    this._built = true;
  }

  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2600);
  }

  async _stepTemp(delta) {
    const eid = this._eid("target_temp");
    if (!eid) { this._toast("未找到温度实体", "err"); return; }
    const s = this._st(eid); if (!s) return;
    const cur = this._num(eid);
    if (cur == null) { this._toast("当前温度不可读", "err"); return; }
    let v = +(cur + delta).toFixed(1);
    const mn = s.attributes.min, mx = s.attributes.max;
    if (mn != null && v < mn) v = mn;
    if (mx != null && v > mx) v = mx;
    try {
      await this._hass.callService("number", "set_value", { entity_id: eid, value: v });
      this._toast(`已设为 ${v}°C`, "ok");
    } catch (e) { this._toast("设置失败：" + ((e && e.message) || "未知"), "err"); }
  }

  async _tapMode(m) {
    if (this._busy[m.key]) return;
    const el = this.querySelector(`.m[data-k="${m.key}"]`);
    let eid = null, dom = null, svc = null;
    if (m.kind === "climate") {
      eid = this._eid(m.field || "ac"); dom = "climate"; svc = this._on(eid) ? "turn_off" : "turn_on";
    } else {
      // ★ 2026-10-09：字段名由 MODES 显式给出（此前按 key 三元判断，新增项易错绑）
      eid = this._eid(m.field);
      if (eid) { dom = eid.split(".")[0]; svc = this._on(eid) ? "turn_off" : "turn_on"; }
    }
    if (!eid) { this._toast(`${m.name} 未接入`, "err"); return; }
    // switch 域只有 turn_on/turn_off/toggle；非可控域直接说明，别发不存在的服务
    if (dom !== "climate" && dom !== "switch" && dom !== "input_boolean" && dom !== "fan") {
      this._toast(`${m.name} 当前为只读（${dom}），无法远程控制`, "err");
      return;
    }
    this._busy[m.key] = true; el.classList.add("busy");
    try {
      await this._hass.callService(dom, svc, { entity_id: eid });
      this._toast(`${m.name} 已${svc === "turn_on" ? "开启" : "关闭"}`, "ok");
      this._update();
    } catch (e) {
      this._toast(`${m.name} 失败`, "err");
    } finally { delete this._busy[m.key]; el.classList.remove("busy"); }
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);

    q("#v-room").textContent = (t => t == null ? "—" : t.toFixed(0) + "°C")(this._num(this._eid("room_temp")));

    // 空气质量（数值越小越好；App 显示"2 优"）
    const aqi = this._num(this._eid("aqi"));
    const aqiEl = q("#v-aqi");
    if (aqi == null) { aqiEl.textContent = "—"; aqiEl.className = "v"; q("#l-aqi").textContent = "空气质量"; }
    else {
      aqiEl.textContent = aqi <= 50 ? "优" : (aqi <= 100 ? "良" : "差");
      aqiEl.className = "v" + (aqi <= 50 ? " good" : "");
      q("#l-aqi").textContent = `AQI ${aqi}`;
    }

    // 温度
    const t = this._num(this._eid("target_temp"));
    q("#v-temp").textContent = t == null ? "—" : (Number.isInteger(t) ? t : t.toFixed(1));
    const dec = q("#dec"), inc = q("#inc");
    const ts = this._st(this._eid("target_temp"));
    if (ts && ts.attributes) {
      if (dec) dec.disabled = ts.attributes.min != null && t != null && t <= ts.attributes.min;
      if (inc) inc.disabled = ts.attributes.max != null && t != null && t >= ts.attributes.max;
    }

    // 5 个模式状态
    // ★ 从 _modes() 派生，避免"第二份硬编码数据源"（改一处漏一处）
    const MAP = {};
    this._modes().forEach(m => { MAP[m.key] = this._eid(m.field || "ac"); });
    Object.entries(MAP).forEach(([k, eid]) => {
      const el = q(`.m[data-k="${k}"]`); if (!el) return;
      const ok = !!eid && !!this._st(eid);
      el.className = "m" + (ok && this._on(eid) ? " on" : "") + (this._busy[k] ? " busy" : "");
      el.style.opacity = ok ? "" : ".45";
    });

    // 定时组（当前仅展示占位：集成无实体）
    q("#scheds").innerHTML = `
      <div class="sched ro">
        <div><div class="tm">06:55<small>出发</small></div>
             <div class="rule">法定工作日</div></div>
        <div class="sep">│</div>
        <div><div class="tp">24°C</div></div>
        <div class="sw"></div>
      </div>
      <div class="sched ro">
        <div><div class="tm">07:00<small>出发</small></div>
             <div class="rule">法定工作日</div></div>
        <div class="sep">│</div>
        <div><div class="tp">22°C</div></div>
        <div class="sw"></div>
      </div>`;
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangClimatePage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "空调控制（二级页）",
  description: "温度调节 + 空调/极速制冷/极速制热/除雪除冰 + 空气质量",
  preview: true,
});
})();

/* ===================== lixiang-seat-page.js ===================== */
(function () {

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


/**
 * lixiang-seat-page —— 座椅控制（二级页，对齐 App）
 *
 * App 实测布局（截图 1260×2844 @3x）：
 *   · 座椅俯视图占 60% 高度，控制圆按钮【叠在座椅上】
 *   · 方向盘加热独立在顶部
 *   · 主驾/副驾：靠背加热 + 坐垫通风（各 2 个）
 *   · 二排：3 个加热（左中右）+ 2 个通风（左/右，中间无）
 *   · 激活态橙色 #FF9500，未激活灰色
 *
 * 实体（fan 域，9 个）：
 *   fan.主驾座椅加热 / 通风 · 副驾座椅加热 / 通风
 *   fan.二排{左,中,右}座椅加热 · fan.二排{左,右}座椅通风
 *   switch.方向盘加热
 */

const CARD_TAG = "lixiang-seat-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-seat-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-seat:#F2F2F5; }
  @media (prefers-color-scheme: dark) {
    lixiang-seat-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E;
            --lx-blue:#4C9AFF; --lx-seat:#2C2C2E; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  .top { background:var(--lx-card); padding:8px 16px 12px; }
  .toprow { display:flex; align-items:center; gap:10px; }
  .back { width:32px; height:32px; border-radius:50%; background:var(--lx-bg);
          display:flex; align-items:center; justify-content:center; cursor:pointer; flex:0 0 auto; }
  .back img { width:18px; height:18px; opacity:.7; }
  .stat { flex:1; display:flex; justify-content:center; gap:26px; }
  .st { text-align:center; }
  .st .v { font-size:21px; font-weight:500; line-height:1.1; }
  .st .v.good { color:var(--lx-green); }
  .st .l { font-size:11px; color:var(--lx-t3); margin-top:2px; }
  .info { width:32px; height:32px; }

  /* ── 座椅区（俯视布局）── */
  .stage { position:relative; padding:18px 14px 8px; }
  .wheel { display:flex; justify-content:center; margin-bottom:6px; }

  /* 单排两座 */
  .row2seat { display:grid; grid-template-columns:1fr 1fr; gap:26px;
              padding:0 18px; margin-top:6px; }
  /* 二排三座 */
  .row3seat { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;
              padding:0 8px; margin-top:14px; }

  /* 座椅本体（白色圆角块，模拟座椅）*/
  .seat { background:var(--lx-seat); border-radius:22px; padding:10px 8px 12px;
          display:flex; flex-direction:column; align-items:center; gap:9px;
          box-shadow:0 1px 3px rgba(0,0,0,.04); }
  .seat .pile { width:100%; height:40px; border-radius:12px;
                background:var(--lx-bg); opacity:.75; margin-bottom:2px; }
  .seat.bench { border-radius:18px; padding:10px 6px 12px; }
  .seat.bench .pile { height:34px; }

  /* 圆按钮 */
  .btn { width:56px; height:56px; border-radius:50%; background:var(--lx-bg);
         border:none; display:flex; align-items:center; justify-content:center;
         cursor:pointer; box-shadow:0 1px 4px rgba(0,0,0,.07);
         transition:transform .13s, background .2s, box-shadow .2s; position:relative; }
  .btn:active { transform:scale(.9); }
  .btn:disabled, .btn.dim { opacity:.35; cursor:not-allowed; }
  .btn img { width:26px; height:26px; }
  .btn svg { width:26px; height:26px; }
  /* 激活：橙色 */
  .btn.on { background:#FFF4E5; box-shadow:0 0 0 1.5px var(--lx-orange) inset; }
  .btn.on img, .btn.on svg { filter:none; }
  .btn .sp { position:absolute; width:22px; height:22px; border-radius:50%;
             border:2.5px solid rgba(255,149,0,.25); border-top-color:var(--lx-orange);
             animation:spin .7s linear infinite; display:none; }
  .btn.busy .sp { display:block; }
  .btn.busy img, .btn.busy svg { opacity:.2; }
  @keyframes spin { to { transform:rotate(360deg); } }

  /* 底部卡片区 */
  .sheet { margin-top:18px; background:var(--lx-bg); border-radius:22px 22px 0 0;
           padding:6px 16px 20px; box-shadow:0 -2px 12px rgba(0,0,0,.04); }
  .grab { width:36px; height:4px; border-radius:2px; background:var(--lx-line);
          margin:6px auto 16px; }
  .dial { display:flex; align-items:center; justify-content:center; gap:22px; }
  .dial button { width:40px; height:40px; border-radius:50%; border:none;
                 background:transparent; color:var(--lx-t1); font-size:28px;
                 cursor:pointer; font-weight:300; }
  .dial button:active { transform:scale(.9); }
  .dial .t { font-family:"LxNum"; font-size:46px; font-weight:500; line-height:1; }
  .dial .t sup { font-size:20px; font-weight:400; }
  .tlbl { text-align:center; font-size:12px; color:var(--lx-t3); margin-top:6px; }
  .modes { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin-top:20px; }
  /* ★ 2026-10-11 该车型无可用模式时的空态 */
  .mempty { grid-column:1/-1; padding:26px 12px; text-align:center;
            color:var(--lx-t3,#9A9A9A); font-size:13px; }
  .m { display:flex; flex-direction:column; align-items:center; gap:6px;
       cursor:pointer; padding:4px 0; border-radius:12px; }
  .m:hover { background:var(--lx-card); }
  .m .c { width:50px; height:50px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center; }
  .m .c img { width:24px; height:24px; }
  .m .n { font-size:11px; color:var(--lx-t2); }
  .m.on .c { background:rgba(10,88,246,.1); }
  .m.on .n { color:var(--lx-blue); }
  .sched { margin-top:20px; background:var(--lx-card); border-radius:16px;
           padding:14px 16px; display:flex; align-items:center; gap:10px; }
  .sched .tm { font-family:"LxNum"; font-size:16px; font-weight:500; }
  .sched .tm small { font-size:11px; color:var(--lx-t3); font-family:"Licium";
                     font-weight:400; margin-left:3px; }
  .sched .tp { font-family:"LxNum"; font-size:16px; font-weight:500; }
  .sched .rule { font-size:11px; color:var(--lx-t3); margin-top:3px; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

/* 座椅图标（SVG，橙色/灰色由 CSS 控制）*/
const ICON_HEAT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="2" stroke-linecap="round"><path d="M8 14c0-1.5 1-2 1-3.5S8 8 8 8"/>
  <path d="M12 15c0-1.5 1-2 1-3.5S12 9 12 9"/><path d="M16 14c0-1.5 1-2 1-3.5S16 8 16 8"/></svg>`;
const ICON_FAN = `<svg viewBox="0 0 24 24" fill="currentColor">
  <circle cx="12" cy="12" r="2.2"/><path d="M12 3.5c1.6 0 2.6 2 1.7 3.5-.5.9-.5 1.9 0 2.6-1.4-.6-2.6-1.2-3.2-2.3C9.6 5.4 10.4 3.5 12 3.5z"/>
  <path d="M20.5 12c0 1.6-2 2.6-3.5 1.7-.9-.5-1.9-.5-2.6 0 .6-1.4 1.2-2.6 2.3-3.2 1.9-.9 3.8-.1 3.8 1.5z"/>
  <path d="M12 20.5c-1.6 0-2.6-2-1.7-3.5.5-.9.5-1.9 0-2.6 1.4.6 2.6 1.2 3.2 2.3.9 1.9.1 3.8-1.5 3.8z"/>
  <path d="M3.5 12c0-1.6 2-2.6 3.5-1.7.9.5 1.9.5 2.6 0-.6 1.4-1.2 2.6-2.3 3.2-1.9.9-3.8.1-3.8-1.5z"/></svg>`;

class LixiangSeatPage extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._busy = {}; this._built = false; }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 20; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _on(id) {
    const s = this._st(id); if (!s) return false;
    const v = String(s.state).toLowerCase();
    if (["on","true","open"].includes(v)) return true;
    const n = parseFloat(s.state);
    return !isNaN(n) && n > 0;        // fan 域常用 0-3 档
  }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  _seatHtml(keys, label, opts) {
    // keys: {heat, vent} —— 自动发现的字段名
    const heat = keys.heat ? this._eid(keys.heat) : null;
    const vent = keys.vent ? this._eid(keys.vent) : null;
    const o = opts || {};
    // ★ 2026-10-11 车型适配：整排都没有可控件 → 整排不渲染。
    //   否则会出现"一个空座椅图形，点不动"（如 5 座车的二排中、
    //   或这台车只有前排座椅加热）。
    if (!heat && !vent) return "";
    return `<div class="seat${o.bench ? " bench" : ""}" data-seat="${label}">
      <div class="pile"></div>
      ${heat ? `<button class="btn" data-fan="${keys.heat}" aria-label="${label}加热">
        <span class="ic" style="color:#9A9A9A">${ICON_HEAT}</span><span class="sp"></span></button>` : ""}
      ${vent ? `<button class="btn" data-fan="${keys.vent}" aria-label="${label}通风">
        <span class="ic" style="color:#9A9A9A">${ICON_FAN}</span><span class="sp"></span></button>` : ""}
    </div>`;
  }

  /** 模式定义（★ 提到方法里，与空调页同构）。 */
  _modes() {
    return [
      { key:"ac",      name:"空调",     icon:"ic_home_fan_on.webp",  src:"ac" },
      { key:"cool",    name:"极速制冷", icon:"ic_home_ice_cool.webp", src:"ac_fast_cold" },
      { key:"heat",    name:"极速制热", icon:"ic_home_fan_off.webp",  src:"ac_fast_hot" },
      { key:"defrost", name:"除雪除冰", icon:"ic_home_ice_heat.webp", src:"ac_defrost" },
    ];
  }

  /**
   * 该模式在这台车上是否可用（车型适配）。
   * ★ 判据 = 实体是否存在（服务端已按车型能力门控），与首页/空调/设置页一致。
   */
  _modeSupported(m, warmup) {
    const eid = this._eid(m.src);
    if (!eid) return false;
    if (this._st(eid)) return true;
    if (warmup) return !!(this._config || {})[m.src];
    return false;
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";

    const wheelEid = this._eid("steer_heat");
    root.innerHTML = `
      <div class="top">
        <div class="toprow">
          <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
            <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
          <div class="stat">
            <div class="st"><div class="v" id="v-room">—</div><div class="l">车内温度</div></div>
            <div class="st"><div class="v good" id="v-aqi">—</div><div class="l">空气</div></div>
          </div>
          <div class="info"></div>
        </div>
      </div>

      <div class="stage">
        ${wheelEid ? `<div class="wheel">
          <button class="btn" data-fan="steer_heat" aria-label="方向盘加热">
            <span class="ic" style="color:#9A9A9A">${ICON_HEAT}</span><span class="sp"></span></button>
        </div>` : ""}

        ${(() => {
          const r2 = [this._seatHtml({heat:"seat_fl_heat", vent:"seat_fl_vent"}, "主驾"),
                      this._seatHtml({heat:"seat_fr_heat", vent:"seat_fr_vent"}, "副驾")].filter(Boolean).join("");
          const r3 = [this._seatHtml({heat:"seat_rl_heat", vent:"seat_rl_vent"}, "二排左", {bench:true}),
                      this._seatHtml({heat:"seat_rc_heat"}, "二排中", {bench:true}),
                      this._seatHtml({heat:"seat_rr_heat", vent:"seat_rr_vent"}, "二排右", {bench:true})].filter(Boolean).join("");
          // ★ 整排都为空 → 该排容器也不出现
          return (r2 ? `<div class="row2seat">${r2}</div>` : "")
               + (r3 ? `<div class="row3seat">${r3}</div>` : "");
        })()}
      </div>

      <div class="sheet">
        <div class="grab"></div>
        <div class="dial">
          <button id="dec" aria-label="降低温度">−</button>
          <div class="t"><span id="v-temp">—</span><sup>°C</sup></div>
          <button id="inc" aria-label="升高温度">+</button>
        </div>
        <div class="tlbl">目标温度</div>
        <div class="modes" id="modes"></div>
        <div class="sched">
          <div><div class="tm">06:55<small>出发</small></div>
               <div class="rule">法定工作日</div></div>
          <div style="color:var(--lx-line)">│</div>
          <div class="tp">24°C</div>
        </div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    // 返回
    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/climate";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    // 座椅按钮（统一绑定）
    root.querySelectorAll("[data-fan]").forEach(btn => {
      const key = btn.dataset.fan;
      const act = () => this._toggleFan(key, btn);
      this._a11y(btn, btn.getAttribute("aria-label"), act);
      btn.addEventListener("click", act);
    });

    // 温度 ±
    const step = (d) => this._stepTemp(d);
    this._a11y(this.querySelector("#dec"), "降低温度", () => step(-0.5));
    this._a11y(this.querySelector("#inc"), "升高温度", () => step(+0.5));
    this.querySelector("#dec").addEventListener("click", () => step(-0.5));
    this.querySelector("#inc").addEventListener("click", () => step(+0.5));

    // 模式（★ 2026-10-11 按车型能力过滤，与空调页同一套）
    const mb = this.querySelector("#modes");
    const modes = this._modes().filter(m => this._modeSupported(m));
    if (!modes.length) {
      mb.innerHTML = '<div class="mempty">该车型暂无可用模式</div>';
    } else {
      modes.forEach(m => {
        const d = document.createElement("div");
        d.className = "m"; d.dataset.k = m.key;
        d.innerHTML = `<div class="c"><img src="${__iconBase}/${m.icon}" alt=""
          onerror="this.src='${__iconBase}/ic_home_fan_on.webp'"></div><div class="n">${m.name}</div>`;
        const act = () => this._tapMode(m);
        this._a11y(d, m.name, act);
        d.addEventListener("click", act);
        mb.appendChild(d);
      });
    }

    this._built = true;
  }

  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2400);
  }

  async _toggleFan(key, btn) {
    const eid = this._eid(key);
    if (!eid) { this._toast("该座椅功能未接入", "err"); return; }
    if (this._busy[key]) return;
    this._busy[key] = true; btn.classList.add("busy");
    const dom = eid.split(".")[0];
    try {
      if (dom === "fan") {
        // fan 域：0=关，1/2/3=档位 → 按 App 语义做开关
        const cur = this._num(eid);
        const next = (cur != null && cur > 0) ? 0 : 3;   // 开到最高档
        await this._hass.callService("fan", "set_percentage", {
          entity_id: eid, percentage: next === 0 ? 0 : 100 });
      } else {
        await this._hass.callService(dom, this._on(eid) ? "turn_off" : "turn_on", { entity_id: eid });
      }
      this._toast((next === undefined ? "" : "") + "已切换", "ok");
      this._update();
    } catch (e) {
      // 降级：尝试 toggle
      try {
        await this._hass.callService("homeassistant", "toggle", { entity_id: eid });
        this._update();
      } catch (e2) { this._toast("操作失败：" + ((e2 && e2.message) || "未知"), "err"); }
    } finally { delete this._busy[key]; btn.classList.remove("busy"); }
  }

  async _stepTemp(d) {
    const eid = this._eid("target_temp");
    if (!eid) return;
    const cur = this._num(eid); if (cur == null) return;
    const s = this._st(eid);
    let v = +(cur + d).toFixed(1);
    if (s && s.attributes.min != null && v < s.attributes.min) v = s.attributes.min;
    if (s && s.attributes.max != null && v > s.attributes.max) v = s.attributes.max;
    try {
      await this._hass.callService("number", "set_value", { entity_id: eid, value: v });
      this._toast(`已设为 ${v}°C`, "ok");
    } catch (e) { this._toast("设置失败", "err"); }
  }

  async _tapMode(m) {
    const eid = this._eid(m.src);
    if (!eid) { this._toast(`${m.name} 未接入`, "err"); return; }
    const dom = m.src === "ac" ? "climate" : eid.split(".")[0];
    try {
      await this._hass.callService(dom, this._on(eid) ? "turn_off" : "turn_on", { entity_id: eid });
      this._toast(`${m.name} 已切换`, "ok");
      this._update();
    } catch (e) { this._toast(`${m.name} 失败`, "err"); }
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);
    q("#v-room").textContent = (t => t == null ? "—" : t.toFixed(0) + "°C")(this._num(this._eid("room_temp")));
    const aqi = this._num(this._eid("aqi"));
    const a = q("#v-aqi");
    a.textContent = aqi == null ? "—" : (aqi <= 50 ? "优" : (aqi <= 100 ? "良" : "差"));
    a.className = "v" + (aqi != null && aqi <= 50 ? " good" : "");

    const t = this._num(this._eid("target_temp"));
    q("#v-temp").textContent = t == null ? "—" : (Number.isInteger(t) ? t : t.toFixed(1));

    // ★ 从 _modes() 派生（避免第二份硬编码数据源）
    const MODES = {};
    this._modes().forEach(m => { MODES[m.key] = this._eid(m.src); });
    Object.entries(MODES).forEach(([k, f]) => {
      const el = q(`.m[data-k="${k}"]`); if (!el) return;
      const eid = this._eid(f);
      el.className = "m" + (eid && this._on(eid) ? " on" : "");
    });

    // 座椅按钮状态（激活 = 橙色）
    this.querySelectorAll("[data-fan]").forEach(btn => {
      const key = btn.dataset.fan;
      const eid = this._eid(key);
      const ok = !!eid && !!this._st(eid);
      btn.className = "btn" + (ok && this._on(eid) ? " on" : "") + (this._busy[key] ? " busy" : "")
                    + (ok ? "" : " dim");
      btn.disabled = !ok;
      const ic = btn.querySelector(".ic");
      if (ic) ic.style.color = (ok && this._on(eid)) ? "#FF9500" : "#9A9A9A";
    });
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangSeatPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "座椅控制（二级页）",
  description: "座椅俯视布局：主/副驾加热通风 + 二排三座 + 方向盘加热，激活橙色",
  preview: true,
});
})();

/* ===================== lixiang-location-page.js ===================== */
(function () {

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


/**
 * lixiang-location-page —— 车辆位置（二级页，对齐 App）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   地图占 64%，车辆图标居中，左下「闪灯/鸣笛」浮动按钮
 *   地址卡：完整地址 + 距您 xx m + 导航按钮
 *   驻车照片：3 路（俯视/前/后）+ 时间 + 重新拍照
 *
 * 实体：
 *   device_tracker.车辆位置（lat/lon）
 *   button.闪灯 / 鸣笛 / 远程拍照
 *   sensor.360 拍照状态 / 拍照信息
 *
 * 能力边界：
 *   ✅ 驻车照片可显示（2026-10-03 打通）：
 *      VSS 拍照时间 → 构造 5 路 OSS key → lixiang_auto.get_svm_photo
 *      换签名 URL → <img>。链路逆向自 5 月抓包。
 *   ✅ 闪灯/鸣笛 可触发
 *   ⚠️ 触发拍照（button.远程拍照）实测 2009 —— 与充电同因，需 JOB 通道
 */

const CARD_TAG = "lixiang-location-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-location-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-location-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  /* ── 地图区 ── */
  .mapwrap { position:relative; height:340px; background:#E8EEF4; overflow:hidden; }
  /* ── 自建地图（高德瓦片，免 key/免登录）── */
  .tiles { position:absolute; inset:0; cursor:grab; touch-action:none; }
  .tiles.grabbing { cursor:grabbing; }
  .tiles img { position:absolute; width:256px; height:256px; user-select:none;
               pointer-events:none; -webkit-user-drag:none; }
  /* ★ 2026-10-03：车标改为【小车图形】（对齐 App）——
     原来是个 36px 大圆点，太大且不像车，无法表达"车辆位置"。
     小车用已有的 icon_car_loc.webp，尺寸收小到 22px。 */
  .puck { position:absolute; width:22px; height:22px; margin:-11px 0 0 -11px;
          display:flex; align-items:center; justify-content:center;
          pointer-events:none; z-index:4; }
  .puck img { width:22px; height:22px;
              filter:drop-shadow(0 1px 3px rgba(0,0,0,.45)); }
  .mapctl { position:absolute; right:12px; bottom:12px; display:flex;
            flex-direction:column; gap:6px; z-index:5; }
  .mapctl span { width:32px; height:32px; border-radius:8px;
                 background:rgba(255,255,255,.96); display:flex;
                 align-items:center; justify-content:center; font-size:17px;
                 color:#333; cursor:pointer; box-shadow:0 1px 4px rgba(0,0,0,.16);
                 user-select:none; }
  .mapctl span:active { transform:scale(.93); }
  .mapwrap iframe { width:100%; height:100%; border:0; }
  .mapwrap .ph { position:absolute; inset:0; display:flex; flex-direction:column;
                 align-items:center; justify-content:center; gap:10px;
                 font-size:12.5px; color:var(--lx-t3); text-align:center; padding:0 30px; }
  .mapwrap .ph .car { width:44px; height:62px; }
  .back { position:absolute; left:14px; top:14px; width:38px; height:38px;
          border-radius:50%; background:rgba(255,255,255,.95); display:flex;
          align-items:center; justify-content:center; cursor:pointer; z-index:3;
          box-shadow:0 1px 5px rgba(0,0,0,.12); }
  .back img { width:19px; height:19px; opacity:.75; }
  /* 浮动按钮 */
  .floats { position:absolute; left:14px; bottom:14px; display:flex; gap:9px; z-index:3; }
  .fbtn { display:inline-flex; align-items:center; gap:6px; font-size:13px;
          padding:9px 15px; border-radius:22px; background:rgba(255,255,255,.97);
          box-shadow:0 2px 8px rgba(0,0,0,.13); cursor:pointer;
          transition:transform .13s; white-space:nowrap; }
  .fbtn:active { transform:scale(.94); }
  .fbtn img { width:17px; height:17px; }
  .fbtn.busy { opacity:.55; }

  /* ── 地址卡 ── */
  .addr { padding:16px 20px 14px; display:flex; align-items:flex-start; gap:12px; }
  .addr .tx { flex:1; min-width:0; }
  .addr .a { font-size:16px; font-weight:500; line-height:1.4; }
  .addr .d { font-size:13px; color:var(--lx-t3); margin-top:6px; }
  .nav { width:46px; height:46px; border-radius:50%; background:var(--lx-card);
         display:flex; align-items:center; justify-content:center; cursor:pointer;
         flex:0 0 auto; transition:transform .13s; }
  .nav:active { transform:scale(.92); }
  .nav img { width:22px; height:22px; }

  /* ── 驻车照片 ── */
  .sec { padding:12px 0 0; border-top:8px solid var(--lx-card); }
  .sechd { display:flex; align-items:center; gap:10px; padding:14px 20px 10px; }
  .sechd .t { font-size:16px; font-weight:500; }
  .sechd .ts { font-size:12.5px; color:var(--lx-t3); margin-top:3px; }
  .sechd .ra { margin-left:auto; display:inline-flex; align-items:center; gap:6px;
               font-size:13px; padding:8px 14px; border-radius:20px;
               background:var(--lx-card); cursor:pointer; }
  .sechd .ra img { width:16px; height:16px; }
  .photos { display:flex; gap:10px; padding:0 20px 6px; overflow-x:auto;
            scrollbar-width:none; }
  .photos::-webkit-scrollbar { display:none; }
  .ph { flex:0 0 auto; width:150px; height:100px; border-radius:12px;
        background:#2A2A2E; position:relative; overflow:hidden;
        display:flex; align-items:flex-end; }
  .ph img { width:100%; height:100%; object-fit:cover; }
  .ph .lbl { position:absolute; left:8px; top:8px; font-size:11px; color:#fff;
             background:rgba(0,0,0,.45); padding:2px 7px; border-radius:6px; }
  .ph { cursor:pointer; }
  .ph:active { transform:scale(.97); }
  .ph .zoom { position:absolute; right:6px; bottom:6px; width:20px; height:20px;
              border-radius:50%; background:rgba(0,0,0,.5); color:#fff;
              display:flex; align-items:center; justify-content:center;
              font-size:12px; line-height:1; }
  /* ── 照片大图查看（点缩略图打开）── */
  .lightbox { position:fixed; inset:0; background:rgba(0,0,0,.92); z-index:9999;
              display:none; flex-direction:column; }
  .lightbox.on { display:flex; }
  .lightbox .lbhd { display:flex; align-items:center; gap:10px;
                    padding:14px 18px; color:#fff; font-size:15px; }
  .lightbox .lbx { margin-left:auto; font-size:22px; cursor:pointer;
                   width:32px; height:32px; display:flex; align-items:center;
                   justify-content:center; border-radius:50%;
                   background:rgba(255,255,255,.14); }
  .lightbox .lbbody { flex:1; display:flex; align-items:center;
                      justify-content:center; padding:0 14px 22px; }
  .lightbox img { max-width:100%; max-height:100%; object-fit:contain;
                  border-radius:10px; }
  .lightbox .lbnav { display:flex; gap:8px; justify-content:center;
                     padding:0 0 18px; }
  .lightbox .lbnav span { padding:7px 15px; border-radius:18px;
                          background:rgba(255,255,255,.14); color:#fff;
                          font-size:13px; cursor:pointer; }
  .lightbox .lbnav span.on { background:var(--lx-blue); }
  .ph .none { position:absolute; inset:0; display:flex; align-items:center;
              justify-content:center; font-size:11px; color:rgba(255,255,255,.5);
              text-align:center; padding:0 10px; line-height:1.5; }
  .tip { padding:10px 20px 0; font-size:11.5px; color:var(--lx-t3); line-height:1.6; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangLocationPage extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._busy = {}; this._built = false; }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 18; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _txt(id) { const s = this._st(id);
             return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    root.innerHTML = `
      <div class="mapwrap" id="mapwrap">
        <div class="tiles" id="tiles"></div>
        <div class="puck" id="puck" style="display:none">
          <img src="${__iconBase}/icon_car_loc.webp" onerror="__lxIconFallback(this)" alt="车辆位置"></div>
        <div class="mapctl">
          <span id="cz-in" role="button" tabindex="0" aria-label="放大">+</span>
          <span id="cz-out" role="button" tabindex="0" aria-label="缩小">−</span>
          <span id="cz-me" role="button" tabindex="0" aria-label="回到车辆">⌖</span>
        </div>
        <div class="ph" id="mapph" style="display:none">
          <img class="car" src="${__iconBase}/icon_car_loc.webp" onerror="__lxIconFallback(this)" alt="">
          <div id="coords">定位获取中…</div>
        </div>
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <div class="floats">
          <div class="fbtn" id="btn-flash" role="button" tabindex="0" aria-label="闪灯">
            <img src="${__iconBase}/ic_home_lightning.png" alt="" onerror="this.style.visibility='hidden'">闪灯</div>
          <div class="fbtn" id="btn-horn" role="button" tabindex="0" aria-label="鸣笛">
            <img src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'">鸣笛</div>
        </div>
      </div>

      <div class="addr">
        <div class="tx">
          <div class="a" id="v-addr">地址获取中…</div>
          <div class="d" id="v-dist"></div>
        </div>
        <div class="nav" id="btn-nav" role="button" tabindex="0" aria-label="导航到车辆">
          <img src="${__iconBase}/ic_home_navigation.webp" onerror="__lxIconFallback(this)" alt=""></div>
      </div>

      <div class="sec">
        <div class="sechd">
          <div><div class="t">驻车照片</div><div class="ts" id="v-photots">—</div></div>
          <div class="ra" id="btn-photo" role="button" tabindex="0" aria-label="重新拍照">
            <img src="${__iconBase}/ic_home_photo.png" alt="" onerror="this.style.visibility='hidden'">重新拍照</div>
        </div>
        <div class="photos" id="photos"></div>
        <div class="lightbox" id="lightbox" role="dialog" aria-modal="true"
             aria-label="驻车照片大图">
          <div class="lbhd"><span id="lb-title">驻车照片</span>
            <div class="lbx" id="lb-close" role="button" tabindex="0"
                 aria-label="关闭">×</div></div>
          <div class="lbbody"><img id="lb-img" alt=""></div>
          <div class="lbnav" id="lb-nav"></div>
        </div>
        <div class="tip">驻车照片由车辆摄像头拍摄。点击「重新拍照」后，
          照片会显示在这里（5 路：前 / 后 / 左 / 右 / 俯视）。
          图片链接约 24 小时有效，过期后需重新获取。</div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    const flash = () => this._press("btn_flash", "闪灯");
    const horn = () => this._press("btn_horn", "鸣笛");
    const photo = () => this._press("btn_photo", "远程拍照");
    [["#btn-flash", flash, "闪灯"], ["#btn-horn", horn, "鸣笛"],
     ["#btn-photo", photo, "重新拍照"]].forEach(([sel, fn, label]) => {
      const el = this.querySelector(sel); if (!el) return;
      this._a11y(el, label, fn);
      el.addEventListener("click", fn);
    });

    // 大图查看器的关闭（点遮罩空白处也关）
    const lb = this.querySelector("#lightbox");
    if (lb) {
      this._a11y(this.querySelector("#lb-close"), "关闭大图",
                 () => this._closeLightbox());
      lb.addEventListener("click", (ev) => {
        if (ev.target === lb || ev.target.classList.contains("lbbody")) {
          this._closeLightbox();
        }
      });
    }

    // 导航
    const nav = () => {
      const dt = this._st(this._eid("tracker"));
      const la = dt && dt.attributes.latitude, lo = dt && dt.attributes.longitude;
      if (la == null || lo == null) { this._toast("暂无定位", "err"); return; }
      // 用系统地图 URL scheme（手机端可唤起）
      const url = `https://uri.amap.com/marker?position=${lo},${la}&name=我的车`;
      window.open(url, "_blank");
    };
    this._a11y(this.querySelector("#btn-nav"), "导航到车辆", nav);
    this.querySelector("#btn-nav").addEventListener("click", nav);

    this._built = true;
  }

  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2400);
  }

  async _press(field, label) {
    const eid = this._eid(field);
    if (!eid) { this._toast(`${label} 未接入`, "err"); return; }
    if (this._busy[field]) return;
    this._busy[field] = true;
    const el = this.querySelector(field === "btn_flash" ? "#btn-flash"
              : (field === "btn_horn" ? "#btn-horn" : "#btn-photo"));
    if (el) el.classList.add("busy");
    try {
      await this._hass.callService("button", "press", { entity_id: eid });
      this._toast(`${label} 已触发`, "ok");
    } catch (e) {
      this._toast(`${label} 失败：${(e && e.message) || "未知"}`, "err");
    } finally {
      delete this._busy[field];
      if (el) el.classList.remove("busy");
    }
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);

    // 定位
    const dt = this._st(this._eid("tracker"));
    const la = dt && dt.attributes.latitude, lo = dt && dt.attributes.longitude;
    const coords = q("#coords");
    if (la != null && lo != null) {
      coords.textContent = `${Number(la).toFixed(5)}, ${Number(lo).toFixed(5)}`;
      // ★ 2026-10-03：改用【自建地图】——直接拼高德瓦片。
      //   此前用 iframe 嵌 uri.amap.com/marker，但那是网页版，
      //   在 iframe 里会要求登录（截图里是「请按住滑块拖动」验证页）。
      //   高德瓦片本身免 key、免登录：
      //     https://webrd0{s}.is.autonavi.com/appmaptile?...&x=&y=&z=
      //   注意 HA 存 WGS84、高德瓦片是 GCJ-02，需要纠偏（见 _wgs2gcj）。
      this._initMap(la, lo);
    } else {
      coords.textContent = "暂无定位（车辆可能离线）";
    }

    // 地址（HA 无反向地理编码时显示坐标 + 提示）
    const addrState = this._txt(this._eid("address"));
    const addrEl = q("#v-addr");
    if (dt && dt.attributes.address) addrEl.textContent = dt.attributes.address;
    else if (addrState && !/^\d+$/.test(String(addrState))) addrEl.textContent = String(addrState);
    else if (la != null && lo != null) addrEl.textContent = `坐标 ${Number(la).toFixed(4)}, ${Number(lo).toFixed(4)}`;
    else addrEl.textContent = "地址不可用";

    // 距离（本机到车；浏览器定位不可用时隐藏）
    const distEl = q("#v-dist");
    if (this._myPos && la != null && lo != null) {
      const d = this._haversine(this._myPos[0], this._myPos[1], la, lo);
      distEl.textContent = d < 1000 ? `距您 ${Math.round(d)}m` : `距您 ${(d/1000).toFixed(1)}km`;
    } else distEl.textContent = "";

    // 拍照时间
    const info = this._txt(this._eid("photo_info"));
    const stt = this._txt(this._eid("photo_status"));
    q("#v-photots").textContent = info || stt || "暂无记录";

    // ★ 2026-10-03：驻车照片改为【真实图片】
    //   链路（抓包逆向）：VSS 拍照时间 → 构造 5 路 OSS key →
    //   lixiang_auto.get_svm_photo 换签名 URL → <img src>。
    //   URL 有时效，所以缓存 2 分钟（够一次浏览，又不至于显示过期图）。
    this._renderPhotos(q, info);
  }

  /** 渲染 5 路驻车照片（前/后/左/右/俯视）。 */
  async _renderPhotos(q, photoTime) {
    const box = q("#photos");
    if (!box) return;
    const ANGLES = [["Top", "俯视"], ["Front", "前"], ["Rear", "后"],
                    ["Left", "左"], ["Right", "右"]];

    // 首次：占位骨架（避免空白闪烁）
    if (!box.dataset.init) {
      box.dataset.init = "1";
      box.innerHTML = ANGLES.map(([k, lbl]) =>
        `<div class="ph" data-a="${k}"><div class="none">${lbl}视图<br>加载中…</div>
         <div class="lbl">${lbl}</div></div>`).join("");
    }

    const stamp = String(photoTime || "");
    const now = Date.now();
    if (this._phCache && this._phCache.stamp === stamp &&
        now - this._phCache.at < 120000) {
      this._paintPhotos(box, this._phCache.urls, ANGLES);
      return;
    }
    if (this._phBusy) return;
    this._phBusy = true;
    try {
      const res = await this._hass.callService(
        "lixiang_auto", "get_svm_photo",
        photoTime ? { time: photoTime } : {}, undefined, false, true);
      const payload = (res && (res.result || res.response)) || {};
      const first = Object.values(payload)[0] || {};
      const urls = first.urls || {};
      this._phCache = { stamp, urls, at: Date.now() };
      this._paintPhotos(box, urls, ANGLES, first.error);
    } catch (err) {
      this._paintPhotos(box, {}, ANGLES, String(err && err.message || err));
    } finally {
      this._phBusy = false;
    }
  }

  /** 打开大图查看器（可左右切换 5 路）。 */
  _openLightbox(curKey, curLbl, curUrl, urls, angles) {
    const lb = this.querySelector("#lightbox");
    if (!lb) return;
    // 只列出真正有图的方位
    const avail = angles.map(([k, l]) => {
      const hit = Object.entries(urls || {})
        .find(([kk]) => kk && kk.includes(`picIn${k}.jpg`));
      return hit ? [k, l, hit[1]] : null;
    }).filter(Boolean);
    if (!avail.length) return;

    const show = (idx) => {
      const [k, l, u] = avail[idx];
      const img = lb.querySelector("#lb-img");
      img.src = u;
      img.alt = `${l}视图`;
      lb.querySelector("#lb-title").textContent = `驻车照片 · ${l}`;
      lb.querySelectorAll("#lb-nav span").forEach((sp, i) =>
        sp.classList.toggle("on", i === idx));
      lb.dataset.idx = String(idx);
    };
    const nav = lb.querySelector("#lb-nav");
    nav.innerHTML = avail.map(([k, l], i) =>
      `<span data-i="${i}" role="button" tabindex="0">${l}</span>`).join("");
    nav.querySelectorAll("span").forEach((sp) => {
      sp.onclick = () => show(Number(sp.dataset.i));
    });

    const start = Math.max(0, avail.findIndex(([k]) => k === curKey));
    show(start);
    lb.classList.add("on");
    this._lbKeyHandler = (ev) => {
      if (ev.key === "Escape") { this._closeLightbox(); return; }
      const n = avail.length;
      const i = Number(lb.dataset.idx || 0);
      if (ev.key === "ArrowRight") show((i + 1) % n);
      if (ev.key === "ArrowLeft") show((i - 1 + n) % n);
    };
    document.addEventListener("keydown", this._lbKeyHandler);
    lb.querySelector("#lb-close").focus?.();
  }

  _closeLightbox() {
    const lb = this.querySelector("#lightbox");
    if (!lb) return;
    lb.classList.remove("on");
    lb.querySelector("#lb-img").src = "";   // 释放图片
    if (this._lbKeyHandler) {
      document.removeEventListener("keydown", this._lbKeyHandler);
      this._lbKeyHandler = null;
    }
  }

  /** 把 URL 填进对应方位；缺失的显示原因而不是假装有图。 */
  _paintPhotos(box, urls, angles, err) {
    const list = Object.entries(urls || {});
    angles.forEach(([key, lbl]) => {
      const cell = box.querySelector(`.ph[data-a="${key}"]`);
      if (!cell) return;
      const hit = list.find(([k]) => k && k.includes(`picIn${key}.jpg`));
      if (hit) {
        // ★ 图片可能已过期（实测 5 个月前的照片在 OSS 已 404，
        //   而签名 URL 本身仍有效）—— 加载失败要如实说明，不静默空白。
        cell.innerHTML = `<img src="${hit[1]}" alt="${lbl}视图" loading="lazy"
             style="width:100%;height:100%;object-fit:cover;border-radius:8px"
             onerror="this.parentNode.innerHTML='<div class=&quot;none&quot;>${lbl}视图<br>（图片已过期）</div><div class=&quot;lbl&quot;>${lbl}</div>'">
           <div class="lbl">${lbl}</div>
           <div class="zoom" aria-hidden="true">⤢</div>`;
        // 点缩略图 → 大图（URL 只在内存里，不落 DOM 属性）
        cell.onclick = () => this._openLightbox(key, lbl, hit[1], urls, angles);
        cell.setAttribute("role", "button");
        cell.setAttribute("tabindex", "0");
        cell.setAttribute("aria-label", `${lbl}视图，点击查看大图`);
      } else {
        const why = err ? "获取失败" : (list.length ? "该方位无图" : "尚未拍照");
        cell.innerHTML = `<div class="none">${lbl}视图<br>（${why}）</div>
           <div class="lbl">${lbl}</div>`;
      }
    });
  }

  // ── 自建地图：高德瓦片 ────────────────────────────────────────────────
  /** WGS84 → GCJ-02（大陆有 300~600m 偏移，不纠偏车标会跑偏）。 */
  _wgs2gcj(lat, lon) {
    const a = 6378245.0, ee = 0.00669342162296594323;
    const outOfChina = (la, lo) => lo < 72.004 || lo > 137.8347 || la < 0.8293 || la > 55.8271;
    if (outOfChina(lat, lon)) return [lat, lon];
    const tfLat = (x, y) => {
      let r = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
      r += (20*Math.sin(y*Math.PI) + 40*Math.sin(y/3*Math.PI)) * 2/3;
      r += (160*Math.sin(y/12*Math.PI) + 320*Math.sin(y*Math.PI/30)) * 2/3;
      return r;
    };
    const tfLon = (x, y) => {
      let r = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
      r += (20*Math.sin(x*Math.PI) + 40*Math.sin(x/3*Math.PI)) * 2/3;
      r += (150*Math.sin(x/12*Math.PI) + 300*Math.sin(x/30*Math.PI)) * 2/3;
      return r;
    };
    const dLat0 = tfLat(lon - 105, lat - 35), dLon0 = tfLon(lon - 105, lat - 35);
    const radLat = lat / 180 * Math.PI;
    let magic = Math.sin(radLat); magic = 1 - ee*magic*magic;
    const sqrtMagic = Math.sqrt(magic);
    const dLat = (dLat0 * 180) / ((a * (1 - ee)) / (magic * sqrtMagic) * Math.PI);
    const dLon = (dLon0 * 180) / (a / sqrtMagic * Math.cos(radLat) * Math.PI);
    return [lat + dLat, lon + dLon];
  }

  _lonlatToTile(lat, lon, z) {
    const n = 2 ** z;
    const x = (lon + 180) / 360 * n;
    const y = (1 - Math.log(Math.tan(lat * Math.PI/180) + 1/Math.cos(lat * Math.PI/180)) / Math.PI) / 2 * n;
    return [x, y];
  }

  _initMap(la, lo) {
    const box = this.querySelector("#tiles");
    const wrap = this.querySelector("#mapwrap");
    const puck = this.querySelector("#puck");
    if (!box || !wrap || la == null || lo == null) return;
    // WGS84 → GCJ-02
    const [glat, glon] = this._wgs2gcj(Number(la), Number(lo));
    this._map = this._map || { z: 16 };
    this._map.lat = glat; this._map.lon = glon;
    this.querySelector("#mapph").style.display = "none";

    this._drawMap();
    if (!box.dataset.wired) {
      box.dataset.wired = "1";
      // 拖拽平移
      let sx = 0, sy = 0, ox = 0, oy = 0, drag = false;
      const down = (e) => {
        drag = true; box.classList.add("grabbing");
        const p = e.touches ? e.touches[0] : e;
        sx = p.clientX; sy = p.clientY; ox = this._map.px || 0; oy = this._map.py || 0;
        e.preventDefault();
      };
      const move = (e) => {
        if (!drag) return;
        const p = e.touches ? e.touches[0] : e;
        this._map.px = ox + (sx - p.clientX);
        this._map.py = oy + (sy - p.clientY);
        this._positionTiles();
        e.preventDefault();
      };
      const up = () => { drag = false; box.classList.remove("grabbing"); };
      box.addEventListener("mousedown", down);
      box.addEventListener("touchstart", down, { passive: false });
      window.addEventListener("mousemove", move);
      window.addEventListener("touchmove", move, { passive: false });
      window.addEventListener("mouseup", up);
      window.addEventListener("touchend", up);
      // 双击放大
      box.addEventListener("dblclick", () => this._zoomMap(1));
    }
    // 缩放 / 回到车辆
    const wire = (sel, fn, label) => {
      const el = this.querySelector(sel);
      if (el && !el.dataset.w) { el.dataset.w = "1"; el.onclick = fn;
        this._a11y?.(el, label, fn); el.setAttribute("tabindex","0"); }
    };
    wire("#cz-in", () => this._zoomMap(1), "放大");
    wire("#cz-out", () => this._zoomMap(-1), "缩小");
    wire("#cz-me", () => { this._map.px = 0; this._map.py = 0; this._drawMap(); }, "回到车辆");
    puck.style.display = "";
  }

  _zoomMap(delta) {
    if (!this._map) return;
    const z = Math.max(3, Math.min(18, this._map.z + delta));
    if (z === this._map.z) return;
    // 缩放时保持车辆在视野中心
    this._map.z = z; this._map.px = 0; this._map.py = 0;
    this._drawMap();
  }

  /** 按当前缩放/偏移算出需要的瓦片并放置。 */
  /** ★★ 2026-10-11 修复：这个方法此前【只有调用、没有定义】（第 562 行
   *  `this._positionTiles()`）→ 拖动地图立刻抛
   *  `TypeError: this._positionTiles is not a function`（真机 frontend 日志实证）。
   *
   *  职责：**只重新定位已有瓦片**（不创建/删除）。
   *  拖动时只需平移，用这个比重建 `_drawMap()` 快得多、也不闪。
   *  瓦片范围变化（缩放/大跳）才走 `_drawMap()`。
   *
   *  定位算式与 `_drawMap` 同源（都来自瓦片坐标系的小数坐标）：
   *    left = 车辆在容器中的像素位置 - 车辆所在瓦片内的偏移 + (瓦片整数坐标 - 中心瓦片) * 256
   */
  _positionTiles() {
    const box = this.querySelector("#tiles");
    const wrap = this.querySelector("#mapwrap");
    if (!box || !wrap || !this._map) return;
    const W = wrap.clientWidth || 400, H = wrap.clientHeight || 340;
    const z = this._map.z;
    const [cxExact, cyExact] = this._lonlatToTile(this._map.lat, this._map.lon, z);
    const cxInt = Math.floor(cxExact), cyInt = Math.floor(cyExact);
    const offX = (cxExact - cxInt) * 256;
    const offY = (cyExact - cyInt) * 256;
    const px = this._map.px || 0, py = this._map.py || 0;
    const cpx = W / 2 + px, cpy = H / 2 + py;
    box.querySelectorAll("img[data-k]").forEach((im) => {
      const parts = String(im.dataset.k || "").split("_");
      if (parts.length !== 2) return;
      const tx = Number(parts[0]), ty = Number(parts[1]);
      if (!Number.isFinite(tx) || !Number.isFinite(ty)) return;
      im.style.left = Math.round(cpx - offX + (tx - cxInt) * 256) + "px";
      im.style.top = Math.round(cpy - offY + (ty - cyInt) * 256) + "px";
    });
  }

  _drawMap() {
    const box = this.querySelector("#tiles");
    const wrap = this.querySelector("#mapwrap");
    if (!box || !wrap || !this._map) return;
    const W = wrap.clientWidth || 400, H = wrap.clientHeight || 340;
    const z = this._map.z;
    // ★ 关键：cx/cy 是【瓦片坐标系里的小数】(如 27394.7)。
    //   车辆中心与该点的像素差 = (cx - cxInt) * 256。
    //   之前写成 cpx - (cx - tx) * 256 —— 把整个 cx（两万多）当像素用了，
    //   结果 left = -1400 万 px，瓦片全跑到屏幕外（这就是"看不到地图"的原因）。
    const [cxExact, cyExact] = this._lonlatToTile(this._map.lat, this._map.lon, z);
    const cxInt = Math.floor(cxExact), cyInt = Math.floor(cyExact);
    const offX = (cxExact - cxInt) * 256;   // 车辆在中心瓦片内的像素偏移
    const offY = (cyExact - cyInt) * 256;
    const px = this._map.px || 0, py = this._map.py || 0;
    const cpx = W / 2 + px, cpy = H / 2 + py;   // 车辆在容器里的像素位置
    // 需要覆盖的瓦片范围（以中心瓦片为基准向外扩）
    const x0 = cxInt - Math.ceil((cpx - offX) / 256);
    const x1 = cxInt + Math.ceil((W - cpx + offX) / 256);
    const y0 = cyInt - Math.ceil((cpy - offY) / 256);
    const y1 = cyInt + Math.ceil((H - cpy + offY) / 256);
    const n = 2 ** z;
    const frag = [];
    for (let tx = x0; tx <= x1; tx++) {
      for (let ty = y0; ty <= y1; ty++) {
        if (tx < 0 || ty < 0 || tx >= n || ty >= n) continue;
        // 该瓦片左上角在容器中的位置
        const left = cpx - offX + (tx - cxInt) * 256;
        const top = cpy - offY + (ty - cyInt) * 256;
        const s = (tx + ty) % 4 + 1;   // 高德 1..4 轮询
        const url = `https://webrd0${s}.is.autonavi.com/appmaptile`
                  + `?lang=zh_cn&size=1&scale=1&style=8&x=${tx}&y=${ty}&z=${z}`;
        frag.push(`<img data-k="${tx}_${ty}" src="${url}"`
                + ` style="left:${Math.round(left)}px;top:${Math.round(top)}px">`);
      }
    }
    // 复用已有瓦片节点（减少闪烁）
    const existing = new Map();
    box.querySelectorAll("img").forEach((im) => existing.set(im.dataset.k, im));
    const added = [];
    for (const f of frag) {
      const k = /data-k="([^"]+)"/.exec(f)[1];
      const im = existing.get(k);
      if (im) {
        const st = /left:(-?\d+)px;top:(-?\d+)px/.exec(f);
        im.style.left = st[1] + "px"; im.style.top = st[2] + "px";
        existing.delete(k);
      } else {
        added.push(f);
      }
    }
    existing.forEach((im) => im.remove());
    if (added.length) box.insertAdjacentHTML("beforeend", added.join(""));
    // 车辆标记固定在中心
    const puck = this.querySelector("#puck");
    if (puck) { puck.style.left = (W/2 + px) + "px"; puck.style.top = (H/2 + py) + "px"; }
  }

  _haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000, toRad = (x) => x * Math.PI / 180;
    const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat/2)**2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangLocationPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "车辆位置（二级页）",
  description: "地图定位 + 地址 + 距离 + 闪灯/鸣笛 + 驻车照片入口",
  preview: true,
});
})();

/* ===================== lixiang-task-page.js ===================== */
(function () {

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


/**
 * lixiang-task-page —— 车控任务（对齐 App「任务大师」，但落地为 HA 自动化）
 *
 * 背景：
 *   App 的「任务大师」是【云端规则引擎】—— 规则存理想服务器，
 *   集成没有对应 API，无法读写。
 *
 * 但 App 的模型 = IFTTT = HA automation：
 *   任务名称  → alias
 *   如果      → trigger
 *   就执行    → action
 *
 * 本卡片用【同样的交互】创建 **HA 自动化**，效果等价甚至更强：
 *   · 本地执行（不依赖网络，更快）
 *   · 可联动其他品牌设备
 *   · 可发通知 / 调脚本
 *
 * 写入 API：POST /api/config/automation/config/{id}
 */

/* ★ 条件/动作分类的中文名（服务端只给英文 classification） */
const _DICT_CLS_LABEL = {
  ConditionTimes:"时间", ConditionEnvironments:"环境", ConditionLocations:"位置",
  ConditionNavigations:"导航", ConditionPassengers:"乘员", ConditionSittingPositions:"坐姿",
  ConditionDrivings:"驾驶", ConditionPowerStatus:"充电供电", ConditionDoorsAndWindows:"门窗",
  ConditionBelts:"安全带", ConditionLights:"灯光", ConditionVolumes:"音量",
  ConditionApplications:"应用", ConditionModes:"模式", ConditionAccessories:"配件",
  ActionDelays:"延时", ActionAirs:"空调", ActionSeatAirs:"座椅通风", ActionSeatHeats:"座椅加热",
  ActionSeatMassages:"座椅按摩", ActionSittingPositions:"座椅位置", ActionDrivings:"驾驶",
  ActionDoorsAndWindows:"门窗", ActionLights:"灯光", ActionScreenShows:"屏幕",
  ActionVolumes:"音量", ActionNavigations:"导航", ActionBluetooths:"蓝牙",
  ActionApplications:"应用", ActionModes:"模式", ActionLiStudents:"学习",
  ActionAccessories:"配件",
};
/* ★ 常用条目的中文名（未列出的直接显示英文 type，不猜） */
const _DICT_ITEM_LABEL = {
  Gear:"挡位", Speed:"车速", Lock:"车锁", BatteryRemaining:"剩余电量",
  InsideTemperature:"车内温度", OutsideTemperature:"车外温度", TimeRange:"时间段",
  Sunrise:"日出", Sunset:"日落", Time:"定时", InRange:"在位置范围内", OutRange:"在位置范围外",
  LeftFDoor:"主驾车门", RightFDoor:"副驾车门", TailDoor:"尾门",
  LeftFWindow:"主驾车窗", RightFWindow:"副驾车窗", LeftRWindow:"左后车窗", RightRWindow:"右后车窗",
  DriverBelt:"主驾安全带", CopilotBelt:"副驾安全带",
  ChargingStatus:"充电状态", ChargingGunStatus:"充电枪",
  MusicPlaying:"音乐播放", MediaVolume:"媒体音量",
  Driver:"主驾", Copilot:"副驾", SecondLeft:"二排左", SecondRight:"二排右", SecondMid:"二排中",
  GetOnCar:"上车", GetOffCar:"下车",
  ACSwitch:"空调开关", Defog:"除雾", AirPurification:"空气净化",
  DriverHeating:"主驾加热", SecondLHeating:"二排左加热",
  DriverAir:"主驾通风", SeatHeating_:"座椅加热",
  Headlights:"大灯", AllDoorsLock:"全车落锁", AutoUnlock:"自动解锁",
  Delay:"延时", OpenApp:"打开应用", BackHome:"回家",
};

const CARD_TAG = "lixiang-task-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

/* ── 车控常用模板（对应 App 社区的常见任务）──
 * entity_id: null 的占位符在卡片运行时用自动发现结果填充 */
function buildPresets(card) {
  const eid = (f) => card._eid(f);
  return PRESET_DEFS.map((p) => {
    const t = Object.assign({}, p.trigger);
    if (!t.entity_id) {
      t.entity_id = eid(t._field
        || (t.platform === "numeric_state" && t.below != null ? "battery"
            : (t.above != null ? "room_temp" : "status")));
    }
    delete t._field;
    const action = p.action.map((a) => {
      const b = JSON.parse(JSON.stringify(a));
      if (b.target && b.target.entity_id === null) b.target.entity_id = eid(p.actionField || "ac");
      return b;
    }).filter((a) => !(a.target && !a.target.entity_id));
    return Object.assign({}, p, { trigger: t, action });
  }).filter((p) => p.trigger.entity_id && p.action.length);
}
const PRESET_DEFS = [
  { name: "无人关闭通风", icon: "ic_home_fan_on.webp", color: "#34C759", actionField: "ac",
    desc: "离车后自动关闭空调通风",
    trigger: { platform: "state", entity_id: null, to: "已驻车（P 档）", for: "00:05:00" },
    action: [{ service: "climate.turn_off", target: { entity_id: null } }] },
  { name: "有人自动通风", icon: "ic_home_fan_on.webp", color: "#34C759", actionField: "ac",
    desc: "车内温度过高时开启空调",
    trigger: { platform: "numeric_state", entity_id: null, above: 30 },
    action: [{ service: "climate.turn_on", target: { entity_id: null } }] },
  { name: "离车关遮阳帘防晒", icon: "ic_home_control.webp", color: "#0A58F6", actionField: "sunshade",
    desc: "锁车后关闭遮阳帘",
    trigger: { platform: "state", entity_id: null, to: "locked", _field: "lock" },
    action: [{ service: "cover.close_cover", target: { entity_id: null } }] },
  { name: "低电量提醒", icon: "ic_home_battery.webp", color: "#FF9500", actionField: "sentry",
    desc: "电量低于 20% 时发通知",
    trigger: { platform: "numeric_state", entity_id: null, below: 20 },
    action: [{ service: "persistent_notification.create",
               data: { title: "理想 L6 电量偏低", message: "建议尽快充电" } }] },
  { name: "哨兵模式自动开启", icon: "ic_home_sentry.png", color: "#FF3B30", actionField: "ac",
    desc: "驻车 10 分钟后开启哨兵",
    trigger: { platform: "state", entity_id: null, to: "已驻车（P 档）", for: "00:10:00", _field: "status" },
    action: [{ service: "switch.turn_on", target: { entity_id: null } }] },
  { name: "长途驾驶疲劳缓解", icon: "ic_home_control.webp", color: "#FF9500", actionField: "ac",
    desc: "连续驾驶 2 小时后提醒休息",
    trigger: { platform: "state", entity_id: null, to: "行驶中", for: "02:00:00", _field: "status" },
    action: [{ service: "persistent_notification.create",
               data: { title: "该休息了", message: "已连续驾驶 2 小时" } }] },
];

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  lixiang-task-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-task-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; position:relative; }
  .back { width:34px; height:34px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center; cursor:pointer; }
  .back img { width:18px; height:18px; opacity:.7; }
  .topbar h1 { position:absolute; left:0; right:0; text-align:center;
               font-size:18px; font-weight:500; margin:0; pointer-events:none; }
  .help { margin-left:auto; font-size:15px; color:var(--lx-t2); cursor:pointer;
          padding:6px 8px; position:relative; z-index:2; }

  /* Tabs */
  .tabs { display:flex; gap:26px; padding:6px 20px 0; border-bottom:1px solid var(--lx-line); }
  .tab { font-size:15.5px; color:var(--lx-t2); padding:10px 0 12px; cursor:pointer;
         position:relative; }
  .tab.on { color:var(--lx-t1); font-weight:500; }
  .tab.on::after { content:""; position:absolute; left:0; right:0; bottom:-1px;
                   height:2.5px; background:var(--lx-blue); border-radius:2px; }

  .sorts { display:flex; gap:20px; padding:16px 20px 6px; }
  .sort { font-size:14.5px; color:var(--lx-t3); cursor:pointer; }
  .sort.on { color:var(--lx-t1); font-weight:500; }

  /* 任务卡列表 */
  .list { padding:6px 16px 0; }
  .item { display:flex; align-items:center; gap:13px; background:var(--lx-card);
          border-radius:16px; padding:15px 16px; margin-bottom:10px; cursor:pointer;
          transition:transform .13s; }
  .item:active { transform:scale(.985); }
  .item .ic { width:38px; height:38px; border-radius:11px; display:flex;
              align-items:center; justify-content:center; flex:0 0 auto; }
  .item .ic img { width:21px; height:21px; }
  .item .tx { flex:1; min-width:0; }
  .item .n { font-size:16px; display:flex; align-items:center; gap:7px; }
  .item .n .new { font-size:10px; background:var(--lx-blue); color:#fff;
                  padding:2px 6px; border-radius:5px; font-weight:500; }
  .item .a { font-size:12.5px; color:var(--lx-t3); margin-top:5px; }
  .item .ar { color:var(--lx-t3); font-size:17px; flex:0 0 auto; }
  .item.on .n { color:var(--lx-blue); }

  /* 创建区 */
  .create { margin:18px 16px 0; }
  .field { background:var(--lx-card); border-radius:18px; padding:16px;
           margin-bottom:14px; }
  .field .lbl { font-size:15px; font-weight:500; margin-bottom:4px; }
  .field .hint { font-size:12.5px; color:var(--lx-t3); line-height:1.55;
                 margin-bottom:12px; }
  .nameinput { width:100%; border:none; background:transparent; font-size:16px;
               color:var(--lx-t1); outline:none; font-family:inherit;
               padding:10px 0; }
  .nameinput::placeholder { color:#C7C7CC; }
  .addbox { border:1.5px dashed var(--lx-line); border-radius:14px; padding:22px;
            display:flex; flex-direction:column; align-items:center; gap:6px;
            cursor:pointer; color:var(--lx-t2); }
  .addbox .p { font-size:26px; line-height:1; font-weight:300; }
  .addbox .t { font-size:14.5px; }
  .chips { display:flex; flex-direction:column; gap:8px; }
  .chip { background:var(--lx-bg); border-radius:12px; padding:12px 14px;
          font-size:13.5px; display:flex; align-items:center; gap:9px; }
  .chip .x { margin-left:auto; color:var(--lx-t3); cursor:pointer; padding:0 4px;
             font-size:16px; }
  .confirm { text-align:center; border-radius:26px; padding:15px; font-size:16px;
             background:#1A1A1A; color:#fff; cursor:pointer; transition:opacity .2s; }
  .confirm.dis { background:#E5E5EA; color:#AEAEB2; cursor:not-allowed; }
  .confirm:not(.dis):active { transform:scale(.985); }

  /* 底部固定 */
  .bottom { display:flex; align-items:center; gap:12px; margin:18px 16px 0; }
  .share { font-size:14.5px; color:var(--lx-t2); cursor:pointer; }
  .mk { flex:1; text-align:center; background:#1A1A1A; color:#fff;
        border-radius:24px; padding:14px; font-size:15px; cursor:pointer; }

  .empty { text-align:center; color:var(--lx-t3); font-size:13px; padding:30px 0; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:82%; text-align:center; line-height:1.5; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangTaskPage extends HTMLElement {
  setConfig(c) {
    this._config = c || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base; this._tab = "discover"; this._sort = "rec";
    this._mine = []; this._draft = null; this._built = false;
  }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 20; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try { const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) {}
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }
  _eid(f) {
    const m = (this._config || {})[f];
    if (typeof m === "string" && m.includes(".")) return m;
    return (this._autoBind() || {})[f] || null;
  }
  // ★ 2026-10-11 新增：读实体状态（其他页面都有；此前本页缺它，
  //   新加的触发条件过滤调用后会抛 TypeError → 被 test_frontend_bindings 抓到）
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }


  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role","button"); el.setAttribute("tabindex","0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handler(e); }
    });
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    root.innerHTML = `
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <h1>任务大师</h1>
        <div class="help" id="help" role="button" tabindex="0" aria-label="帮助">帮助</div>
      </div>

      <div class="tabs">
        <div class="tab on" data-tab="discover" role="button" tabindex="0">发现</div>
        <div class="tab" data-tab="mine" role="button" tabindex="0">我的任务</div>
        <div class="tab" data-tab="create" role="button" tabindex="0">创建任务</div>
      </div>

      <div id="body"></div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    const help = () => this._toast(
      "App 的「任务大师」规则存在理想云端，集成无法读写。本页创建的是 HA 自动化" +
      "（本地执行，可联动其他设备），效果等价。", null, 5200);
    this._a11y(this.querySelector("#help"), "帮助", help);
    this.querySelector("#help").addEventListener("click", help);

    this.querySelectorAll(".tab").forEach(t => {
      const act = () => { this._tab = t.dataset.tab; this._render(); };
      this._a11y(t, t.textContent, act);
      t.addEventListener("click", act);
    });

    this._built = true;
  }

  /** 模板（延迟构造：实体由自动发现提供） */
  _presets() {
    if (!this._presetCache) this._presetCache = buildPresets(this);
    return this._presetCache;
  }

  _toast(msg, kind, ms) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, ms || 2600);
  }

  /** 我的任务：枚举 automation 实体（由本卡片创建的） */
  _myTasks() {
    const out = [];
    const h = this._hass; if (!h) return out;
    for (const id of Object.keys(h.states)) {
      if (!id.startsWith("automation.")) continue;
      const s = h.states[id];
      const a = s.attributes || {};
      const isMine = (a.id && String(a.id).startsWith("lx_"))
        || /理想|车辆|车控|哨兵|充电|座椅|空调/.test(a.friendly_name || "");
      if (isMine) out.push({ id, eid: id, alias: a.friendly_name || id,
                             on: s.state === "on", last: a.last_triggered });
    }
    return out;
  }

  _render() {
    const box = this.querySelector("#body");
    this.querySelectorAll(".tab").forEach(t =>
      t.className = "tab" + (t.dataset.tab === this._tab ? " on" : ""));

    if (this._tab === "discover") { box.innerHTML = this._discoverHtml(); this._bindDiscover(); }
    else if (this._tab === "mine") { box.innerHTML = this._mineHtml(); this._bindMine(); }
    else { box.innerHTML = this._createHtml(); this._bindCreate(); }
  }

  /* ── 发现（模板库）── */
  _discoverHtml() {
    return `
      <div class="sorts">
        <span class="sort on" data-s="rec">推荐</span>
        <span class="sort" data-s="hot">最热</span>
        <span class="sort" data-s="new">飙升</span>
      </div>
      <div class="list">
        ${this._presets().map((p, i) => `
          <div class="item" data-i="${i}">
            <div class="ic" style="background:${p.color}22">
              <img src="${__iconBase}/${p.icon}" alt="" onerror="this.style.visibility='hidden'"></div>
            <div class="tx">
              <div class="n">${p.name}<span class="new">NEW</span></div>
              <div class="a">${p.desc}</div>
            </div>
            <div class="ar">›</div>
          </div>`).join("")}
      </div>
      <div class="bottom">
        <span class="share" id="share" role="button" tabindex="0">分享码添加</span>
        <div class="mk" id="mk" role="button" tabindex="0">创建任务</div>
      </div>`;
  }

  _bindDiscover() {
    this.querySelectorAll(".sort").forEach(s => {
      const act = () => {
        this._sort = s.dataset.s;
        this.querySelectorAll(".sort").forEach(x =>
          x.className = "sort" + (x.dataset.s === this._sort ? " on" : ""));
      };
      this._a11y(s, s.textContent, act);
      s.addEventListener("click", act);
    });
    this.querySelectorAll(".item").forEach(it => {
      const p = this._presets()[Number(it.dataset.i)];
      const act = () => this._applyPreset(p);
      this._a11y(it, p.name, act);
      it.addEventListener("click", act);
    });
    const mk = this.querySelector("#mk");
    if (mk) { const a = () => { this._tab = "create"; this._render(); };
      this._a11y(mk, "创建任务", a); mk.addEventListener("click", a); }
    const sh = this.querySelector("#share");
    if (sh) { const a = () => this._toast("分享码需在理想 App 内使用（云端功能）");
      this._a11y(sh, "分享码添加", a); sh.addEventListener("click", a); }
  }

  /* ── 我的任务 ── */
  _mineHtml() {
    const list = this._myTasks();
    if (!list.length) {
      return `<div class="empty">还没有任务<br>
        <span style="font-size:12px">到「发现」里选一个模板，或自己创建</span></div>
        <div class="bottom"><div class="mk" id="mk2" role="button" tabindex="0">创建任务</div></div>`;
    }
    return `<div class="list">${list.map(t => `
      <div class="item${t.on ? " on" : ""}" data-eid="${t.eid}">
        <div class="ic" style="background:${t.on ? "#0A58F622" : "#8E8E9322"}">
          <img src="${__iconBase}/ic_home_control.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <div class="tx">
          <div class="n">${t.alias}</div>
          <div class="a">${t.on ? "已启用" : "已停用"}${t.last ? " · 上次 " + String(t.last).slice(0, 16) : ""}</div>
        </div>
        <div class="ar">›</div>
      </div>`).join("")}</div>
      <div class="bottom"><div class="mk" id="mk3" role="button" tabindex="0">创建任务</div></div>`;
  }

  _bindMine() {
    this.querySelectorAll(".item").forEach(it => {
      const eid = it.dataset.eid;
      const act = async () => {
        try {
          await this._hass.callService("automation", this._hass.states[eid].state === "on" ? "turn_off" : "turn_on",
            { entity_id: eid });
          this._toast("已切换", "ok"); this._render();
        } catch (e) { this._toast("操作失败", "err"); }
      };
      this._a11y(it, it.querySelector(".n").textContent, act);
      it.addEventListener("click", act);
    });
    const mk = this.querySelector("#mk2") || this.querySelector("#mk3");
    if (mk) { const a = () => { this._tab = "create"; this._render(); };
      this._a11y(mk, "创建任务", a); mk.addEventListener("click", a); }
  }

  /* ── 创建 ── */
  _createHtml() {
    const d = this._draft;
    const trg = d && d.trigger ? `<div class="chips"><div class="chip">
        <span>${this._describeTrigger(d.trigger)}</span>
        <span class="x" data-del="t">×</span></div></div>` : "";
    const act = d && d.action && d.action.length ? `<div class="chips">
        ${d.action.map((a, i) => `<div class="chip">
          <span>${this._describeAction(a)}</span>
          <span class="x" data-del="a" data-i="${i}">×</span></div>`).join("")}</div>` : "";
    const canConfirm = !!(d && d.name && d.action && d.action.length);
    return `
      <div class="create">
        <div class="field">
          <input class="nameinput" id="tname" placeholder="任务名称"
            value="${d && d.name ? d.name : ""}" aria-label="任务名称">
        </div>
        <div class="field">
          <div class="lbl">如果</div>
          <div class="hint">发生以下情况时，任务将自动运行。不添加时，任务将手动运行</div>
          ${trg || `<div class="addbox" id="addtrg" role="button" tabindex="0">
            <div class="p">＋</div><div class="t">添加</div></div>`}
        </div>
        <div class="field">
          <div class="lbl">就执行</div>
          <div class="hint">执行哪些操作？</div>
          ${act || `<div class="addbox" id="addact" role="button" tabindex="0">
            <div class="p">＋</div><div class="t">添加</div></div>`}
        </div>
        <div class="confirm${canConfirm ? "" : " dis"}" id="confirm"
          role="button" tabindex="0">确定</div>
      </div>`;
  }

  _bindCreate() {
    if (!this._draft) this._draft = { name: "", trigger: null, action: [] };
    const nm = this.querySelector("#tname");
    if (nm) nm.addEventListener("input", (e) => { this._draft.name = e.target.value; });

    const at = this.querySelector("#addtrg");
    if (at) { const a = () => this._pickTrigger();
      this._a11y(at, "添加触发条件", a); at.addEventListener("click", a); }
    const aa = this.querySelector("#addact");
    if (aa) { const a = () => this._pickAction();
      this._a11y(aa, "添加操作", a); aa.addEventListener("click", a); }

    this.querySelectorAll("[data-del]").forEach(x => {
      const a = () => {
        if (x.dataset.del === "t") this._draft.trigger = null;
        else this._draft.action.splice(Number(x.dataset.i), 1);
        this._render();
      };
      this._a11y(x, "删除", a); x.addEventListener("click", a);
    });

    const cf = this.querySelector("#confirm");
    if (cf) {
      const a = () => {
        if (cf.className.includes("dis")) {
          this._toast("请填写任务名称并至少添加一个操作", "err"); return;
        }
        this._save();
      };
      this._a11y(cf, "确定", a); cf.addEventListener("click", a);
    }
  }

  _describeTrigger(t) {
    if (t.platform === "state") {
      const s = this._hass && this._hass.states[t.entity_id];
      const nm = s ? (s.attributes.friendly_name || t.entity_id) : t.entity_id;
      return `${nm} 变为「${t.to}」${t.for ? " 持续 " + this._forText(t.for) : ""}`;
    }
    if (t.platform === "numeric_state") {
      const s = this._hass && this._hass.states[t.entity_id];
      const nm = s ? (s.attributes.friendly_name || t.entity_id) : t.entity_id;
      const cmp = t.above != null ? `高于 ${t.above}` : `低于 ${t.below}`;
      return `${nm} ${cmp}`;
    }
    if (t.platform === "time") return `每天 ${t.at}`;
    return JSON.stringify(t).slice(0, 40);
  }
  _forText(f) {
    const m = String(f).match(/(\d+):(\d+):(\d+)/);
    if (!m) return f;
    const h = +m[1], mi = +m[2];
    return h ? `${h} 小时` : `${mi} 分钟`;
  }
  _describeAction(a) {
    const svc = a.service || "";
    const tgt = (a.target && a.target.entity_id) || (a.data && a.data.entity_id) || "";
    const s = this._hass && this._hass.states[tgt];
    const nm = s ? (s.attributes.friendly_name || tgt) : tgt;
    const MAP = { "climate.turn_on": "开启空调", "climate.turn_off": "关闭空调",
      "switch.turn_on": "开启", "switch.turn_off": "关闭",
      "cover.close_cover": "关闭", "cover.open_cover": "打开",
      "lock.lock": "上锁", "lock.unlock": "解锁",
      "persistent_notification.create": "发送通知" };
    return `${svc} ${MAP[svc] ? "（" + MAP[svc] + "）" : ""} ${nm}`.trim();
  }

  /** 触发条件选择（简化为常用几项） */
  async _pickTrigger() {
    // ★ 优先用服务端字典（86 条件 + 参数模板）；取不到则回退下面的简表
    if (await this._ensureDict()) {
      const r = await this._pickFromDict("选择触发条件", "conditions");
      if (r) { this._draft.trigger = { platform: "state", entity_id: this._eid("status"), to: r.type, params: r.payload }; }
      return;
    }
    const OPTS = [
      { label: "驻车后", t: { platform: "state", entity_id: this._eid("status"), to: "已驻车（P 档）", for: "00:05:00" } },
      { label: "开始行驶", t: { platform: "state", entity_id: this._eid("status"), to: "行驶中" } },
      { label: "车辆上锁", t: { platform: "state", entity_id: this._eid("lock"), to: "locked" } },
      { label: "电量低于 20%", t: { platform: "numeric_state", entity_id: this._eid("battery"), below: 20 } },
      { label: "车内温度高于 30°C", t: { platform: "numeric_state", entity_id: this._eid("room_temp"), above: 30 } },
      // ★ 2026-10-11 与动作列表一致地过滤：实体不存在就别给这个选项，
      //   否则用户选了 → 任务创建失败（服务端找不到该 entity_id）
    ].filter(o => o.t && o.t.entity_id && this._st(o.t.entity_id));
    if (!OPTS.length) { this._toast("这台车暂无可用触发条件（缺少状态实体）", "err"); return; }
    const pick = await this._choose("选择触发条件", OPTS.map(o => o.label));
    if (pick == null) return;
    this._draft.trigger = OPTS[pick].t;
    this._render();
  }

  async _pickAction() {
    if (await this._ensureDict()) {
      const r = await this._pickFromDict("选择操作", "actions");
      if (r) this._draft.action.push(r.payload);
      return;
    }
    const act = this._eid("ac"), lock = this._eid("lock"), sentry = this._eid("sentry");
    const OPTS = [
      { label: "开启空调", a: act ? { service: "climate.turn_on", target: { entity_id: act } } : null },
      { label: "关闭空调", a: act ? { service: "climate.turn_off", target: { entity_id: act } } : null },
      { label: "开启哨兵模式", a: sentry ? { service: "switch.turn_on", target: { entity_id: sentry } } : null },
      { label: "关闭哨兵模式", a: sentry ? { service: "switch.turn_off", target: { entity_id: sentry } } : null },
      { label: "车辆上锁", a: lock ? { service: "lock.lock", target: { entity_id: lock } } : null },
      { label: "发送通知", a: { service: "persistent_notification.create",
          data: { title: "理想 L6", message: "任务已触发" } } },
    ].filter(o => o.a);
    const pick = await this._choose("选择操作", OPTS.map(o => o.label));
    if (pick == null) return;
    this._draft.action.push(OPTS[pick].a);
    this._render();
  }

  /** 轻量选择器（替代 window.prompt —— 后者在 HA 里体验差） */
  /**
   * 拉取字典（一次即可，缓存在实例上）。
   * ★ 取不到时静默返回 false —— 调用方回退到旧的硬编码简表，
   *   **不让用户看到一个空的"添加条件"表单**（那会像坏了）。
   */
  async _ensureDict() {
    if (this._dictCache) return true;
    if (this._dictTried) return false;          // 本次会话已试过，不重复打
    this._dictTried = true;
    try {
      const res = await fetch("/lixiang_auto/task-dict.json");
      const j = await res.json();
      if (j && j.ok && Array.isArray(j.conditions) && j.conditions.length) {
        this._dictCache = j;
        return true;
      }
    } catch (e) {
      // 忽略：回退旧简表
    }
    return false;
  }

  /**
   * ★ 2026-10-11 字典驱动：从服务端下发的 condition-and-action 字典构建条件/动作列表。
   *   取不到时返回 null（调用方回退到旧的硬编码简表，不让用户看到空表单）。
   *   字典结构（见 task_dict.py）：classification → items[{type,source,params[]}]
   */
  _dict(kind) {
    // ★ 卡片拿不到 coordinator → 字典经 REST 视图暴露（/lixiang_auto/task-dict.json）
    const d = this._dictCache || null;
    if (!d) return null;
    const groups = d[kind] || [];
    if (!groups.length) return null;
    return groups.map(g => ({
      cls: g.classification,
      label: _DICT_CLS_LABEL[g.classification] || g.classification,
      items: (g.items || []).map(it => ({
        type: it.type,
        label: _DICT_ITEM_LABEL[it.type] || it.type,
        source: it.source,
        params: it.params || [],
      })),
    })).filter(g => g.items.length);
  }

  /** 该条目是否需要参数表单（没有 params 就是选完即用）。 */
  static _needsForm(item) { return Array.isArray(item.params) && item.params.length > 0; }

  /**
   * 两级选择：先选分类，再选条目；带参数的在第二步后追加参数表单。
   * @returns {Promise<null | {type:string, t:object, a:object}>}
   */
  _pickFromDict(title, kind, typeKey) {
    const groups = this._dict(kind);
    if (!groups) return Promise.resolve(null);
    return (async () => {
      // ① 选分类
      const gi = await this._choose(title, groups.map(g => g.label));
      if (gi == null) return null;
      const g = groups[gi];
      // ② 选条目
      const ii = await this._choose(g.label, g.items.map(i => i.label));
      if (ii == null) return null;
      const item = g.items[ii];
      // ③ 需要参数 → 生成表单
      let vals = {};
      if (item.params.length) {
        vals = await this._fillParams(item);
        if (vals === null) return null;          // 用户取消
      }
      const body = {};
      for (const [k, v] of Object.entries(vals)) body[k] = v;
      return { type: item.type, payload: body, source: item.source,
               text: `${g.label} · ${item.label}` };
    })();
  }

  /**
   * 按参数模板生成表单。
   * ★ 支持的控件类型（来自实测字典）：
   *   singleChoiceList / multiChoiceList → 单选/多选按钮组
   *   singleColumnSelector            → 数值选择（滚轮/滑杆）
   *   默认（无 value）→ 文本输入
   * 未知类型不猜：退回文本输入并保留原始 key（服务端仍可能接受）。
   */
  _fillParams(item) {
    return new Promise((resolve) => {
      const ov = document.createElement("div");
      ov.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:21;
        display:flex;align-items:flex-end;justify-content:center;`;
      const sheet = document.createElement("div");
      sheet.style.cssText = `background:var(--lx-bg);color:var(--lx-t1);width:100%;
        max-width:460px;border-radius:20px 20px 0 0;padding:16px 0 24px;
        font-family:inherit;max-height:78vh;overflow:auto;`;
      const vals = {};
      const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
      const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ESC_MAP[c]);

      const rows = item.params.map((p, i) => {
        const key = p.key;
        const label = p.label || key;
        const type = p.type || "";
        const opts = Array.isArray(p.value) ? p.value : null;
        if (type.includes("ChoiceList") && opts) {
          // 单选按钮组（多选暂按单选，取第一个匹配 —— ★ 不猜多选语义）
          const multi = type.includes("multi");
          vals[key] = p.defaultValue != null ? p.defaultValue
                    : (multi && Array.isArray(p.defaultValue) ? p.defaultValue[0] : opts[0]);
          return `<div style="padding:10px 20px">
            <div style="font-size:12.5px;color:var(--lx-t3);margin-bottom:7px">${esc(label)}</div>
            <div data-p="${i}" data-key="${esc(key)}" data-multi="${multi}"
                 style="display:flex;flex-wrap:wrap;gap:7px">
              ${opts.map(o => `<span data-v="${esc(o)}" style="padding:6px 12px;border-radius:9px;
                 font-size:13px;border:1px solid var(--lx-line);cursor:pointer">${esc(o)}</span>`).join("")}
            </div></div>`;
        }
        if (type === "singleColumnSelector" && opts) {
          // 数值：默认取 defaultValue（找不到则取中间值）
          let init = p.defaultValue;
          const hit = opts.some((n) => String(n) === String(init));
          if (init == null || !hit) init = opts[Math.floor(opts.length / 2)];
          vals[key] = init;
          return `<div style="padding:10px 20px">
            <div style="font-size:12.5px;color:var(--lx-t3);margin-bottom:7px">${esc(label)}</div>
            <input data-p="${i}" data-key="${esc(key)}" data-kind="num"
              value="${esc(init)}" inputmode="decimal"
              style="width:100%;padding:11px 12px;border-radius:10px;font-size:15px;
                     border:1px solid var(--lx-line);background:var(--lx-card);color:var(--lx-t1)">
            <div style="font-size:11px;color:var(--lx-t3);margin-top:5px">可选：${esc(opts[0])} ~ ${esc(opts[opts.length-1])}</div>
          </div>`;
        }
        // 兜底：文本输入（不猜语义，保留原始 key）
        vals[key] = p.defaultValue != null ? p.defaultValue : "";
        return `<div style="padding:10px 20px">
          <div style="font-size:12.5px;color:var(--lx-t3);margin-bottom:7px">${esc(label)}</div>
          <input data-p="${i}" data-key="${esc(key)}" data-kind="txt" value="${esc(vals[key])}"
            style="width:100%;padding:11px 12px;border-radius:10px;font-size:15px;
                   border:1px solid var(--lx-line);background:var(--lx-card);color:var(--lx-t1)">
        </div>`;
      }).join("");

      sheet.innerHTML = `<div style="font-size:16px;font-weight:500;padding:0 20px 6px">${esc(item.label)}</div>
        ${rows}
        <div style="display:flex;gap:10px;padding:14px 20px 0">
          <div id="ok" style="flex:1;text-align:center;padding:13px 0;border-radius:12px;
               background:var(--lx-blue);color:#fff;font-size:15px;cursor:pointer">确定</div>
          <div id="cx" style="flex:1;text-align:center;padding:13px 0;border-radius:12px;
               font-size:15px;color:var(--lx-t3);border:1px solid var(--lx-line);cursor:pointer">取消</div>
        </div>`;
      ov.appendChild(sheet);
      document.body.appendChild(ov);

      // 选项高亮 + 单选
      sheet.querySelectorAll("[data-p]").forEach((box) => {
        const key = box.dataset.key;
        const multi = box.dataset.multi === "true";
        if (box.tagName === "INPUT") {
          box.addEventListener("input", () => { vals[key] = box.value; });
          return;
        }
        const paint = () => box.querySelectorAll("[data-v]").forEach(el => {
          const on = String(el.dataset.v) === String(vals[key]);
          el.style.background = on ? "var(--lx-blue)" : "transparent";
          el.style.color = on ? "#fff" : "";
        });
        box.querySelectorAll("[data-v]").forEach(el => {
          const v = el.dataset.v;
          const a = () => {
            if (!multi) vals[key] = v;                 // ★ 不猜多选语义
            else {
              const cur = Array.isArray(vals[key]) ? vals[key] : [vals[key]];
              const i = cur.indexOf(v);
              if (i >= 0) cur.splice(i, 1); else cur.push(v);
              vals[key] = cur;
            }
            paint();
          };
          this._a11y(el, String(v), a);
          el.addEventListener("click", a);
        });
        paint();
      });

      const close = (r) => { ov.remove(); resolve(r); };
      const ok = () => {
        sheet.querySelectorAll("input[data-kind]").forEach((inp) => {
          const key = inp.dataset.key;
          vals[key] = inp.dataset.kind === "num" ? Number(inp.value) : inp.value;
        });
        close(vals);
      };
      sheet.querySelector("#ok").addEventListener("click", ok);
      sheet.querySelector("#cx").addEventListener("click", () => close(null));
      this._a11y(sheet.querySelector("#ok"), "确定", ok);
    });
  }

  _choose(title, labels) {
    return new Promise((resolve) => {
      const ov = document.createElement("div");
      ov.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:20;
        display:flex;align-items:flex-end;justify-content:center;`;
      const sheet = document.createElement("div");
      sheet.style.cssText = `background:var(--lx-bg);color:var(--lx-t1);width:100%;
        max-width:460px;border-radius:20px 20px 0 0;padding:18px 0 26px;
        font-family:inherit;max-height:70vh;overflow:auto;`;
      sheet.innerHTML = `<div style="font-size:16px;font-weight:500;padding:0 20px 14px">${title}</div>`
        + labels.map((l, i) => `<div data-i="${i}" style="padding:15px 20px;
            font-size:15px;border-top:1px solid var(--lx-line);cursor:pointer">${l}</div>`).join("")
        + `<div id="cx" style="padding:15px 20px;font-size:15px;color:var(--lx-t3);
            border-top:8px solid var(--lx-card);cursor:pointer;text-align:center">取消</div>`;
      const close = (v) => { ov.remove(); resolve(v); };
      sheet.querySelectorAll("[data-i]").forEach(el => {
        const i = Number(el.dataset.i);
        const a = () => close(i);
        this._a11y(el, labels[i], a);
        el.addEventListener("click", a);
      });
      const cx = sheet.querySelector("#cx");
      const ca = () => close(null);
      this._a11y(cx, "取消", ca);
      cx.addEventListener("click", ca);
      ov.appendChild(sheet);
      ov.addEventListener("click", (e) => { if (e.target === ov) close(null); });
      this.appendChild(ov);
    });
  }

  async _applyPreset(p) {
    const id = "lx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const cfg = {
      alias: p.name, description: p.desc,
      trigger: [p.trigger], action: p.action, mode: "single",
    };
    try {
      await this._saveCfg(id, cfg);
      this._toast(`已创建「${p.name}」`, "ok", 3200);
      this._tab = "mine"; this._render();
    } catch (e) {
      this._toast("创建失败：" + ((e && e.message) || "未知"), "err", 4000);
    }
  }

  async _save() {
    const d = this._draft;
    const id = "lx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const cfg = { alias: d.name, trigger: d.trigger ? [d.trigger] : [], action: d.action, mode: "single" };
    try {
      await this._saveCfg(id, cfg);
      this._toast(`已创建「${d.name}」`, "ok", 3200);
      this._draft = null;
      this._tab = "mine"; this._render();
    } catch (e) {
      this._toast("创建失败：" + ((e && e.message) || "未知"), "err", 4000);
    }
  }

  async _saveCfg(id, cfg) {
    const h = this._hass;
    const tok = h.auth && h.auth.data ? h.auth.data.access_token : null;
    const res = await fetch(`/api/config/automation/config/${id}`, {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" },
        tok ? { Authorization: "Bearer " + tok } : {}),
      body: JSON.stringify(cfg),
    });
    if (!res.ok) {
      const t = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${t.slice(0,80)}`);
    }
    return res.json().catch(() => ({}));
  }

  _update() {
    if (!this._built) return;
    // 首屏与切换 tab 时重绘（保持输入内容：create 页由 _draft 承载）
    this._render();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangTaskPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "任务大师（HA 版）",
  description: "用 App 的交互创建 HA 自动化：模板库 + 如果/就执行 + 我的任务",
  preview: true,
});
})();

/* ===================== lixiang-ad-page.js ===================== */
(function () {

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


/**
 * lixiang-ad-page —— 智驾统计（二级页）
 *
 * 数据源（真实实体）：
 *   sensor.li_xiang_l6_fu_zhu_jia_shi_li_cheng   辅助驾驶里程
 *   sensor.li_xiang_l6_fu_zhu_jia_shi_tian_shu   辅助驾驶天数
 *   sensor.li_xiang_l6_noa_li_cheng              NOA 里程
 *   sensor.li_xiang_l6_lcc_li_cheng              LCC 里程
 *   sensor.li_xiang_l6_acc_li_cheng              ACC 里程
 *   sensor.li_xiang_l6_zong_li_cheng             总里程（算占比）
 */

const CARD_TAG = "lixiang-ad-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
function lxNavigate(card, path) {
  if (!path || !card) return;
  let handled = false;
  try {
    const ev = new CustomEvent("lx-navigate", {
      detail: { path }, bubbles: true, composed: true, cancelable: true,
    });
    handled = !card.dispatchEvent(ev);          // 被 preventDefault → 父级已接管
  } catch (e) { handled = false; }
  if (handled) return;
  history.pushState(null, "", path);
  card.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
}

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖
const __fontFallback = BUILTIN_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-ad-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-purple:#7B61FF;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-ad-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { container-type:inline-size; position:relative; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:18px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  .topbar { display:flex; align-items:center; height:48px; padding:0 16px; }
  .back { width:24px; height:24px; opacity:.75; cursor:pointer; }
  .topbar h1 { font-size:17px; font-weight:500; margin:0; flex:1; text-align:center; }
  .topbar .r { min-width:56px; }

  /* 主卡：智驾里程 + 占比 */
  .hero { margin:6px 20px 0; border-radius:18px; padding:20px 18px;
          background:linear-gradient(155deg,var(--lx-card) 0%,var(--lx-bg) 100%); }
  .hero .lbl { font-size:12.5px; color:var(--lx-t3); }
  .hero .big { font-family:"LxNum","Licium"; font-size:38px; font-weight:600;
               line-height:1.1; margin-top:6px; }
  .hero .big small { font-size:16px; font-weight:500; color:var(--lx-t2); margin-left:4px; }
  .hero .sub { font-size:12.5px; color:var(--lx-t3); margin-top:8px; }
  .hero .bar { height:8px; border-radius:20px; background:var(--lx-line);
               overflow:hidden; margin-top:14px; display:flex; }
  .hero .bar i { display:block; height:100%; transition:width .5s; }

  /* 三栏明细 */
  .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:11px; padding:14px 20px 0; }
  .g { background:var(--lx-card); border-radius:16px; padding:14px 12px; }
  .g .l { font-size:11.5px; color:var(--lx-t3); display:flex; align-items:center; gap:5px; }
  .g .l i { width:8px; height:8px; border-radius:50%; display:inline-block; }
  .g .v { font-family:"LxNum","Licium"; font-size:19px; font-weight:600; margin-top:6px; }
  .g .v small { font-size:10.5px; color:var(--lx-t2); margin-left:2px; }
  .g .p { font-size:11px; color:var(--lx-t3); margin-top:4px; }

  .sect { padding:18px 20px 0; }
  .sect h2 { font-size:14px; font-weight:500; margin:0 0 10px; }
  .row { display:flex; align-items:center; gap:12px; padding:13px 16px;
         background:var(--lx-card); border-radius:14px; margin-bottom:10px; }
  .row img { width:22px; height:22px; }
  .row .tx { flex:1; }
  .row .nm { font-size:14px; }
  .row .sd { font-size:11.5px; color:var(--lx-t3); margin-top:3px; }
  .row .val { font-family:"LxNum","Licium"; font-size:16px; font-weight:600; }

  /* 说明 */
  .note { margin:18px 20px 0; padding:14px; border-radius:12px;
          background:var(--lx-card); font-size:12px; color:var(--lx-t2);
          line-height:1.65; }
  .note b { color:var(--lx-t1); }
  .note .it { display:flex; gap:8px; margin-top:8px; }
  .note .it:first-child { margin-top:0; }
  .note .dot { color:var(--lx-blue); }

  /* ── 键盘可达：统一焦点样式（无障碍）── */
  [role="button"]:focus-visible, .card:focus-visible, .entry:focus-visible,
  .row.click:focus-visible, .m:focus-visible, .yhead:focus-visible,
  .year .yhead:focus-visible, button:focus-visible, input:focus-visible {
    outline: 2px solid var(--lx-blue, #0A58F6);
    outline-offset: 2px;
    border-radius: 8px;
  }
  /* 尊重「减少动态效果」偏好 */
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
  }

  .refresh { width:30px; height:30px; border-radius:50%; display:flex;
             align-items:center; justify-content:center; cursor:pointer;
             transition:background .15s, transform .3s; }
  .refresh:hover { background:var(--lx-card); }
  .refresh:active { transform:scale(.9); }
  .refresh img { width:17px; height:17px; opacity:.6; }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }

  /* ── 下拉刷新 ── */
  .ptr { position:absolute; left:0; right:0; top:0; height:0; overflow:hidden;
         display:flex; align-items:center; justify-content:center;
         transition:height .2s ease; pointer-events:none; }
  .ptr .sp { width:20px; height:20px; border-radius:50%;
             border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
             animation:lspin .8s linear infinite; }
  .ptr .tx { font-size:11.5px; color:var(--lx-t3); margin-left:8px; }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangAdPage extends HTMLElement {

  /* ── 自动绑定（与 app-home 同一引擎，用户不用手填实体 ID）── */
  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) {
        out = new AB(this._hass, this._config || {}).resolve() || {};
      }
    } catch (e) { /* 引擎不可用时退回手填 */ }
    // ★ 只有非空结果才缓存：hass.entities 未就绪时返回 {} ，
    //   若缓存会导致永久空绑定（真实踩过的坑）
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  /** 取实体：手填配置 > 自动发现 */
  _eid(field) {
    const c = this._config || {};
    const manual = c[field];
    if (typeof manual === "string" && manual.includes(".")) return manual;
    return (this._autoBind() || {})[field] || null;
  }

  /** 嵌套组也支持自动发现 */
  _eidIn(group, key) {
    const c = this._config || {};
    const m = (c[group] || {})[key];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[key] || null;
  }

  /**
   * 让元素键盘可达（无障碍）。
   * 用法：this._a11y(el, "车锁", handler)
   */
  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        handler(e);
      }
    });
  }
  setConfig(c){ this._config=c||{}; this._built=false; }
  set hass(h){ this._hass=h; if(!this._built) this._build(); this._update(); }
  getCardSize(){ return 16; }

  disconnectedCallback() {
    // 清理定时器与监听，避免卡片被移除后仍持有引用（内存泄漏）
    if (this._tt) { clearTimeout(this._tt); this._tt = null; }
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
    if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; }
    this._fetching = false;
    this._fetchingYears = false;
  }
  _num(id){ const s=(id&&this._hass)?this._hass.states[id]:null;
    if(!s||["unknown","unavailable"].includes(s.state)) return null;
    const n=parseFloat(s.state); return isNaN(n)?null:n; }

  _build(){
    while(this.firstChild) this.removeChild(this.firstChild);
    const st=document.createElement("style"); st.textContent=STYLE; this.appendChild(st);
    const c=this._config;
    const root=document.createElement("div");
    root.className="root"; root.dataset.theme=c.theme||"light";
    root.innerHTML=`
      <div class="ptr" id="ptr"><div class="sp"></div><div class="tx">下拉刷新</div></div>
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="返回">
        <h1>智驾统计</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="" style="transform:rotate(-90deg)">
        </div>
      </div>
      <div class="hero">
        <div class="lbl">辅助驾驶总里程</div>
        <div class="big"><span id="h-ad">—</span><small>km</small></div>
        <div class="sub" id="h-sub">—</div>
        <div class="bar">
          <i id="b-noa" style="width:0%"></i>
          <i id="b-lcc" style="width:0%"></i>
          <i id="b-acc" style="width:0%"></i>
        </div>
      </div>
      <div class="grid">
        <div class="g"><div class="l"><i style="background:#0A58F6"></i>NOA</div>
          <div class="v"><span id="g-noa">—</span><small>km</small></div>
          <div class="p" id="p-noa">—</div></div>
        <div class="g"><div class="l"><i style="background:#34C759"></i>LCC</div>
          <div class="v"><span id="g-lcc">—</span><small>km</small></div>
          <div class="p" id="p-lcc">—</div></div>
        <div class="g"><div class="l"><i style="background:#FF9500"></i>ACC</div>
          <div class="v"><span id="g-acc">—</span><small>km</small></div>
          <div class="p" id="p-acc">—</div></div>
      </div>
      <div class="sect">
        <h2>使用情况</h2>
        <div class="row"><img src="${__iconBase}/ic_home_navigation.webp" onerror="__lxIconFallback(this)" alt="">
          <div class="tx"><div class="nm">累计使用天数</div>
            <div class="sd" id="d-sub">—</div></div>
          <div class="val"><span id="d-days">—</span> 天</div></div>
        <div class="row"><img src="${__iconBase}/ic_home_mileage.webp" onerror="__lxIconFallback(this)" alt="">
          <div class="tx"><div class="nm">占总里程比例</div>
            <div class="sd" id="t-sub">—</div></div>
          <div class="val"><span id="d-ratio">—</span>%</div></div>
        <div class="row"><img src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'">
          <div class="tx"><div class="nm">日均智驾里程</div>
            <div class="sd">辅助驾驶里程 ÷ 使用天数</div></div>
          <div class="val"><span id="d-avg">—</span> km</div></div>
      </div>
      <div class="note">
        <div class="it"><span class="dot">·</span><span><b>NOA</b>（导航辅助驾驶）：在高精地图覆盖路段自动变道、进出匝道。</span></div>
        <div class="it"><span class="dot">·</span><span><b>LCC</b>（车道居中辅助）：保持车道居中并跟车行驶。</span></div>
        <div class="it"><span class="dot">·</span><span><b>ACC</b>（自适应巡航）：仅保持车速与车距，不做车道控制。</span></div>
        <div class="it"><span class="dot">·</span><span>数据来源为车端统计，可能存在延迟，请以车辆显示为准。</span></div>
      </div>
    `;
    this.appendChild(root);
    const _bk4 = this.querySelector("#back");
    this._a11y(_bk4, "返回", ()=>_bk4.click());
    _bk4.addEventListener("click", ()=>{
      const p=(c.nav||{}).back||"/lixiang/app";
      lxNavigate(this, p);
    });
    
    // 刷新：重新拉取实体状态
    const _rf = this.querySelector("#refresh");
    const _doRf = () => {
      const el = this.querySelector("#refresh");
      if (el) el.classList.add("spin");
      this._built = this._built;   // 触发 _update
      this._update(); if (this._fetchStats) this._fetchStats();
      setTimeout(() => { if (el) el.classList.remove("spin"); }, 700);
    };
    if (_rf) { this._a11y(_rf, "刷新", _doRf); _rf.addEventListener("click", _doRf); }

    // ── 下拉刷新（触摸手势，对齐 App）──
    (() => {
      const ptr = this.querySelector("#ptr");
      const rootEl = this.querySelector(".root");
      if (!ptr || !rootEl) return;
      let startY = 0, pulling = false, dist = 0;
      const TH = 64;
      rootEl.addEventListener("touchstart", (e) => {
        if (window.scrollY > 4) return;
        startY = e.touches[0].clientY; pulling = true; dist = 0;
      }, { passive: true });
      rootEl.addEventListener("touchmove", (e) => {
        if (!pulling) return;
        dist = e.touches[0].clientY - startY;
        if (dist > 0 && window.scrollY <= 4) {
          const h = Math.min(dist * 0.55, 70);
          ptr.style.height = h + "px";
          ptr.querySelector(".tx").textContent = h >= TH * 0.5 ? "松开刷新" : "下拉刷新";
        }
      }, { passive: true });
      rootEl.addEventListener("touchend", () => {
        if (!pulling) return;
        pulling = false;
        const h = parseFloat(ptr.style.height) || 0;
        if (h >= TH * 0.5) {
          ptr.style.height = "44px";
          ptr.querySelector(".tx").textContent = "刷新中…";
          Promise.resolve(this.this._update()).finally(() => {
            setTimeout(() => { ptr.style.height = "0px"; }, 500);
          });
        } else {
          ptr.style.height = "0px";
        }
        dist = 0;
      }, { passive: true });
    })();

    this._built=true;
  }

  _update(){
    if(!this._built) return;
    const c=this._config, q=s=>this.querySelector(s);
    const ad=this._num(this._eid("ad_km")), noa=this._num(this._eid("noa_km")),
          lcc=this._num(this._eid("lcc_km")), acc=this._num(this._eid("acc_km"));
    const total=this._num(this._eid("total_km")), days=this._num(this._eid("ad_days"));
    const fmt=(n)=> n==null ? "—" : Math.round(n).toLocaleString();

    q("#h-ad").textContent = fmt(ad);
    if (ad!=null && total!=null && total>0) {
      q("#h-sub").textContent = `占总里程 ${(ad/total*100).toFixed(1)}%（总里程 ${fmt(total)} km）`;
    } else q("#h-sub").textContent = "数据加载中…";

    // 占比条（以 NOA/LCC/ACC 之和为分母）
    const parts=[["noa",noa],["lcc",lcc],["acc",acc]];
    const sum=parts.reduce((a,[,v])=>a+(v||0),0);
    parts.forEach(([k,v])=>{
      const el=q(`#b-${k}`);
      if(!el) return;
      el.style.width = (sum>0 && v!=null) ? (v/sum*100)+"%" : "0%";
      el.style.background = k==="noa"?"#0A58F6":(k==="lcc"?"#34C759":"#FF9500");
    });
    [["noa",noa],["lcc",lcc],["acc",acc]].forEach(([k,v])=>{
      const vEl=q(`#g-${k}`), pEl=q(`#p-${k}`);
      if(vEl) vEl.textContent = fmt(v);
      if(pEl) pEl.textContent = (sum>0 && v!=null) ? `占智驾 ${(v/sum*100).toFixed(1)}%` : "—";
    });

    q("#d-days").textContent = days==null ? "—" : Math.round(days).toLocaleString();
    if (days!=null) {
      const startYear = new Date().getFullYear() - Math.floor(days/365);
      q("#d-sub").textContent = `自 ${startYear} 年起累计`;
    } else q("#d-sub").textContent = "—";

    if (ad!=null && total!=null && total>0) {
      const r=ad/total*100;
      q("#d-ratio").textContent = r.toFixed(1);
      q("#t-sub").textContent = `${fmt(ad)} ÷ ${fmt(total)} km`;
    } else { q("#d-ratio").textContent="—"; q("#t-sub").textContent="—"; }

    if (ad!=null && days!=null && days>0) q("#d-avg").textContent = (ad/days).toFixed(1);
    else q("#d-avg").textContent = "—";
  }
}

if(!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangAdPage);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "智驾统计（二级页）",
  description: "NOA/LCC/ACC 里程与占比、使用天数、日均里程",
  preview: true,
});
})();

/* ===================== lixiang-bindings-card.js ===================== */
(function () {

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


/**
 * lixiang-bindings-card —— 自动发现诊断卡
 *
 * 用途：
 *   · 查看卡片自动绑定了哪些实体（透明度）
 *   · 排查「某个数据不显示」（缺哪个字段一眼可见）
 *   · 提交 issue 时截图/复制，帮我们支持新车型
 *
 * 配置：
 *   type: custom:lixiang-bindings-card
 *   vin: HLX32XXXXXXXXXXXX   # 可选，多车时指定
 *   show_all: true           # 显示未匹配字段（默认 true）
 */

const CARD_TAG = "lixiang-bindings-card";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// —— 图标基址自动降级（★ 2026-10-14）——
// 为什么需要：快捷按钮等图标是 **JS 赋值**的（img.src = ...），没有 HTML 属性
// 可挂 onerror 回退 → 用户机器上没有 /local/lixiang-icons 时**永久破图**
// （车主实测：别人家的 L8 八个快捷按钮全是破图）。
// 做法：整页只探一次 /local/lixiang-icons（用 Image 探测，**不做 DOM 查询** ——
// HA 卡片在 Shadow DOM 内，document 级选择器查不到；见
// tests/test_frontend_cards.py::test_cards_no_global_dom_query）。
// 探测失败 → 把本模块的图标基址切到集成内置路径。
// 必须放在 __iconBase 声明**之后**（否则 TDZ 抛错，探测静默失效）。
{
  const __toBuiltin = () => { __iconBase = __iconFallback; };
  if (typeof window !== "undefined") {
    if (window.__lxIconBaseMissing) {
      __toBuiltin();
    } else {
      window.__lxIconCbs = window.__lxIconCbs || [];
      window.__lxIconCbs.push(__toBuiltin);
      if (!window.__lxIconProbing) {
        window.__lxIconProbing = true;
        const __p = new Image();
        __p.onerror = () => {
          window.__lxIconBaseMissing = true;
          (window.__lxIconCbs || []).forEach(fn => { try { fn(); } catch (e) { /* 忽略 */ } });
        };
        __p.src = DEFAULT_ICON_BASE + "/ic_home_battery.webp";
      }
    }
  }
}

let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf"); font-weight:500; font-display:swap; }
  lixiang-bindings-card { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-bindings-card { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding:16px 18px 18px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }
  h2 { font-size:16px; font-weight:500; margin:0 0 4px; }
  .sub { font-size:12px; color:var(--lx-t3); margin-bottom:14px; }

  /* 概览 */
  .sum { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:14px; }
  .s { background:var(--lx-card); border-radius:14px; padding:12px 10px; text-align:center; }
  .s .v { font-size:19px; font-weight:600; }
  .s .v.ok { color:var(--lx-green); }
  .s .v.bad { color:var(--lx-orange); }
  .s .l { font-size:11px; color:var(--lx-t3); margin-top:4px; }

  /* 车型 */
  .model { background:var(--lx-card); border-radius:14px; padding:12px 14px; margin-bottom:14px;
           font-size:13px; display:flex; align-items:center; gap:8px; }
  .model b { font-weight:600; }
  .model .tag { font-size:11px; padding:2px 8px; border-radius:7px;
                background:rgba(10,88,246,.1); color:var(--lx-blue); }

  /* 表格 */
  .sec { font-size:13px; color:var(--lx-t3); margin:16px 0 8px; }
  .tbl { width:100%; border-collapse:collapse; font-size:12.5px; }
  .tbl td { padding:7px 6px; border-bottom:1px solid var(--lx-line); vertical-align:middle; }
  .tbl tr:last-child td { border-bottom:none; }
  .tbl .f { color:var(--lx-t2); width:34%; }
  .tbl .e { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11.5px;
            color:var(--lx-t1); word-break:break-all; }
  .tbl .s { width:26px; text-align:center; }
  .dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--lx-green); }
  .dot.miss { background:var(--lx-orange); }

  /* 操作 */
  .acts { display:flex; gap:10px; margin-top:16px; }
  .btn { flex:1; text-align:center; padding:11px; border-radius:12px; font-size:13.5px;
         background:var(--lx-card); cursor:pointer; transition:background .15s; }
  .btn:hover { background:#EFEFF3; }
  .btn:active { transform:scale(.98); }
  .btn.primary { background:var(--lx-blue); color:#fff; }
  .btn.primary:hover { background:#0B4FD8; }
  .tip { font-size:11.5px; color:var(--lx-t3); margin-top:12px; line-height:1.6; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  /* 无障碍：键盘焦点 + 动效偏好 */
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }
`;

class LixiangBindingsCard extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._built = false; }
  set hass(h) { this._hass = h; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 14; }
  disconnectedCallback() { if (this._tt) clearTimeout(this._tt); }

  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault(); e.stopPropagation(); handler(e);
      }
    });
  }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root"; root.dataset.theme = (this._config && this._config.theme) || "light";
    root.innerHTML = `
      <h2>实体自动发现</h2>
      <div class="sub">卡片会按实体名称自动绑定，无需手填实体 ID</div>
      <div class="sum" id="sum"></div>
      <div class="model" id="model"></div>
      <div id="tables"></div>
      <div class="acts">
        <div class="btn" id="btn-copy" role="button" tabindex="0" aria-label="复制绑定详情">复制详情</div>
        <div class="btn primary" id="btn-refresh" role="button" tabindex="0" aria-label="重新扫描">重新扫描</div>
      </div>
      <div class="tip">如果某个功能没绑上，通常说明当前车型没有该实体（而非卡片出错）。<br>
        复制详情后可在 issue 中粘贴，帮助我们适配新车型。</div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const copy = () => this._copy();
    this._a11y(this.querySelector("#btn-copy"), "复制绑定详情", copy);
    this.querySelector("#btn-copy").addEventListener("click", copy);

    const ref = () => { this._refresh(); };
    this._a11y(this.querySelector("#btn-refresh"), "重新扫描", ref);
    this.querySelector("#btn-refresh").addEventListener("click", ref);

    this._built = true;
  }

  _toast(msg) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show";
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2000);
  }

  _entries() {
    // 复用卡片里的实体识别逻辑（与 app-home 一致）
    const out = {};
    for (const id of Object.keys(this._hass.states || {})) {
      const e = (this._hass.entities || {})[id];
      if (e && e.platform === "lixiang_auto") out[id] = e.original_name || e.name || id;
    }
    return out;
  }

  _refresh() {
    if (this._engine) { this._engine._cache = null; }
    this._update();
    this._toast("已重新扫描");
  }

  _copy() {
    const sm = this._snapshot();
    const lines = [
      `# 理想卡片实体绑定诊断`,
      `车型: ${sm.model || "(未识别)"}  车系: ${sm.series || "-"}`,
      `实体池: ${sm.poolSize}`,
      `匹配: ${sm.matched}/${sm.total} (${sm.rate})`,
      ``,
      `## 已绑定`,
      ...Object.entries(sm.bindings).map(([f, e]) => `${f}\t${e}`),
      ``,
      `## 未匹配`,
      ...(sm.missing || []).map((f) => f),
    ];
    const text = lines.join("\n");
    const done = () => this._toast("已复制到剪贴板");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => this._fallbackCopy(text, done));
    } else this._fallbackCopy(text, done);
  }

  _fallbackCopy(text, done) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      this.appendChild(ta); ta.select();
      document.execCommand("copy");
      this.removeChild(ta); done();
    } catch (e) { this._toast("复制失败，请手动选择"); }
  }

  _snapshot() {
    const AB = window.LixiangAutoBind;
    if (!AB) {
      return { poolSize: 0, total: 0, matched: 0, rate: "0%", bindings: {}, missing: ["(引擎未加载)"] };
    }
    this._engine = new AB(this._hass, this._config || {});
    const detected = this._detectModel();
    return this._engine.summary(detected);
  }

  _detectModel() {
    const c = this._config || {}, h = this._hass;
    if (c.model_name) return { name: c.model_name, model: c.model_name,
                               series: this._seriesOf(c.model_name) };
    let out = null;
    if (h && h.devices) {
      for (const d of Object.values(h.devices)) {
        const isLi = (d.manufacturer || "").includes("理想")
          || JSON.stringify(d.identifiers || []).includes("lixiang");
        if (!isLi) continue;
        const mdl = d.model || d.name || "";
        out = { name: d.name || mdl, model: mdl, series: this._seriesOf(mdl) };
        break;
      }
    }
    return out;
  }
  _seriesOf(t) {
    const m = String(t || "").match(/(MEGA|L[6-9]|i[6-9]|ONE)/i);
    return m ? m[1].toUpperCase() : "";
  }

  _update() {
    if (!this._built) return;
    const sm = this._snapshot();
    const q = (s) => this.querySelector(s);

    q("#sum").innerHTML = `
      <div class="s"><div class="v ok">${sm.matched}</div><div class="l">已绑定</div></div>
      <div class="s"><div class="v ${sm.missing.length ? "bad" : ""}">${sm.missing.length}</div>
        <div class="l">未匹配</div></div>
      <div class="s"><div class="v">${sm.rate}</div><div class="l">匹配率</div></div>`;

    q("#model").innerHTML = sm.model
      ? `车型 <b>${sm.model}</b>${sm.series ? `<span class="tag">${sm.series}</span>` : ""}
         <span style="color:var(--lx-t3);margin-left:auto">实体池 ${sm.poolSize}</span>`
      : `未识别到理想设备 <span style="color:var(--lx-t3);margin-left:auto">实体池 ${sm.poolSize}</span>`;

    const showAll = this._config.show_all !== false;
    const rows = Object.entries(sm.bindings).map(([f, e]) =>
      `<tr><td class="s"><span class="dot"></span></td>
       <td class="f">${f}</td><td class="e">${e}</td></tr>`);
    const missRows = showAll && sm.missing.length
      ? `<div class="sec">未匹配（当前车型可能没有）</div>
         <table class="tbl">${sm.missing.map((f) =>
           `<tr><td class="s"><span class="dot miss"></span></td>
            <td class="f">${f}</td><td class="e" style="color:var(--lx-t3)">—</td></tr>`).join("")}</table>`
      : "";
    q("#tables").innerHTML =
      `<div class="sec">已绑定 (${sm.matched})</div>
       <table class="tbl">${rows.join("")}</table>${missRows}`;
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangBindingsCard);
window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "实体自动发现（诊断）",
  description: "查看卡片自动绑定了哪些实体；未匹配项一目了然；可复制详情反馈",
  preview: true,
});
})();

/* ===================== lixiang-overview-card.js ===================== */
(function () {
/* lixiang-overview-card —— 理想汽车「车辆总览」卡片
 *
 * ★ 2026-10-13 新增
 *
 * 设计参考社区「尊界 S800 车辆总览」卡的深色玻璃风格：
 *   三栏（身份 / 能量 / 车况）→ 窄屏两栏 → 手机单栏。
 * 但数据来源完全不同：
 *   · 尊界卡要求用户手填 28 个实体 ID；本卡走**实体自动发现**，
 *     默认零配置（可选用 config.entities 覆盖个别字段）。
 *   · 车型名、车图、车漆色都由集成接口给，与实车一致。
 *
 * 只读展示卡：不发送任何车辆控制指令。
 */
const CARD_TAG = "lixiang-overview-card";

/* ── 车辆位置小地图：自绘高德瓦片 ────────────────────────────────
 * ★ 2026-10-18 改用自绘，替换 HA 官方 <ha-map>。
 *   原因：ha-map 的瓦片走 HA 代理 /api/map_tiles，上游不可达时整块空白
 *   （实测：该网络环境只解析到 IPv6 且无 IPv6 出口 → 代理 502 → 地图不显示）；
 *   车控「位置页」自己拉高德瓦片一直正常 → 统一成同一套实现。
 *   坐标系要点（位置页踩过）：经纬度换出的是【瓦片坐标系里的小数】(如 27394.7)，
 *   车辆相对该瓦片左上角的像素偏移 = 小数部分 × 256；
 *   早前把整个 cx（两万多）当像素用 → left ≈ -1400 万 px → 瓦片全跑出屏幕。
 */
const _lonlatToTile = (lat, lon, z) => {
  const n = 2 ** z;
  return [((lon + 180) / 360) * n,
          ((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n];
};
const _amapTile = (tx, ty, z) => {
  const s = (((tx + ty) % 4) + 4) % 4 + 1;      // 高德 4 节点轮询
  // ★ style=8：实测高德已下线 style=6（深色）→ 404；style=8 可用
  //   （与车控「位置页」保持一致；实测 200 / 17012 字节）
  return `https://webrd0${s}.is.autonavi.com/appmaptile`
       + `?lang=zh_cn&size=1&scale=1&style=8&x=${tx}&y=${ty}&z=${z}`;
};
const _renderTileMap = (box, lat, lon, z, opt) => {
  const W = (opt && opt.w) || box.clientWidth || 320;
  const H = (opt && opt.h) || box.clientHeight || 190;
  const [fx, fy] = _lonlatToTile(lat, lon, z);
  const cx = Math.floor(fx), cy = Math.floor(fy);
  const offX = (fx - cx) * 256, offY = (fy - cy) * 256;
  const cpx = W / 2, cpy = H / 2, n = 2 ** z;
  const want = [];
  for (let tx = cx - Math.ceil((cpx - offX) / 256);
       tx <= cx + Math.ceil((W - cpx + offX) / 256); tx++) {
    for (let ty = cy - Math.ceil((cpy - offY) / 256);
         ty <= cy + Math.ceil((H - cpy + offY) / 256); ty++) {
      if (tx < 0 || ty < 0 || tx >= n || ty >= n) continue;
      want.push({ k: tx + "_" + ty, tx, ty,
        left: Math.round(cpx - offX + (tx - cx) * 256),
        top:  Math.round(cpy - offY + (ty - cy) * 256) });
    }
  }
  const have = new Map();
  box.querySelectorAll("img[data-k]").forEach((im) => have.set(im.dataset.k, im));
  for (const w of want) {
    const im = have.get(w.k);
    const url = _amapTile(w.tx, w.ty, z);
    if (im) {
      im.style.left = w.left + "px"; im.style.top = w.top + "px";
      if (im.getAttribute("src") !== url) im.src = url;
      have.delete(w.k);
    } else {
      const el = document.createElement("img");
      el.dataset.k = w.k; el.src = url;
      el.style.left = w.left + "px"; el.style.top = w.top + "px";
      box.appendChild(el);
    }
  }
  have.forEach((im) => im.remove());
};
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先

// 内置图标回退（与其它卡片一致）
const __lxIconFallback = (typeof window !== "undefined" && (window.__lxIconFallback = window.__lxIconFallback || function (img) {
  if (img.dataset.lxFb) return;
  img.dataset.lxFb = "1";
  const s = img.getAttribute("src") || "";
  const rel = s.replace(/^\/local\/lixiang-icons\//, "");
  if (rel === s) return;
  img.src = "/lixiang_auto/lixiang-icons/" + rel;
})) || function () {};

const STYLE = `
  :host { display:block; container-type:inline-size; color:#eef2f8;
          font-family:"Licium",-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
          -webkit-tap-highlight-color:transparent; }
  * { box-sizing:border-box; }
  ha-card { display:block; overflow:hidden; border-radius:26px!important;
            border:1px solid #c2cce535!important; color:#eef2f8!important;
            background:radial-gradient(ellipse at 8% 0%,#5b7a9c3d,transparent 52%),
                       linear-gradient(120deg,#243444eb,#232840eb)!important;
            box-shadow:0 12px 36px #0002!important; }
  .main { display:grid; grid-template-columns:minmax(0,1.26fr) minmax(0,1fr) minmax(0,.86fr);
          gap:26px; padding:22px 26px 16px; }
  .identity,.energy,.condition { min-width:0; }
  .eyebrow { font-size:10px; color:#9fb6d6; letter-spacing:4px; font-weight:650; }
  .title { font-size:29px; font-weight:600; letter-spacing:1.5px; margin:5px 0 3px; }
  .title b { font-weight:350; letter-spacing:1px; margin-left:8px; }
  .subtitle { color:#adbbcd; font-size:12px; letter-spacing:.6px; }
  .badges { display:flex; gap:7px; flex-wrap:wrap; margin-top:12px; }
  .badge { font-size:11px; padding:4px 10px; border:1px solid #ffffff26; border-radius:30px;
           color:#d4dceb; background:#ffffff08; white-space:nowrap; }
  .badge.online { color:#a5e3d2; border-color:#91d8c333; background:#89d5bc12; }
  .badge.offline { color:#cfd6e0; }
  .dot { display:inline-block; width:5px; height:5px; border-radius:50%;
         background:currentColor; margin-right:5px; vertical-align:middle; }
  .art { position:relative; height:170px; margin:6px 0 0; overflow:hidden;
         border-radius:16px; }
  .art.has-photo { border:1px solid #ffffff14; background:#0d1622; }
  .art:before { content:''; position:absolute; inset:22px 12px 4px;
                background:radial-gradient(ellipse,#c9d6ea1a,transparent 68%); }
  .art img { position:absolute; inset:0; width:100%; height:100%;
             object-fit:contain; pointer-events:none; }
  .art-note { color:#9fadc2; font-size:9px; text-align:right; margin-top:6px; }
  .range-main { display:flex; align-items:baseline; gap:8px; margin-bottom:13px; flex-wrap:wrap; }
  .range-main>span { color:#b6c4d6; font-size:12px; flex:1; }
  .range-main>b { font-size:36px; font-weight:550; letter-spacing:-1.2px; line-height:1.3; }
  .range-main small { font-size:13px; color:#bcc8d8; letter-spacing:0; }
  .meter { padding:12px 15px; margin-top:10px; border-radius:15px;
           background:#ffffff06; border:1px solid #ffffff10; }
  .meter-top { display:flex; align-items:baseline; justify-content:space-between;
               font-size:12px; color:#cbd7e5; }
  .meter-top strong { font-size:23px; font-weight:500; line-height:1.15; }
  .meter-top small { font-size:12px; color:#b7c5d6; }
  .track { height:5px; background:#ffffff12; border-radius:10px; margin:10px 0; overflow:hidden; }
  .track i { display:block; height:100%; border-radius:10px;
             background:linear-gradient(90deg,#4c9aff,#9fd0ff); }
  .fuel .track i { background:linear-gradient(90deg,#a98d63,#e6d2ab); }
  .range { display:flex; justify-content:space-between; font-size:11px; color:#aebed0; }
  .range b { font-size:16px; color:#eef4fc; font-weight:500; }
  .range small { font-size:11px; font-weight:400; color:#b4c2d4; }
  .charge { display:flex; justify-content:space-between; gap:8px; margin:12px 2px 0;
            font-size:11px; color:#c0cddd; }
  .charge b { color:#e2e9f5; font-weight:500; }
  .section-label { display:flex; justify-content:space-between; align-items:center;
                   color:#c1cddd; font-size:12px; margin:6px 0 10px; }
  .section-label small { font-size:10px; color:#8d9db3; }
  .tire-grid { height:158px; display:grid; grid-template-columns:1fr 72px 1fr;
               grid-template-rows:1fr 1fr; gap:6px 4px; align-items:center; text-align:center; }
  .tire { display:flex; flex-direction:column; align-items:center; }
  .tire span { font-size:10px; color:#a5b6cb; }
  .tire b { font-size:22px; font-weight:450; line-height:1.35; }
  .tire.low b { color:#e8b96b; }
  .tire small { font-size:9px; color:#8fa3bb; }
  .top-car { grid-column:2; grid-row:1/3; width:72px; height:148px; opacity:.92; }
  .cabin { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:13px; }
  .cabin .detail-stat { padding:10px 9px; border:1px solid #ffffff10; border-radius:12px;
                        background:#ffffff03; }
  .detail-stat { min-width:0; display:flex; flex-direction:column; gap:4px; }
  .detail-stat span { font-size:10px; color:#a3b2c6; }
  .detail-stat b { font-size:15px; font-weight:500; color:#e9eff8; white-space:nowrap;
                   overflow:hidden; text-overflow:ellipsis; }
  .footer { display:flex; justify-content:space-between; gap:12px; align-items:center;
            padding:10px 26px; border-top:1px solid #ffffff12; background:#0000000c;
            flex-wrap:wrap; font-size:10px; color:#a8b6c8; }
  .fresh { color:#b2c9b9; }
  .stale { color:#dfba83; }
  .details { border-top:1px solid #ffffff0c; }
  /* ★ 2026-10-17 车辆位置（复用 HA 官方 ha-map，见 _mapHtml） */
  .mapsec { padding:0 26px 14px; }
  .mapsec .lxmap { display:block; height:190px; border-radius:14px; overflow:hidden;
                   position:relative; background:#0d1520; }
  /* 自绘高德瓦片（2026-10-18 替换 ha-map，见 _renderTileMap 注释） */
  .mapsec .lxmap .tiles { position:absolute; inset:0; overflow:hidden; }
  .mapsec .lxmap .tiles img { position:absolute; width:256px; height:256px;
                             max-width:none; user-select:none; pointer-events:none; }
  @container (max-width: 520px) { .mapsec { padding:0 14px 12px; } .mapsec .lxmap { height:160px; } }
  .details summary { font-size:11px; color:#bac7d7; padding:11px 26px; cursor:pointer;
                     user-select:none; }
  .details summary:focus-visible { outline:2px solid #a9d7ed; outline-offset:-4px; }
  .detail-grid { padding:4px 26px 16px; display:grid;
                 grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }
  .note { font-size:10px; color:#98a7bb; padding:0 26px 15px; line-height:1.7; }

  /* ── 超宽屏（电脑/分区视图占满整行）────────────────────────────
     ★ 2026-10-14：卡片拉到 1400px+ 时三栏被拉散、内容稀疏（大片空白）。
     处理：① 内容区限宽 1440px 居中，避免无限拉伸；
           ② 同档放大车图与字号，让宽屏有"大屏该有的信息密度"。 */
  @container (min-width: 1250px) {
    .main { max-width:1440px; margin:0 auto; gap:34px; padding:26px 34px 20px; }
    .title { font-size:34px; }
    .subtitle { font-size:13px; }
    .badge { font-size:12px; padding:5px 12px; }
    .art { height:214px; }
    .art-note { font-size:10px; }
    .range-main>b { font-size:44px; }
    .range-main>span { font-size:13px; }
    .meter { padding:15px 18px; margin-top:12px; border-radius:17px; }
    .meter-top strong { font-size:26px; }
    .track { height:6px; margin:12px 0; }
    .range b { font-size:18px; }
    .charge { font-size:12px; margin-top:14px; }
    .section-label { font-size:13px; margin:8px 0 12px; }
    .tire-grid { height:196px; grid-template-columns:1fr 96px 1fr; gap:8px 6px; }
    .top-car { width:96px; height:184px; }
    .tire b { font-size:25px; }
    .tire span { font-size:11px; }
    .cabin { gap:10px; margin-top:16px; }
    .cabin .detail-stat { padding:12px 11px; }
    .cabin .detail-stat b { font-size:17px; }
    .cabin .detail-stat span { font-size:11px; }
    .footer, .details summary, .detail-grid, .note { max-width:1440px; margin-left:auto; margin-right:auto; }
    .footer { padding:12px 34px; font-size:11px; }
    .detail-grid { gap:20px; }
  }

  @container (max-width: 950px) {
    .main { gap:18px; padding:20px; }
    .title { font-size:25px; }
    .art { height:160px; }
    .tire-grid { grid-template-columns:1fr 58px 1fr; }
    .top-car { width:58px; }
    .footer { padding:10px 20px; }
  }
  /* 中等宽度（HA masonry 单列 ≈500-750px）：身份区与能量区**并排**，
     而不是把身份区拉满整行（那样在电脑上像手机版）。车况整行放下面。 */
  @container (max-width: 750px) {
    .main { grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px 18px; }
    .condition { grid-column:1/-1; padding-top:14px; border-top:1px solid #ffffff12; }
    .tire-grid { grid-template-columns:minmax(0,1fr) 84px minmax(0,1fr); height:170px; }
    .top-car { width:84px; height:158px; }
    .title { font-size:26px; }
    .art { height:150px; }
    /* ★ 2026-10-14 车主："剩余时间下面，一行直接显示四个" ——
         统计区固定【一行四个】，不再随宽度降到 3/2 列（那样"剩余充电时间"下面
         的 4 项会掉成两行）。 */
    .detail-grid { grid-template-columns:repeat(4,minmax(0,1fr)); }
  }
  @container (max-width: 480px) {
    .main { grid-template-columns:1fr; padding:20px 18px 14px; gap:18px; }
    .identity { grid-column:auto; }
    .art { height:158px; margin:2px -4px 0; }
    .energy { border-top:1px solid #ffffff12; padding-top:14px; }
    .condition { border-top:1px solid #ffffff12; padding-top:10px; }
    .tire-grid { grid-template-columns:1fr 88px 1fr; height:164px; }
    .top-car { width:88px; height:156px; }
    .footer { padding:12px 18px; gap:5px; }
    .detail-grid { grid-template-columns:repeat(4,minmax(0,1fr)); padding:4px 14px 16px; gap:10px; }
    .details summary { padding:12px 18px; }
    .note { padding:0 18px 14px; }
  }
  @media (prefers-reduced-motion: reduce) { * { transition:none!important; } }
`;

// 无 DOM 环境（Node 单测）也能导入：HTMLElement 缺失时退化为普通类
const __Base = (typeof HTMLElement !== "undefined") ? HTMLElement : class {};

class LixiangOverviewCard extends __Base {
  constructor() {
    super();
    // ★ shadow DOM：与尊界卡同款做法。同时 `:host{container-type:inline-size}`
    //   只有在 shadow root 里才成立 —— 用 light DOM 时容器查询不会生效，
    //   窄屏断点会失效（实测：400px 下仍是三栏、数字被挤断）。
    if (typeof this.attachShadow === "function") this.attachShadow({ mode: "open" });
    this._built = false;
    this._bindCache = null;
    this._artDone = false;
  }

  setConfig(config) {
    if (config && config.entities && typeof config.entities !== "object") {
      throw new Error("entities 必须是「字段: 实体ID」的对象");
    }
    this._config = config || {};
    this._built = false;
    this._bindCache = null;
    if (this._hass) this._build();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    const sig = this._signature();
    if (sig !== this._sig) { this._sig = sig; this._render(); }
  }

  connectedCallback() {
    this._tm = setInterval(() => { if (this._hass) this._render(); }, 60000);
  }
  disconnectedCallback() { clearInterval(this._tm); }
  getCardSize() { return 6; }
  getGridOptions() { return { columns: 48, rows: "auto", min_columns: 12 }; }

  /* ---------- 实体解析：手填 > 自动发现 ---------- */
  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) { /* 引擎不可用 → 全走手填 */ }
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  _eid(field) {
    const m = (this._config.entities || {})[field];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[field] || null;
  }

  _st(field) { const id = this._eid(field); return (id && this._hass) ? this._hass.states[id] : null; }
  state(field) { const s = this._st(field); return s ? s.state : undefined; }
  _num(v) {
    if (v === undefined || v === null || v === "" || v === "unknown" || v === "unavailable") return null;
    const n = Number(String(v).replace(/[^\d.\-+]/g, ""));
    return Number.isFinite(n) ? n : null;
  }
  num(field) { return this._num(this.state(field)); }
  fmt(field, d = 0) {
    const n = this.num(field);
    if (n === null) return "—";
    return n.toLocaleString("zh-CN", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  /** 实体单位（小写）—— 不假设单位，按实体实际单位换算/显示 */
  _unit(field) {
    const st = this._st(field);
    return String(((st && st.attributes) || {}).unit_of_measurement || "").toLowerCase();
  }

  /** 胎压 → {v, unit}：实体是 kPa 时换算成 bar（与「车辆健康」页同一规则） */
  _pressure(field) {
    const v = this.num(field);
    if (v === null) return { v: null, unit: "bar" };
    const u = this._unit(field);
    if (u.includes("kpa")) return { v: v / 100, unit: "bar" };
    if (u.includes("psi")) return { v: v / 14.5038, unit: "bar" };
    if (u.includes("bar")) return { v, unit: "bar" };
    return { v, unit: u || "bar" };
  }

  /** 百分比类字段：只有实体单位确实是 % 才当作百分比（可画进度条） */
  _pct(field) {
    const v = this.num(field);
    if (v === null) return null;
    const u = this._unit(field);
    if (u && !u.includes("%")) return null;
    return Math.max(0, Math.min(100, v));
  }

  esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* 车型（读设备注册表；config.model_name 可覆盖） */
  _model() {
    const c = this._config || {};
    if (c.model_name) return { name: c.model_name, series: this._series(c.model_name) };
    const h = this._hass;
    if (h && h.devices) {
      for (const d of Object.values(h.devices)) {
        const isLi = (d.manufacturer || "").includes("理想")
          || JSON.stringify(d.identifiers || []).includes("lixiang");
        if (!isLi) continue;
        if (c.vin && !JSON.stringify(d.identifiers || []).includes(c.vin)) continue;
        const mdl = d.model || d.name || "";
        return { name: d.name || mdl, series: this._series(mdl) };
      }
    }
    return { name: "", series: "" };
  }
  _series(text) {
    const m = String(text || "").match(/(MEGA|L[6-9]|i[6-9]|ONE)/i);
    return m ? m[1].toUpperCase() : "";
  }

  /* 数据新鲜度：取已用实体的最新 last_updated */
  _lastUpdated() {
    const h = this._hass; if (!h) return null;
    let best = 0;
    for (const f of ["battery", "range_total", "range_elec", "online", "status"]) {
      const s = this._st(f);
      if (s && s.last_updated) {
        const t = Date.parse(s.last_updated);
        if (Number.isFinite(t) && t > best) best = t;
      }
    }
    return best || null;
  }
  _fmtTime(ts) {
    if (!ts) return "暂无时间";
    const tz = (this._hass && this._hass.config && this._hass.config.time_zone) || "Asia/Shanghai";
    return new Date(ts).toLocaleString("zh-CN", {
      timeZone: tz, month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  }

  _signature() {
    const h = this._hass;
    if (!h) return "";
    const fields = ["battery", "range_total", "range_elec", "range_fuel", "fuel",
      "tire_lf", "tire_rf", "tire_lr", "tire_rr", "room_temp", "target_temp",
      "ac", "charge_status", "charge_power", "charge_remain", "online", "status",
      "sentry", "total_km", "month_km", "wltc_total", "charge_voltage",
      "charge_current", "pack_voltage", "total_kwh"];
    const parts = fields.map((f) => this.state(f));
    return JSON.stringify(parts) + "|" + Math.floor(Date.now() / 60000);
  }

  /* ---------- 渲染 ---------- */
  _build() {
    const root = this.shadowRoot;
    while (root.firstChild) root.removeChild(root.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; root.appendChild(st);
    const card = document.createElement("ha-card");
    card.innerHTML = '<div class="body"></div>';
    root.appendChild(card);
    this._body = card.querySelector(".body");
    this._built = true;
    this._render();
  }

  _render() {
    if (!this._built || !this._body) return;
    // ★ 2026-10-17 车主：「概览卡片下面有个更多数据，建议默认展开」
    //   初次渲染默认展开；用户手动开合后（details 已存在）沿用其状态。
    const _prev = this._body.querySelector("details");
    const open = _prev ? _prev.open : true;

    const online = this.state("online");
    const onlineOn = online === "在线" || online === "on" || online === "true";
    const onlineOff = online === "离线" || online === "off" || online === "false";
    const sentry = this.state("sentry");
    const acState = this.state("ac");
    const charge = this.state("charge_status");
    const drive = this.state("status");

    const w = (v) => Math.max(0, Math.min(100, v || 0));

    // pct=null 表示该实体不是百分比（例如油量若按升上报）→ 只显示带单位的数值，不画误导性进度条
    const meter = (label, field, rangeField, color, pct) => `
      <section class="meter ${color}">
        <div class="meter-top"><span>${label}</span><strong>${this.num(field) === null ? "—"
          : pct === null ? `${this.fmt(field, 1)}<small> ${this._unit(field) || ""}</small>`
          : `${this.fmt(field)}<small> %</small>`}</strong></div>
        ${pct === null ? "" : `<div class="track" role="meter" aria-label="${label}" aria-valuemin="0" aria-valuemax="100"
             aria-valuenow="${pct}"><i style="width:${w(pct)}%"></i></div>`}
        <div class="range"><span>${color === "electric" ? "纯电续航" : "燃油续航"}</span>
          <b>${this.fmt(rangeField)} <small>km</small></b></div>
      </section>`;

    const tire = (field, label) => {
      const p = this._pressure(field);          // ★ kPa → bar（之前直接显示 kPa 数值当 bar）
      const bad = p.v !== null && p.v > 0 && (p.v < 2.0 || p.v > 2.9);   // 与健康页同阈值
      // 低压时多给一位小数，避免"显示 2.0 却标黄"的困惑（如 1.977 bar）
      const txt = p.v === null ? "—" : (bad && p.v < 2.0 ? p.v.toFixed(2) : p.v.toFixed(1));
      return `<div class="tire${bad ? " low" : ""}"><span>${label}</span>
        <b>${txt}</b><small>${p.unit}</small></div>`;
    };
    const stat = (label, value) =>
      `<div class="detail-stat"><span>${label}</span><b>${value}</b></div>`;
    const avail = (field, unit, d = 1) =>
      this.num(field) === null ? "暂未提供" : `${this.fmt(field, d)} ${unit}`;

    const updated = this._lastUpdated();
    const stale = !updated || (Date.now() - updated > 300000);
    const model = this._model();
    const series = this._config.series || model.series || "";
    const titleMain = "理想";
    const acText = acState === undefined ? "未知"
      : (acState === "off" ? "已关闭" : acState === "on" || acState === "auto" ? "运行中" : String(acState));
    const sentryText = sentry === "on" ? "哨兵开启" : sentry === "off" ? "哨兵关闭" : "哨兵未知";
    const chargeText = charge === undefined ? "充电状态未知" : String(charge);

    this._body.innerHTML = `
      <div class="main">
        <section class="identity">
          <div class="eyebrow">LI AUTO · 车辆总览</div>
          <div class="title">${titleMain}${series ? ` <b>${this.esc(series)}</b>` : ""}</div>
          <div class="subtitle">${this.esc(model.name || "数据来自理想汽车官方接口")}</div>
          <div class="badges">
            <span class="badge ${onlineOn ? "online" : onlineOff ? "offline" : ""}"><i class="dot"></i>${onlineOn ? "车辆在线" : onlineOff ? "车辆离线" : "在线状态未知"}</span>
            <span class="badge">${this.esc(drive || "状态未知")}</span>
            <span class="badge">${sentryText}</span>
          </div>
          <div class="art"><img alt="爱车车型示意图" src="${this.esc(this._config.image || "")}"></div>
          <div class="art-note">车型示意 · 以实车为准</div>
        </section>

        <section class="energy">
          <div class="range-main"><span>总续航</span>
            <b>${this.fmt("range_total")} <small>km</small></b></div>
          ${meter("电池电量", "battery", "range_elec", "electric", this._pct("battery"))}
          ${meter("油量", "fuel", "range_fuel", "fuel", this._pct("fuel"))}
          <div class="charge"><span>${this.esc(chargeText)}</span>
            <b>${this.num("charge_power") === null ? "—" : this.fmt("charge_power", 1) + " kW"}</b></div>
        </section>

        <section class="condition">
          <div class="section-label"><span>四轮胎压</span><small>车头 ↑</small></div>
          <div class="tire-grid">
            ${tire("tire_lf", "左前")}
            ${LixiangOverviewCard.TOP_CAR_SVG}
            ${tire("tire_rf", "右前")}
            ${tire("tire_lr", "左后")}
            ${tire("tire_rr", "右后")}
          </div>
          <div class="cabin">
            ${stat("车内温度", this.num("room_temp") === null ? "—" : this.fmt("room_temp", 1) + " °C")}
            ${stat("空调状态", acText)}
          </div>
        </section>
      </div>

      <div class="footer">
        <span class="${stale ? "stale" : "fresh"}"><i class="dot"></i>数据更新 ${this._fmtTime(updated)}${stale ? " · 数据较旧" : ""}</span>
        <span>总里程 ${this.fmt("total_km", 1)} km</span>
      </div>

      ${this._mapHtml()}

      <details class="details" ${open ? "open" : ""}>
        <summary>更多车辆数据</summary>
        <div class="detail-grid">
          ${stat("WLTC 总续航", avail("wltc_total", "km", 0))}
          ${stat("充电电压", avail("charge_voltage", "V", 0))}
          ${stat("充电电流", avail("charge_current", "A", 1))}
          ${stat("剩余充电时间", this.num("charge_remain") === null ? "—" : this.fmt("charge_remain", 0) + " 分钟")}
          ${stat("空调设定温度", this.num("target_temp") === null ? "—" : this.fmt("target_temp", 0) + " °C")}
          ${stat("电池包电压", avail("pack_voltage", "V", 0))}
          ${stat("本月里程", avail("month_km", "km", 1))}
          ${stat("累计充电量", avail("total_kwh", "kWh", 1))}
        </div>
        <div class="note">
          续航分别取自车辆上报的「总续航 / 纯电续航 / 燃油续航」，不混用或自行相加。
          胎压低于 2.0 bar 会标黄提示。数据较旧时请以车机及官方 App 为准。<br>
          实体由本集成的「自动发现」匹配（按实体中文名），个别字段可用卡片配置里的
          <code>entities:</code> 手动指定。
        </div>
      </details>`;
    if (!this._artDone) { this._artDone = true; this._loadArt(); }
    this._wireMap();   // ★ 每次渲染都要重新喂（innerHTML 重建后瓦片容器是新元素）
    this._paintArt();  // ★ 同理：车图 <img> 也是每次重画新建的，必须重新贴 src
  }

  /** 车辆位置地图
   *
   * ★ 2026-10-18 由 HA 官方 `ha-map` 改为**自绘高德瓦片**：
   *   ha-map 的瓦片走 HA 代理 /api/map_tiles，上游不可达时整块空白
   *   （实测部分网络环境只解析到 IPv6 且无 IPv6 出口 → 代理 502 → 地图不显示）。
   *   车控「位置页」一直是自己拉高德瓦片（正常），故统一成同一套实现。
   *   实现见文件头的 _lonlatToTile / _amapTile / _renderTileMap。
   *
   * * 照顾其它车主（重要）：
   *   · 卡片配置 `show_map: false` 可完全关闭
   *   · **拿不到经纬度就不渲染**（没开定位 / 车型无该实体 / 数据缺失）→ 不出现空框或破图
   */
  _mapHtml() {
    if (this._config && this._config.show_map === false) return "";
    // ⚠️ _st() 收的是**字段名**（内部再 _eid 解析），不是实体 id ——
    //    传 id 进去会被当成字段名再解析一次 → 恒为 null（地图永远不出现）。
    const st = this._st("tracker");
    const a = st && st.attributes ? st.attributes : null;
    const lat = a ? a.latitude : null, lon = a ? a.longitude : null;
    if (lat == null || lon == null) return "";
    // ★ 2026-10-18：不再用 HA 官方 <ha-map>，改用与车控「位置页」一致的
    //   **自绘高德瓦片**。原因：ha-map 瓦片走 HA 代理 /api/map_tiles，
    //   上游不可达时整块空白（实测：该网络环境只解析到 IPv6 且无 IPv6 出口 →
    //   代理 502 → 地图不显示）。改为只依赖高德，与车控卡行为一致。
    return `<section class="mapsec">
              <div class="section-label"><span>车辆位置</span></div>
              <div class="lxmap"><div class="tiles"></div></div>
            </section>`;
  }

  /** ★ 2026-10-17 修「总览车模一会儿有一会儿没」
   *
   *  根因：`_render()` 用 innerHTML **整块重画**，模板里的车图 <img> 是
   *  `src="${config.image || ''}"` —— 用户没配图时就是 **src="" 的空元素**。
   *  而 `_loadArt()` 被 `_artDone` 只跑一次 → 重画后再没人给新 <img> 赋 src
   *  → **每重画一次，车图就消失一次**（定时器 60s + 任何状态更新都会触发）。
   *
   *  修法：把「贴 src」从「拉数据」里拆出来，每次渲染后都重新贴一次
   *  （URL 从 localStorage 取，纯内存操作，不发请求）。
   *  —— 与首页 `_loadCarImage` 同一策略，避免两边行为不一致。
   */
  _paintArt() {
    const img = this._body && this._body.querySelector(".art img");
    if (!img) return;
    let src = "", key = "";
    try {
      const o = JSON.parse(localStorage.getItem("lx_car_img_v1") || "{}");
      if (o && o.src) { src = o.src; key = o.key || ""; }
    } catch (e) {}
    // 用户显式配了图 → 模板里已经有 src，别覆盖
    if (!src && this._config && this._config.image) return;
    if (!src) {
      // 没有缓存也至少别留 src=""（否则浏览器会去请求当前页 URL）
      if (!img.getAttribute("src")) img.removeAttribute("src");
      return;
    }
    if (img.getAttribute("src") === src) { img.style.opacity = "1"; return; }
    img.dataset.lxReal = "1";
    img.style.opacity = "1";
    img.src = src;
    img.alt = "爱车车型示意图" + (key ? " · " + key : "");
    // 兜底：万一这次请求失败，600ms 后再带 ?v= 重试一次
    img.onerror = () => {
      if (img.dataset.lxRetried === "1") { img.style.opacity = "0"; return; }
      img.dataset.lxRetried = "1";
      setTimeout(() => {
        img.src = src + (src.indexOf("?") >= 0 ? "&" : "?") + "v=" + Date.now();
      }, 600);
    };
    img.onload = () => { img.style.opacity = "1"; delete img.dataset.lxRetried; };
  }

  /** 给 ha-map 注入 hass 与实体（innerHTML 之后调用） */
  _wireMap() {
    // ★ 2026-10-18：自绘高德瓦片（与车控「位置页」同一套实现，见 base.js）
    const box = this._body && this._body.querySelector(".lxmap .tiles");
    if (!box) return;
    const st = this._st("tracker");
    const a = st && st.attributes ? st.attributes : null;
    const lat = a ? Number(a.latitude) : NaN;
    const lon = a ? Number(a.longitude) : NaN;
    if (!isFinite(lat) || !isFinite(lon)) { box.innerHTML = ""; return; }
    _renderTileMap(box, lat, lon, 15, {
      w: box.clientWidth || 320,
      h: box.clientHeight || 190,
    });
  }

  /* 车图：config.image > 侧视 > 横版 > 竖版（后端 /lixiang_auto/car-image.json） */
  async _loadArt() {
    // ★ 2026-10-16 修「车图时有时无」：缓存优先 + JSON 重试 + img 带 ?v= 重试
    //   （与 app-home 的 _loadCarImage 同一套策略，共用缓存键 lx_car_img_v1）
    if (this._config.image) return;             // 用户显式指定 → 不覆盖
    if (this._artLoading) return;
    this._artLoading = true;
    const CK = "lx_car_img_v1";
    const put = (src, key) => {
      const img = this._body && this._body.querySelector(".art img");
      if (!img) return;
      if (img.dataset.lxReal === "1" && img.getAttribute("src") === src) return;
      img.dataset.lxReal = "1";
      delete img.dataset.lxRetried;
      img.onload = () => { img.style.opacity = "1"; };
      img.onerror = () => {
        if (img.dataset.lxRetried === "1") { img.style.opacity = "0"; return; }
        img.dataset.lxRetried = "1";
        const bust = src + (src.indexOf("?") >= 0 ? "&" : "?") + "v=" + Date.now();
        setTimeout(() => { img.src = bust; }, 600);
      };
      img.style.opacity = "1";
      img.src = src;
      img.alt = "爱车车型示意图" + (key ? " · " + key : "");
    };
    let hit = null;
    try { const o = JSON.parse(localStorage.getItem(CK) || "{}"); if (o && o.src) hit = o; } catch (e) {}
    if (hit) put(hit.src, hit.key);              // ① 缓存优先 → 秒出
    let data = null;
    for (let i = 0; i < 2 && !data; i++) {       // ② 失败重试一次
      try {
        const r = await fetch("/lixiang_auto/car-image.json", { cache: "no-store" });
        if (r.ok) data = await r.json();
      } catch (e) { /* 保持空图，不显示破图 */ }
      if (!data && i === 0) await new Promise((res) => setTimeout(res, 1500));
    }
    this._artLoading = false;
    if (!data || !data.ok) {
      if (!hit) setTimeout(() => { if (this.isConnected) this._loadArt(); }, 5000);
      return;
    }
    const d = data.side || data.horizontal || data.vertical || null;
    const src = d && d.static ? d.static : "";
    if (!src) return;
    if (!hit || hit.src !== src) put(src, data.color_code);
    try { localStorage.setItem(CK, JSON.stringify({ src, key: data.color_code || "", t: Date.now() })); } catch (e) {}
  }

  static getConfigElement() { return null; }
  static getStubConfig() { return {}; }
}

/* 车辆俯视示意（车头向上）——胎压网格中间那辆车 */
LixiangOverviewCard.TOP_CAR_SVG = `
  <svg class="top-car" viewBox="0 0 80 160" role="img" aria-label="车辆俯视示意，车头向上">
    <defs>
      <linearGradient id="lxbody" x2="1" y2="1">
        <stop stop-color="#9fb0c6"/><stop offset=".5" stop-color="#4f6076"/><stop offset="1" stop-color="#94a3b8"/>
      </linearGradient>
    </defs>
    <rect x="3" y="27" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <rect x="68" y="27" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <rect x="3" y="110" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <rect x="68" y="110" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <path d="M13 23 Q14 5 40 5 Q66 5 67 23 L67 137 Q65 154 40 155 Q15 154 13 137Z"
          fill="url(#lxbody)" stroke="#c3cddb" stroke-width="1"/>
    <path d="M20 47 Q40 37 60 47 L57 68 L23 68Z" fill="#182a3c" stroke="#91a5bc"/>
    <path d="M23 73 H57 L58 110 Q40 119 22 110Z" fill="#22344a" stroke="#8196ad"/>
    <path d="M22 117 Q40 126 58 117 L58 131 Q40 141 22 131Z" fill="#1b2a3d"/>
    <path d="M21 15L33 12M47 12L59 15" stroke="#dde8ef" stroke-width="3" stroke-linecap="round"/>
    <path d="M24 145Q40 149 56 145" stroke="#4C9AFF" stroke-width="2" fill="none"/>
  </svg>`;

// 无 DOM 环境（Node 单测）下安全：只在浏览器注册自定义元素
if (typeof customElements !== "undefined" && !customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, LixiangOverviewCard);
}
if (typeof window !== "undefined") {
  window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
if (!window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
    type: CARD_TAG,
    name: "理想汽车 · 车辆总览",
    description: "电量 / 续航 / 胎压 / 车况的只读总览卡（深色玻璃风格，实体自动发现，零配置）",
    preview: true,
  });
}
})();

/* ===================== lixiang-app.js ===================== */
(function () {

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
/**
 * 理想汽车 · 总入口卡片（一张卡片承载全部页面）
 *
 * ★★ 2026-10-11 为什么做这个
 * ------------------------------------------------------------------
 * 原先用户要用上这套 UI 需要：
 *   · 注册 **14 个资源**（13 张卡片 + auto-bind 引擎）
 *   · 建 **13 个 dashboard 视图**（每张卡片一个）
 *   · 加 13 次卡片
 *   = 27 次手工操作 —— 普通用户根本折腾不下来。
 *
 * 现在只需三步：
 *   ① 注册 1 个资源（本文件）
 *   ② 建 1 个视图
 *   ③ 加 1 张卡片：`type: custom:lixiang-app`
 *
 * 工作原理
 * --------
 * · 本卡片在内部**动态 import 全部子卡片**（用 import.meta.url 解析相对路径，
 *   所以无论从 /lixiang_auto/… 还是 /local/lixiang-cards/… 加载都能找到同级文件）
 * · 子卡片仍是标准自定义元素，本卡片按需创建并切换显示
 * · 导航：子卡片派发 `lx-navigate` 事件 → 本卡片拦截并切换内部页面
 *   （子卡片保留了「未被拦截则回退 HA 路由」的旧行为，所以**多视图用法仍然可用**）
 *
 * 配置
 * ----
 * ```yaml
 * type: custom:lixiang-app
 * # 可选：起始页（默认 app）
 * page: app
 * # 可选：多车时指定
 * vin: HLX32XXXXXXXXXXXX
 * # 可选：传给子卡片的原始配置（高级用法）
 * child: { ... }
 * ```
 */

const CARD_TAG = "lixiang-app";

/** 内部页面表：路径片段 → 子卡片自定义元素名 */
const PAGES = {
  app: "lixiang-app-home",
  charge: "lixiang-charge-page",
  energy: "lixiang-energy-page",
  health: "lixiang-health-page",
  setting: "lixiang-setting-page",
  scene: "lixiang-scene-page",
  climate: "lixiang-climate-page",
  seat: "lixiang-seat-page",
  location: "lixiang-location-page",
  vinfo: "lixiang-vehicle-info-page",
  task: "lixiang-task-page",
  ad: "lixiang-ad-page",
  bindings: "lixiang-bindings-card",
};

/** 全部子卡片文件名（用于动态加载） */
const CARD_FILES = Object.values(PAGES);

/** 加载状态：全局一次即可（多个总卡片实例共享） */
let __loading = null;

function _loadCards() {
  if (__loading) return __loading;
  // ★ 用 import.meta.url 解析同级目录 —— 兼容 /lixiang_auto/… 与 /local/… 两种部署
  const base = new URL(".", import.meta.url).href;
  // ★ 2026-10-14：单文件版（lixiang-all.js）可能已经定义了这些元素 ——
  //   已定义的不再逐个 import（省 13 个请求，也避免重复定义）。
  const pending = CARD_FILES.filter((name) => !customElements.get(name));
  __loading = Promise.all(
    pending.map((name) =>
      import(/* @vite-ignore */ `${base}${name}.js`).catch((e) => {
        // 单个卡片加载失败不应拖垮整体：其余页面照常可用
        console.warn(`[lixiang-app] 子卡片加载失败: ${name}`, e);
      })
    )
  ).then(() => {
    // 自动绑定引擎（可选，缺失时子卡片会自行降级）
    return import(/* @vite-ignore */ `${base}lixiang-auto-bind.js`).catch(() => {});
  });
  return __loading;
}

class LixiangApp extends HTMLElement {
  constructor() {
    super();
    this._built = false;
    this._instances = {};   // 元素名 → 已创建的子卡片
    this._current = null;   // 当前页面 key
    this._mount = null;
  }

  setConfig(config) {
    this._config = config || {};
  }

  /** 在多视图用法下，HA 会把 URL 变化转成 hass 更新；这里同步一下内部页 */
  set hass(h) {
    this._hass = h;
    if (!this._built) {
      this._build();
      return;
    }
    this._syncFromUrl();
    this._pushHass();
  }

  get hass() { return this._hass; }

  /** 子卡片读取父级配置里的 vin 等 */
  get config() { return this._config || {}; }

  async _build() {
    if (this._built) return;
    this._built = true;

    // 事件：子卡片请求导航（cancelable → preventDefault 表示"父级已处理"）
    this.addEventListener("lx-navigate", (e) => {
      const key = this._keyOf(e.detail && e.detail.path);
      if (!key) return;           // 不认识 → 不拦截，让子卡片回退 HA 路由
      e.preventDefault();
      this.show(key);
    });

    // ★ 导航拦截：子卡片一律用 `history.pushState(null,"",p)` + `location-changed`
    //   跳转（12 个文件写法完全一致）。与其改 12 个文件，不如在这里把
    //   **能映射到内部页面的 URL** 拦下来做内部切换 —— 子卡片零改动。
    //   非本卡片的 URL（HA 自己的导航）原样放行，且断开时恢复原函数。
    this._installNavHook();

    // 容器
    this._mount = document.createElement("div");
    this._mount.style.cssText = "display:block;";
    this.appendChild(this._mount);

    // 先显示加载态，避免白屏
    this._mount.innerHTML =
      '<div style="padding:24px;text-align:center;color:var(--lx-t3,#999);'
      + 'font-size:13px">正在加载理想汽车卡片…</div>';

    await _loadCards();

    const start = this._config && this._config.page;
    this.show(PAGES[start] ? start : this._initialKey());
  }

  _installNavHook() {
    const self = this;
    if (!window.__lxNavHook) {
      const orig = history.pushState.bind(history);
      window.__lxNavOrigPush = orig;
      window.__lxNavRefs = 0;
      window.__lxNavTargets = new Set();
      window.__lxNavHook = function (state, title, url) {
        const path = String(url == null ? "" : url);
        for (const t of window.__lxNavTargets) {
          const k = t._keyOf(path);
          if (k) {
            // 内部处理：不改 URL（避免 HA 去切换不存在的视图）
            t.show(k);
            return undefined;
          }
        }
        return orig(state, title, url);
      };
      history.pushState = window.__lxNavHook;
    }
    window.__lxNavRefs += 1;
    window.__lxNavTargets.add(this);
  }

  _removeNavHook() {
    if (!window.__lxNavHook) return;
    window.__lxNavTargets.delete(this);
    window.__lxNavRefs -= 1;
    if (window.__lxNavRefs <= 0 && window.__lxNavOrigPush) {
      history.pushState = window.__lxNavOrigPush;
      window.__lxNavHook = null;
      window.__lxNavTargets = new Set();
    }
  }

  disconnectedCallback() {
    this._removeNavHook();
  }

  /** 从 URL 推断初始页（URL 是 /lixiang/charge 或卡片所在视图的 path） */
  _initialKey() {
    const k = this._keyOf(window.location.pathname);
    return k || "app";
  }

  /** 把路径片段映射到页面 key（兼容 "/lixiang/charge" 与 "charge"） */
  _keyOf(path) {
    if (!path || typeof path !== "string") return null;
    const seg = path.split("/").filter(Boolean).pop();
    if (seg && PAGES[seg]) return seg;
    const last = path.split("/").filter(Boolean);
    for (let i = last.length - 1; i >= 0; i--) {
      if (PAGES[last[i]]) return last[i];
    }
    return null;
  }

  /** 切到某个页面（key 必须是 PAGES 的键） */
  show(key) {
    if (!PAGES[key] || !this._mount) return;
    if (this._current === key) return;
    this._current = key;

    // 只创建一次，之后复用（保留子卡片的内部状态，如滚动位置/已展开月份）
    const tag = PAGES[key];
    let el = this._instances[tag];
    if (!el) {
      el = document.createElement(tag);
      try {
        el.setConfig(this._childConfig());
      } catch (e) {
        console.warn(`[lixiang-app] ${tag} setConfig 失败`, e);
      }
      this._instances[tag] = el;
    }
    this._mount.replaceChildren(el);

    // 同步 hass（子卡片依赖它渲染）
    this._pushHass();
  }

  _childConfig() {
    const c = this._config || {};
    const base = Object.assign({}, c.child || {});
    if (c.vin) base.vin = c.vin;
    return base;
  }

  _pushHass() {
    if (!this._hass) return;
    Object.values(this._instances).forEach((el) => {
      try {
        el.hass = this._hass;
      } catch (e) {
        // 单个子卡片异常不影响其他
        console.warn("[lixiang-app] 传递 hass 失败", e);
      }
    });
  }

  /** 多视图用法：URL 变了就同步内部页（本卡片仍在同一视图内时也生效） */
  _syncFromUrl() {
    const k = this._keyOf(window.location.pathname);
    if (k && k !== this._current) this.show(k);
  }

  getCardSize() { return 12; }

  static getStubConfig() { return {}; }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangApp);

window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
if (!window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "理想汽车 · 全部页面",
  description: "一张卡片承载理想 App 风格的全部页面（首页/充电/能耗/空调/座椅/位置/设置/情景/任务等）",
  preview: false,
});
})();

/* ===================== lixiang-assets.js ===================== */
(function () {

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
 * lixiang-assets.js —— 车型资源解析（适用所有车型的资源层）
 *
 * ★ 设计目标：卡片**不按车型分支**，只问「这辆车该用哪张图」，拿不到就逐级回退，永不空屏。
 *
 * 三级回退链（顺序即优先级）：
 *   ① 用户本地专属图   <config>/www/lixiang_auto/cars/<modelId>.{png,webp,jpg,svg}  （经 /local/ 访问）
 *   ② 内置车系剪影     L 系（L6/L7/L8/L9  SUV）/ W 系（MEGA、i8  MPV）/ M 系（理想ONE）
 *   ③ 通用占位剪影     任何车型都至少有这个兜底
 *
 * ★ 为什么内置剪影而不是官方图：
 *   · 官方车型图只编译在 App 本体里（res/assets 均无法直接取得，也没有 CDN 地址）
 *   · 随集成分发官方素材有版权风险
 *   · 自制剪影体积小、可版本控制、对 unknown/新车型天然可用
 *
 * ★ 持久化：
 *   · 内置剪影：随集成版本分发（`www/lixiang-cards/`，HACS 更新即刷新）
 *   · 用户专属图：放 `<config>/www/lixiang_auto/cars/`，用户自己维护，集成升级不会丢
 *
 * ★ 缓存：资源 URL 会带上版本号（`window.__LX_ASSET_V__`），
 *   由集成侧 `/lixiang_auto/asset-version.js` 注入 —— 版本变了浏览器就会重新拉取。
 */
(function () {
  const CANDIDATE_EXTS = ['png', 'webp', 'jpg', 'svg'];

  // 用户自定义车型图目录（HA 的 www 目录 → /local/）
  const USER_CAR_DIR = '/local/lixiang-cars';   // 与 /local/lixiang-icons 同一约定

  function assetV() {
    try {
      return (typeof window !== 'undefined' && window.__LX_ASSET_V__) || '0';
    } catch (_) {
      return '0';
    }
  }

  /** 给资源 URL 加版本号查询串（cache-buster） */
  function vurl(url) {
    const v = assetV();
    if (!url || v === '0') return url;
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'v=' + encodeURIComponent(v);
  }

  /**
   * 派生车系（L / W / M / generic）。
   * 三个线索任一即可：unityModel（最准）→ 车型名（"理想L6" / "MEGA" / "理想ONE"）→ 都没有则 generic。
   * 这样即使拿不到能力表（modelId/unityModel 缺失），卡片也不会白屏。
   */
  function seriesOf(unityModel, modelName) {
    const u = String(unityModel || '').toUpperCase();
    if (u.startsWith('M')) return 'M';       // M01A / M01B —— 理想ONE
    if (u.startsWith('W')) return 'W';       // W01/W02/W04… —— MEGA / i8
    if (u.startsWith('L')) return 'L';       // L6 / L7 / L8 / L9
    const n = String(modelName || '');
    if (/理想\s*ONE|ONE/i.test(n)) return 'M';
    if (/MEGA|i8/i.test(n)) return 'W';
    if (/L\s*[6-9]/i.test(n)) return 'L';
    return 'generic';
  }

  /* ---- 内置车系剪影（内联 SVG data URI，离线可用、无外部依赖） ---- */
  // 说明：这是**示意剪影**（侧面轮廓），不是官方车型图。
  function svgDataUri(body) {
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 100" width="240" height="100">' +
      '<g fill="currentColor">' + body + '</g></svg>';
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  const SILHOUETTE = {
    // L 系：SUV（较高车身、短前悬）
    L: svgDataUri(
      '<path d="M18 74 q10-30 34-33 q16-2 26-12 q10-10 30-11 q26-1 40 8 l30 12 q16 6 26 16 l8 20 z"/>' +
      '<circle cx="62" cy="76" r="13"/><circle cx="176" cy="76" r="13"/>'
    ),
    // W 系：MPV（长车身、平直车顶）
    W: svgDataUri(
      '<path d="M12 72 q6-26 26-28 l120-4 q30 0 44 12 l14 18 v22 z"/>' +
      '<circle cx="58" cy="76" r="12"/><circle cx="182" cy="76" r="12"/>'
    ),
    // M 系：理想ONE（更方正的早期 SUV 轮廓）
    M: svgDataUri(
      '<path d="M16 74 q8-28 30-30 q18-2 28-10 q10-8 28-9 q24-1 38 9 l26 12 q14 6 22 14 l6 14 z"/>' +
      '<circle cx="60" cy="76" r="13"/><circle cx="170" cy="76" r="13"/>'
    ),
    // 通用占位：最简车身 + 两个轮子
    generic: svgDataUri(
      '<path d="M20 72 q8-24 28-26 q16-2 26-9 q10-7 26-8 q22-1 34 8 l22 11 q12 5 18 12 l4 12 z"/>' +
      '<circle cx="58" cy="76" r="12"/><circle cx="168" cy="76" r="12"/>'
    ),
  };

  /**
   * 车图候选列表（有序，越靠前越优先）。
   * @param {string} modelId     车型 modelId（服务端下发）
   * @param {string} unityModel  能力表里的 unityModel（L6 / W02 / M01B…），可为空
   * @returns {string[]} 候选 URL 列表
   */
  function carImageCandidates(info) {
    info = info || {};
    const modelId = info.modelId || '';
    const unityModel = info.unityModel || '';
    const modelName = info.modelName || '';
    const series = seriesOf(unityModel, modelName);

    // 用户本地图的查找键：modelId 优先，其次 unityModel，最后车系名 —— 与内置剪影之间还要插一次「车系图」以便用户只放一张就能覆盖整个车系
    const keys = [];
    for (const k of [modelId, unityModel, series === 'generic' ? '' : series]) {
      if (k && keys.indexOf(k) < 0) keys.push(k);
    }

    const out = [];
    for (const k of keys) {
      for (const ext of CANDIDATE_EXTS) {
        out.push(vurl(USER_CAR_DIR + '/' + k + '.' + ext));
      }
    }
    out.push(SILHOUETTE[series] || SILHOUETTE.generic);
    out.push(SILHOUETTE.generic);
    return out.filter((u, i) => out.indexOf(u) === i);
  }

  /**
   * 生成「逐级回退」的 <img>：加载失败自动换下一个候选，全失败则隐藏（不留破图图标）。
   * @param {string} modelId
   * @param {string} unityModel
   * @param {object} [opts] {cls, alt, style}
   */
  function carImageHtml(info, opts) {
    opts = opts || {};
    const list = carImageCandidates(info);
    const cls = opts.cls ? ' class="' + opts.cls + '"' : '';
    const style = opts.style ? ' style="' + opts.style + '"' : '';
    const alt = opts.alt != null ? opts.alt : '';
    // onerror 里推进到下一个候选；用尽则隐藏
    return (
      '<img' + cls + style + ' src="' + list[0] + '" alt="' + alt + '" ' +
      'data-lx-candidates="' + encodeURIComponent(JSON.stringify(list)) + '" ' +
      'onerror="window.__lxCarFallback&&window.__lxCarFallback(this)">'
    );
  }

  /** onerror 处理器：换下一个候选；用尽则隐藏元素 */
  function carFallback(img) {
    try {
      let idx = Number(img.dataset.lxIdx || 0) + 1;
      const list = JSON.parse(decodeURIComponent(img.dataset.lxCandidates || '[]'));
      if (idx < list.length) {
        img.dataset.lxIdx = String(idx);
        img.src = list[idx];
        return;
      }
      img.style.visibility = 'hidden';
    } catch (_) {
      img.style.visibility = 'hidden';
    }
  }

  const api = {
    assetV: assetV,
    vurl: vurl,
    seriesOf: seriesOf,
    SILHOUETTE: SILHOUETTE,
    carImageCandidates: carImageCandidates,
    carImageHtml: carImageHtml,
    carFallback: carFallback,
  };

  if (typeof window !== 'undefined') {
    window.LxAssets = api;
    window.__lxCarFallback = carFallback;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
})();

/* ===================== lixiang-auto-bind.js ===================== */
(function () {

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
/**
 * lixiang-auto-bind —— 实体自动发现引擎（供所有理想卡片复用）
 *
 * 设计目标：用户**不用手填 90 个实体 ID**。
 *   配置只需（任选其一）：
 *     · vin: HLX32XXXXXXXXXXXX      ← 最精确
 *     · 或什么都不填（自动认领第一辆理想车）
 *
 * 原理：
 *   ① 从 hass.entities（实体注册表）按 platform==='lixiang_auto' 过滤
 *   ② 用【中文名】匹配（original_name），而非实体 ID 字符串
 *      —— 实体 ID 里的拼音会随 HA 版本/语言变化，中文名稳定
 *   ③ 用 device_id 归属校验（多车时不会串）
 *
 * 匹配策略（三道，逐级放宽）：
 *    exact  完全等于 name
 *    contains 包含 name
 *    regex  正则
 */

const AUTO_BIND = {
  /* ── 车辆标识 ── */
  _meta: { platform: "lixiang_auto" },

  /* ── 字段映射表 ─────────────────────────────────────────────
   * 值可以是：
   *   "充电上限"                  → 精确名
   *   ["充电上限", "电池充电上限"] → 多个候选名（按序尝试）
   *   { any: ["充电", "上限"] }   → 必须同时包含（更稳）
   *   { re: "^充电.*上限$" }      → 正则
   *   { domain: "lock" }          → 只要域名匹配即取（唯一时）
   * ──────────────────────────────────────────────────────────── */
  fields: {
    /* 顶部状态 */
    title:          { meta: true },                      // 由车型名生成
    range_elec:     ["纯电续航(CLTC)", "纯电续航(CLTC)", "纯电续航"],
    range_fuel:     ["燃油续航(CLTC)", "燃油续航"],
    range_total:    ["总续航(CLTC)", "总续航"],
    /* ★ 2026-10-13：总览卡新增 */
    fuel:           ["油量"],
    wltc_total:     ["总续航(WLTC)"],
    wltc_elec:      ["纯电续航(WLTC)"],
    wltc_fuel:      ["燃油续航(WLTC)"],
    charge_voltage: ["交流充电电压", "OGC 充电电压"],
    charge_current: ["交流充电电流", "OGC 充电电流"],
    battery:        ["电池电量"],
    status:         { any: ["行驶", "状态"] },            // 行驶状态
    online:         ["在线状态"],
    /* 里程 */
    month_km:       ["本月里程", "本月陪伴里程"],
    partner_km:     ["陪伴里程"],
    partner_days:   ["陪伴天数"],
    total_km:       ["总里程"],
    ad_km:          ["辅助驾驶里程"],
    ad_days:        ["辅助驾驶天数"],
    noa_km:         ["NOA 里程", "NOA里程"],
    lcc_km:         ["LCC 里程", "LCC里程"],
    acc_km:         ["ACC 里程", "ACC里程"],
    /* 空调 */
    room_temp:      ["车内温度"],
    target_temp:    ["空调设定温度"],
    ac:             { domain: "climate" },
    /* 位置 */
    address:        ["位置服务"],
    tracker:        { domain: "device_tracker" },
    /* 充电 */
    charge_status:  ["充电状态"],
    charge_complete:["充电完成状态"],
    charge_limit:   ["充电上限"],
    // ★ 2026-10-14 官方充电管理页：上限要能"拖"→ 必须拿到 number 实体
    limit_num:      { name: "充电上限", domain: "number" },
    limit_sensor:   { name: "充电上限", domain: "sensor" },
    appt_sw:        { name: "预约充电", domain: "switch" },
    end_time:       { name: "充电结束时间", domain: "time" },
    start_time:     { name: "充电开始时间", domain: "time" },
    charge_mode:    ["充电模式"],
    // ★ 2026-10-14：总览卡的「充电功率」用它（派生实体，kW，V×A）
    charge_power:   { name: "充电功率", domain: "sensor" },
    // 充电效率（CLTC/WLTC，km/h）—— 充电页顶部指标用 power 字段
    charge_eff:     ["充电效率(CLTC)", "充电效率(WLTC)"],
    charge_remain:  ["剩余充电时间"],
    ac_gun:         ["交流充电枪"],
    dc_gun:         ["直流充电枪"],
    port_cover:     ["充电口盖"],
    fault_charge:   ["充电故障"],
    appointment:    ["预约充电"],
    month_kwh:      ["本月充电量"],
    total_kwh:      ["累计充电量"],
    /* 健康 */
    tire_lf:        ["胎压 左前"],
    tire_rf:        ["胎压 右前"],
    tire_lr:        ["胎压 左后"],
    tire_rr:        ["胎压 右后"],
    temp_lf:        ["胎温 左前"],
    temp_rf:        ["胎温 右前"],
    temp_lr:        ["胎温 左后"],
    temp_rr:        ["胎温 右后"],
    warn_lf:        ["胎压告警 左前"],
    warn_rf:        ["胎压告警 右前"],
    warn_lr:        ["胎压告警 左后"],
    warn_rr:        ["胎压告警 右后"],
    pack_voltage:   ["电池包电压"],
    fault_dcdc:     ["DCDC 故障"],
    /* 场景 */
    scene_mode:     ["场景模式"],
    /* 里程能耗页字段 */
    ac_temp:        ["空调设定温度"],
    aqi:            ["空气污染指数"],
    /* 座椅（9 个 fan + 方向盘加热）*/
    steer_heat:     { name: "方向盘加热", domain: "switch" },
    seat_fl_heat:   { name: "主驾座椅加热", domain: "fan" },
    seat_fl_vent:   { name: "主驾座椅通风", domain: "fan" },
    seat_fr_heat:   { name: "副驾座椅加热", domain: "fan" },
    seat_fr_vent:   { name: "副驾座椅通风", domain: "fan" },
    seat_rl_heat:   { name: "二排左座椅加热", domain: "fan" },
    seat_rl_vent:   { name: "二排左座椅通风", domain: "fan" },
    seat_rc_heat:   { name: "二排中座椅加热", domain: "fan" },
    seat_rr_heat:   { name: "二排右座椅加热", domain: "fan" },
    seat_rr_vent:   { name: "二排右座椅通风", domain: "fan" },
    /* 位置页 */
    /* ★ 2026-10-14：车辆信息页（二级）用 —— 车机版本 / OTA（官方 VehicleSetting / VehicleOtaPage 的落点） */
    head_unit_ver:  { name: "整车软件版本", domain: "sensor" },
    head_unit_ver_old: { name: "车机版本", domain: "sensor" },
    ota_version:    { name: "OTA 版本(简)", domain: "sensor" },
    ota_status:     { name: "OTA 状态", domain: "sensor" },
    ota_progress:   { name: "OTA 进度", domain: "sensor" },
    photo_info:     { any: ["360", "拍照", "信息"], domain: "sensor" },
    photo_status:   { any: ["360", "拍照", "状态"], domain: "sensor" },
    vehicle_cfg:    ["车辆配置"],
    /* 保养 */
    maint_sparkplug:      { name: "火花塞" },
    maint_acfilter:       { name: "空调滤芯" },
    maint_brake_oil:      { name: "刹车油" },
    maint_coolfuild:      { name: "冷却液" },
    maint_engine_oil:     { name: "机油" },
    maint_engine_level2:  { name: "保养二级" },
    elec_km:        ["耗电行驶"],
    fuel_l:         ["本月耗油量", "耗油总量"],
    partner_days:   ["陪伴天数"],
    /* 充电页兼容别名（卡片用短名，引擎用长名）*/
    status_charge:  ["预约充电状态", "充电状态"],
    complete:       ["充电完成状态"],
    limit:          ["充电上限"],
    mode:           ["充电模式", "预约充电模式"],
    power:          ["充电效率(CLTC)", "充电效率(WLTC)"],
    remain:         ["剩余充电时间"],
    soc:            ["电池电量"],
    // ★ 2026-10-11：App 首页充电卡显示「剩余2小时25分钟」——
    //   对应 VSS 信号 Vehicle.Powertrain.Battery.ChargeSurplusTime（剩余充电时间，min）
    remain_time:    ["剩余充电时间", "剩余时间", "充电剩余"],
    fault:          ["充电故障"],
    month_times:    null,   // 集成无「次数」实体 → 由卡片从月度统计算（见 charge-page）
    /* 健康页别名 */
    lv_battery:     { any: ["低压", "电源"] },
    fault_stop:     { any: ["故障", "停止充电"] },
    /* 快捷按钮（按域名 + 名称）*/
    lock:           { domain: "lock" },
    window:         { name: "车窗", domain: "cover" },
    trunk:          { name: "尾门", domain: "cover" },
    /* ★ 2026-10-09 修正：首页「授权驾驶」按钮此前绑到 binary_sensor（车辆授权，只读）
       → 点击只会弹「只读，无法控制」。集成里真实的可执行实体是
       button.<车名>_授权驾驶（cmdKey=remoteVehAuth）。

       ★ 2026-10-17：auth_state（binary_sensor「车辆授权」= Vehicle.Provision.Authorize.State）
         **不再用于判断"已授权"** —— 那是这台车与账号的绑定关系，长期为 on，
         会让标签和圆点永远显示"已授权/已启动"。官方的依据是 LXVehicleBLEConnectState
         （蓝牙连接状态，一次性），我们集成没有该信号。字段保留仅供手动配置使用。 */
    auth:           { name: "授权驾驶", domain: "button" },
    auth_state:     { name: "车辆授权", domain: "binary_sensor" },
    find:           { name: "寻车", domain: "button" },
    /* ★ 2026-10-09 修正：后视镜加热此前绑 binary_sensor 且用 any 分支（会命中只读的
       sensor「左后视镜」）→ 按钮点不动。真正的控制在 switch「后视镜加热」（rmCtrl）。 */
    mirror:         { name: "后视镜加热", domain: "switch" },
    /* ★ 2026-10-09 新增：充电口盖控制（cpCtrl）。注意与只读的
       binary_sensor「充电口盖」（port_cover，用于充电页展示）区分开。 */
    port:           { name: "充电盖", domain: "switch" },
    /* 设置（可控制）*/
    sentry:         { name: "哨兵模式", domain: "switch" },
    ac_fast_hot:    { name: "快速制热", domain: "switch" },
    ac_fast_cold:   { name: "快速制冷", domain: "switch" },
    /* ★ 2026-10-09 修正：switch 实体名是「除雪除冰」，不是「除霜」；
       原 any:["除霜"] 会命中只读的 sensor「除霜模式」→ 空调页按钮点不动。 */
    ac_defrost:     { name: "除雪除冰", domain: "switch" },
    steer_heat:     { name: "方向盘加热", domain: "switch" },
    batt_warm:      { name: "电池保温", domain: "switch" },
    /* 远程操作 */
    btn_find:       { name: "寻车", domain: "button" },
    /* ★ 2026-10-09 修正：button 实体名是「授权驾驶」（旧规则找「远程启动」永远无命中）*/
    btn_start:      { name: "授权驾驶", domain: "button" },
    btn_flash:      { name: "闪灯", domain: "button" },
    btn_horn:       { name: "鸣笛", domain: "button" },
    btn_photo:      { name: "远程拍照", domain: "button" },
  },
};

/* ─────────────────────────── 引擎实现 ─────────────────────────── */

class LixiangAutoBind {
  constructor(hass, config) {
    this._hass = hass;
    this._config = config || {};
    this._cache = null;
  }

  /** 主入口：返回 { fieldName: entity_id } */
  resolve() {
    if (this._cache) return this._cache;
    const h = this._hass;
    if (!h || !h.entities) { this._cache = {}; return this._cache; }

    // ① 圈定本集成的实体
    const pool = this._pool();
    if (!pool.length) { this._cache = {}; return this._cache; }

    // ② 逐字段匹配
    const out = {};
    for (const [field, rule] of Object.entries(AUTO_BIND.fields)) {
      if (rule && rule.meta) continue;
      if (rule == null) continue;   // 显式禁用该字段
      const hit = this._match(field, rule, pool);
      if (hit) out[field] = hit;
    }
    this._cache = out;
    return out;
  }

  /** 池：本集成的实体（可被 vin 进一步收窄）*/
  _pool() {
    const h = this._hass;
    const vin = this._config.vin || "";
    let devIds = null;
    if (vin) {
      devIds = new Set(
        Object.values(h.devices || {})
          .filter((d) => (d.identifiers || []).some((i) => String(i).includes(vin)))
          .map((d) => d.id)
      );
    }
    const list = [];
    for (const e of Object.values(h.entities)) {
      // ★ 2026-10-18 修「两辆车时总览卡地图不显示」
      //   `e.platform === "lixiang_auto"` **不区分车** → 两辆车的同名实体
      //   （都叫「车辆位置」「车锁」…）一起进池 → 匹配命中哪辆不确定 →
      //   可能拿到【另一辆】没有位置的实体 → _mapHtml 的 lat/lon 为 null
      //   → 整段 return "" → 地图消失（删掉一辆就正常）。
      //   修法：**有 vin 且能定位到该车设备时，只收该车的实体**。
      const scoped = !!(vin && devIds && devIds.size);
      const byDevice = !!(devIds && devIds.has(e.device_id));
      const isMine = scoped ? byDevice
                           : (e.platform === "lixiang_auto" || byDevice);
      if (!isMine) continue;
      if (scoped && !byDevice) continue;
      const st = h.states[e.entity_id];
      if (!st) continue;   // 未启用/不可用
      list.push({
        id: e.entity_id,
        name: e.original_name || e.name || "",
        domain: e.entity_id.split(".")[0],
        device: e.device_id,
      });
    }
    return list;
  }

  /** 单字段匹配（三道策略）*/
  /**
   * ★ 2026-10-18：多车同名实体消歧。
   *   多候选时**优先选状态有值（非 unknown/unavailable）的那个**；
   *   仍无法区分则返回 null（不猜，避免绑错车 —— 保持既有语义）。
   */
  _pick(cands) {
    if (!cands || !cands.length) return null;
    if (cands.length === 1) return cands[0].id;
    const h = this._hass || {};
    const usable = cands.filter((x) => {
      const st = h.states && h.states[x.id];
      if (!st) return false;
      const v = st.state;
      return v !== "unknown" && v !== "unavailable" &&
             v !== null && v !== undefined && v !== "";
    });
    if (usable.length === 1) return usable[0].id;
    return null;   // 消歧不出来 → 不猜（原有行为）
  }

  _match(field, rule, pool) {
    // 显式配置优先
    const explicit = this._config[field];
    if (typeof explicit === "string" && explicit.includes(".")) return explicit;

    // { domain: "lock" } —— 域名唯一匹配
    if (rule && typeof rule === "object" && rule.domain && !rule.name && !rule.any && !rule.re) {
      const cands = pool.filter((x) => x.domain === rule.domain);
      return cands.length === 1 ? cands[0].id : null;
    }

    // { name, domain } —— 名称 + 域名
    if (rule && typeof rule === "object" && rule.name) {
      const cands = pool.filter((x) =>
        (!rule.domain || x.domain === rule.domain) && x.name.includes(rule.name));
      return cands.length ? cands[0].id : null;
    }

    // { any: [...] } —— 必须同时包含
    //   ★ 2026-10-09 修复：此前忽略 rule.domain，导致 { any:["后视镜"], domain:"binary_sensor" }
    //     命中只读的 sensor「左后视镜」，卡片按钮点不动（真事故）。
    if (rule && typeof rule === "object" && rule.any) {
      const cands = pool.filter((x) =>
        (!rule.domain || x.domain === rule.domain) &&
        rule.any.every((w) => x.name.includes(w)));
      if (cands.length) return cands[0].id;
      return null;
    }

    // { re: "..." } —— 正则
    if (rule && typeof rule === "object" && rule.re) {
      const re = new RegExp(rule.re);
      const cands = pool.filter((x) => re.test(x.name));
      return cands.length ? cands[0].id : null;
    }

    // 字符串 或 数组 —— 精确名优先，再退到包含
    const names = Array.isArray(rule) ? rule : [rule];
    for (const want of names) {
      const exact = pool.find((x) => x.name === want);
      if (exact) return exact.id;
    }
    for (const want of names) {
      const part = pool.find((x) => x.name.includes(want));
      if (part) return part.id;
    }
    return null;
  }

  /**
   * 摘要（人可读，供 console / 诊断卡展示）。
   * 返回 { model, series, poolSize, matched, missing, version }
   */
  summary(detected) {
    const dg = this.diagnose();
    const ok = dg.fields.filter((f) => f.ok);
    const miss = dg.fields.filter((f) => !f.ok);
    return {
      model: (detected && detected.model) || "",
      series: (detected && detected.series) || "",
      poolSize: dg.poolSize,
      total: dg.fields.length,
      matched: ok.length,
      missing: miss.map((f) => f.field),
      rate: dg.fields.length
        ? ((ok.length / dg.fields.length) * 100).toFixed(1) + "%" : "0%",
      bindings: dg.fields.filter((f) => f.ok)
        .reduce((a, f) => (a[f.field] = f.entity, a), {}),
    };
  }

  /** console 打表（默认开启，便于用户/开发者排查；tags 传 false 可关）*/
  logToConsole(detected, enabled) {
    if (enabled === false) return;
    const sm = this.summary(detected);
    /* eslint-disable no-console */
    console.groupCollapsed(
      `%c[理想卡片] 自动发现 ${sm.matched}/${sm.total} (${sm.rate})` +
      (sm.model ? ` · ${sm.model}` : ""),
      "color:#0A58F6;font-weight:600");
    console.log("实体池:", sm.poolSize, "| 车系:", sm.series || "(未识别)");
    console.table(
      Object.entries(sm.bindings).map(([field, entity]) => ({ 字段: field, 实体: entity }))
    );
    if (sm.missing.length) {
      console.log("未匹配字段（该功能可能在本车型不存在）:", sm.missing);
    }
    console.groupEnd();
    /* eslint-enable no-console */
  }

  /** 诊断：返回匹配详情（供卡片显示"自动发现结果"）*/
  diagnose() {
    const pool = this._pool();
    const out = [];
    for (const [field, rule] of Object.entries(AUTO_BIND.fields)) {
      if (rule && rule.meta) continue;
      const hit = this._match(field, rule, pool);
      out.push({ field, entity: hit || null, ok: !!hit });
    }
    return { poolSize: pool.length, fields: out };
  }
}

window.LixiangAutoBind = LixiangAutoBind;
window.LIXIANG_FIELD_DEFS = AUTO_BIND.fields;
})();
