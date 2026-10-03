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
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#3CC75A; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F5F5F7; --lx-bg:#FFF; --lx-line:#EDEDF0; --lx-tire:#D8D8DC; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-tire:#3A3A3E; }
  }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:24px;
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
    root.className = "root";
    const cell = (id, pos) => `<div class="tcell" id="${id}">
        <div class="v"><span class="p">—</span><small>bar</small></div>
        <div class="t"><span class="tt">—</span>°C</div></div>`;
    root.innerHTML = `
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
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
      history.pushState(null, "", p);
      this.dispatchEvent(new CustomEvent("location-changed", { bubbles:true, composed:true }));
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
window.customCards.push({
  type: CARD_TAG,
  name: "车辆健康（二级页）",
  description: "胎压图（bar + 胎温）+ 车辆保养计划",
  preview: true,
});
