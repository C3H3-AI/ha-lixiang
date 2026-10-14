
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
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
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
