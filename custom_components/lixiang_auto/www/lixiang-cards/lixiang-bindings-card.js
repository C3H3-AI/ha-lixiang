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
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf"); font-weight:500; font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
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
window.customCards.push({
  type: CARD_TAG,
  name: "实体自动发现（诊断）",
  description: "查看卡片自动绑定了哪些实体；未匹配项一目了然；可复制详情反馈",
  preview: true,
});
