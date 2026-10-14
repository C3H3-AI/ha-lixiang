
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
        <h2>定时出发</h2>
        <div id="scheds"></div>
      </div>

      <div class="notice">
        <img src="${__iconBase}/ic_home_control.webp" onerror="__lxIconFallback(this)" alt="" style="width:17px;height:17px;flex:0 0 auto;margin-top:1px">
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
