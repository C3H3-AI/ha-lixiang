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
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-seat:#F2F2F5; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E;
            --lx-blue:#4C9AFF; --lx-seat:#2C2C2E; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
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
    return `<div class="seat${o.bench ? " bench" : ""}" data-seat="${label}">
      <div class="pile"></div>
      ${heat ? `<button class="btn" data-fan="${keys.heat}" aria-label="${label}加热">
        <span class="ic" style="color:#9A9A9A">${ICON_HEAT}</span><span class="sp"></span></button>` : ""}
      ${vent ? `<button class="btn" data-fan="${keys.vent}" aria-label="${label}通风">
        <span class="ic" style="color:#9A9A9A">${ICON_FAN}</span><span class="sp"></span></button>` : ""}
    </div>`;
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
            <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
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

        <div class="row2seat">
          ${this._seatHtml({heat:"seat_fl_heat", vent:"seat_fl_vent"}, "主驾")}
          ${this._seatHtml({heat:"seat_fr_heat", vent:"seat_fr_vent"}, "副驾")}
        </div>

        <div class="row3seat">
          ${this._seatHtml({heat:"seat_rl_heat", vent:"seat_rl_vent"}, "二排左", {bench:true})}
          ${this._seatHtml({heat:"seat_rc_heat"}, "二排中", {bench:true})}
          ${this._seatHtml({heat:"seat_rr_heat", vent:"seat_rr_vent"}, "二排右", {bench:true})}
        </div>
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
      history.pushState(null, "", p);
      this.dispatchEvent(new CustomEvent("location-changed", { bubbles:true, composed:true }));
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

    // 4 个模式（复用空调页）
    const MODES = [
      { key:"ac",      name:"空调",     icon:"ic_home_fan_on.webp",  src:"ac" },
      { key:"cool",    name:"极速制冷", icon:"ic_home_ice_cool.webp", src:"ac_fast_cold" },
      { key:"heat",    name:"极速制热", icon:"ic_home_fan_off.webp",  src:"ac_fast_hot" },
      { key:"defrost", name:"除雪除冰", icon:"ic_home_ice_heat.webp", src:"ac_defrost" },
    ];
    const mb = this.querySelector("#modes");
    MODES.forEach(m => {
      const d = document.createElement("div");
      d.className = "m"; d.dataset.k = m.key;
      d.innerHTML = `<div class="c"><img src="${__iconBase}/${m.icon}" alt=""
        onerror="this.src='${__iconBase}/ic_home_fan_on.webp'"></div><div class="n">${m.name}</div>`;
      const act = () => this._tapMode(m);
      this._a11y(d, m.name, act);
      d.addEventListener("click", act);
      mb.appendChild(d);
    });

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

    const MODES = { ac:"ac", cool:"ac_fast_cold", heat:"ac_fast_hot", defrost:"ac_defrost" };
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
window.customCards.push({
  type: CARD_TAG,
  name: "座椅控制（二级页）",
  description: "座椅俯视布局：主/副驾加热通风 + 二排三座 + 方向盘加热，激活橙色",
  preview: true,
});
