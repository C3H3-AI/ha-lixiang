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
import { BASE_CSS, fontFaceCss, iconUrl, esc, ICON_BASE_DEFAULT, FONT_BASE_DEFAULT } from "./lixiang-base.js";

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
export function renderCards(cfg) {
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

export function buildInfoPage(host, cfg) {
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

export default { buildInfoPage, renderCards };
