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
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf"); font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
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
  .modes { display:grid; grid-template-columns:repeat(4,1fr); gap:8px;
           padding:22px 16px 0; }
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

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const root = document.createElement("div");
    root.className = "root";
    root.innerHTML = `
      <div class="top">
        <div class="toprow">
          <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
            <img src="${__iconBase}/ic_home_return.webp" alt="">
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
        <h2>定时出发</h2>
        <div id="scheds"></div>
      </div>

      <div class="notice">
        <img src="${__iconBase}/ic_home_control.webp" alt="" style="width:17px;height:17px;flex:0 0 auto;margin-top:1px">
        <div><b>定时出发暂不可用。</b>该功能的控制指令走 LiNdn（JOB）通道，集成尚未打通，
          因此仅能展示、不能新增或修改。请在理想 App 内设置。</div>
      </div>

      <div class="add ro" id="add" role="button" tabindex="0" aria-label="添加定时">添加</div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    // 返回
    const back = () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      history.pushState(null, "", p);
      this.dispatchEvent(new CustomEvent("location-changed", { bubbles:true, composed:true }));
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    // 温度 ±
    const step = (d) => this._stepTemp(d);
    this._a11y(this.querySelector("#dec"), "降低温度", () => step(-0.5));
    this._a11y(this.querySelector("#inc"), "升高温度", () => step(+0.5));
    this.querySelector("#dec").addEventListener("click", () => step(-0.5));
    this.querySelector("#inc").addEventListener("click", () => step(+0.5));

    // 4 个模式按钮
    const MODES = [
      { key:"ac",      name:"空调",     icon:"ic_home_fan_on.webp",     kind:"climate" },
      { key:"cool",    name:"极速制冷", icon:"ic_home_ice_cool.webp",   kind:"switch" },
      { key:"heat",    name:"极速制热", icon:"ic_home_fan_off.webp",    kind:"switch" },
      { key:"defrost", name:"除雪除冰", icon:"ic_home_ice_heat.webp", kind:"switch" },
    ];
    const box = this.querySelector("#modes");
    MODES.forEach(m => {
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

    // 添加按钮（只读）
    const add = () => this._toast("定时出发需在理想 App 内设置（JOB 通道未打通）");
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
      eid = this._eid("ac"); dom = "climate"; svc = this._on(eid) ? "turn_off" : "turn_on";
    } else {
      eid = this._eid(m.key === "cool" ? "ac_fast_cold" : (m.key === "heat" ? "ac_fast_hot" : "ac_defrost"));
      if (eid) { dom = eid.split(".")[0]; svc = this._on(eid) ? "turn_off" : "turn_on"; }
    }
    if (!eid) { this._toast(`${m.name} 未接入`, "err"); return; }
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
    if (aqi == null) { aqiEl.textContent = "—"; aqiEl.className = "v"; q("#l-aqi").textContent = "空气"; }
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

    // 4 个模式状态
    const MAP = {
      ac: this._eid("ac"),
      cool: this._eid("ac_fast_cold"),
      heat: this._eid("ac_fast_hot"),
      defrost: this._eid("ac_defrost"),
    };
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
window.customCards.push({
  type: CARD_TAG,
  name: "空调控制（二级页）",
  description: "温度调节 + 空调/极速制冷/极速制热/除雪除冰 + 空气质量",
  preview: true,
});
