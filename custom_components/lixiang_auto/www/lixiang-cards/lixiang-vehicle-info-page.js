/**
 * lixiang-vehicle-info-page —— 车辆信息（二级页，对齐 App「车辆设置」）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   卡1（4 行）：🚗车辆昵称 理想L6 / 🚗车牌号 浙A12345 /
 *                🚗车辆型号 理想L6 / Ⓥ车架号 HLX32XXXXXXXXXXXX
 *   卡2（1 行）：ⓘ整车软件版本 V8.6.0
 *
 * 数据源：
 *   ✅ 车辆昵称/型号 —— HA 设备注册表
 *   ✅ 车架号 —— 设备 serial_number
 *   ✅ 配置等级 / 辅助驾驶等级 —— 车辆配置实体属性
 *   ⚠️ 车牌号 —— 接口需特殊 token（100032），暂不可用
 *   ⚠️ 整车软件版本 —— 集成未采集
 */

const CARD_TAG = "lixiang-vehicle-info-page";
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
    --lx-card:#F5F5F7; --lx-bg:#FFF; --lx-line:#EDEDF0; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:24px;
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
    root.className = "root";
    root.innerHTML = `
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
        <h1>车辆设置</h1>
      </div>

      <div class="card">
        <div class="row">
          <img class="ic" src="${__iconBase}/ic_home_control.webp" alt="">
          <span class="k">车辆昵称</span><span class="v" id="v-name">—</span></div>
        <div class="row click" id="r-plate">
          <img class="ic" src="${__iconBase}/ic_home_control.webp" alt="">
          <span class="k">车牌号</span><span class="v na" id="v-plate">暂不可用</span></div>
        <div class="row">
          <img class="ic" src="${__iconBase}/ic_home_control.webp" alt="">
          <span class="k">车辆型号</span><span class="v" id="v-model">—</span></div>
        <div class="row">
          <img class="ic" src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'">
          <span class="k">车架号</span><span class="v mono" id="v-vin">—</span></div>
      </div>

      <div class="card">
        <div class="row click" id="r-sw">
          <img class="ic" src="${__iconBase}/ic_home_health.webp" alt="">
          <span class="k">整车软件版本</span><span class="v na" id="v-sw">暂不可用</span></div>
      </div>

      <div class="card">
        <div class="row">
          <img class="ic" src="${__iconBase}/ic_home_control.webp" alt="">
          <span class="k">配置等级</span><span class="v" id="v-cfg">—</span></div>
        <div class="row">
          <img class="ic" src="${__iconBase}/ic_home_navigation.webp" alt="">
          <span class="k">辅助驾驶等级</span><span class="v" id="v-ad">—</span></div>
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

    // 暂不可用的两项：点击说明原因
    const why = (msg) => () => this._toast(msg);
    const p1 = why("车牌号需要额外的接口令牌（当前返回 100032），集成暂无法读取");
    const p2 = why("整车软件版本集成尚未采集，可在 App「车辆设置」或车机内查看");
    [["#r-plate", p1, "车牌号"], ["#r-sw", p2, "整车软件版本"]].forEach(([sel, fn, label]) => {
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

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);
    const d = this._vehicle();
    const c = this._config || {};

    // 昵称 / 型号
    const nick = c.nickname || (d && d.name_by_user) || (d && d.name) || "—";
    q("#v-name").textContent = nick;
    q("#v-model").textContent = (d && d.model) || c.model_name || nick;

    // 车架号
    const vin = (d && d.serial_number) || c.vin
      || ((this._hass && this._hass.states && this._eid("battery"))
          ? "" : "");
    q("#v-vin").textContent = vin || "—";

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
window.customCards.push({
  type: CARD_TAG,
  name: "车辆信息（二级页）",
  description: "车辆昵称/车牌/型号/车架号/软件版本/配置等级",
  preview: true,
});
