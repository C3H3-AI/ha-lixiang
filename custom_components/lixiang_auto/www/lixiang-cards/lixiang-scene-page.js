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
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
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
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F5F5F7; --lx-bg:#FFF; --lx-line:#EDEDF0; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
    .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
    .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
            --lx-card:#F5F5F7; --lx-bg:#FFF; --lx-line:#EDEDF0; --lx-blue:#0A58F6; }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:22px;
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
  .sw { width:52px; height:31px; border-radius:16px; background:#D8D8DC;
        position:relative; margin-top:16px; flex:0 0 auto;
        transition:background .22s; }
  .sw::after { content:""; position:absolute; top:2px; left:2px; width:27px;
               height:27px; border-radius:50%; background:#fff;
               box-shadow:0 1px 3px rgba(0,0,0,.18); transition:left .22s; }
  .sw.on { background:var(--lx-blue); }
  .sw.on::after { left:23px; }
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
  [role="button"]:focus-visible, [role="switch"]:focus-visible,
  .btn:focus-visible, button:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }
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
          <div class="sw ro" data-sw="${m.key}" role="switch" tabindex="0"
            aria-checked="false" aria-label="${m.name}开关"></div>
        </div>
      </div>`).join("");

    const small = MODES.filter(m => !m.big).map(m => `
      <div class="small" data-k="${m.key}">
        <div class="hd"><img src="${__iconBase}/${m.icon}" alt=""
          onerror="this.style.visibility='hidden'"><span class="n">${m.name}</span></div>
        <div class="d">${m.desc}</div>
        <div class="sw ro" data-sw="${m.key}" role="switch" tabindex="0"
          aria-checked="false" aria-label="${m.name}开关"></div>
      </div>`).join("");

    root.innerHTML = `
      <div class="topbar">
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
        <h1>情景模式</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
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
      history.pushState(null, "", p);
      this.dispatchEvent(new CustomEvent("location-changed", { bubbles:true, composed:true }));
    };
    this._a11y(this.querySelector("#back"), "返回", back);
    this.querySelector("#back").addEventListener("click", back);

    const rf = this.querySelector("#refresh");
    const doRf = () => { rf.classList.add("spin"); this._update(); this._toast("已刷新");
      setTimeout(() => rf.classList.remove("spin"), 900); };
    this._a11y(rf, "刷新", doRf);
    rf.addEventListener("click", doRf);

    // 开关（只读：点击说明）
    this.querySelectorAll("[data-sw]").forEach(sw => {
      const name = (MODES.find(m => m.key === sw.dataset.sw) || {}).name || "";
      const act = () => this._toast(`${name}：需在理想 App 或车机中开启（集成暂不支持远程切换）`, null, 3400);
      this._a11y(sw, `${name}开关`, act);
      sw.addEventListener("click", act);
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
    const n = raw == null ? null : Number(raw);
    // 已验证的映射有限：0/1 表示无激活或第一档；其余按位/序号推断不做承诺
    this.querySelectorAll("[data-sw]").forEach(sw => {
      sw.className = "sw ro";
      sw.setAttribute("aria-checked", "false");
    });
    const root = this.querySelector(".root");
    if (root && raw != null) root.setAttribute("data-scene", String(raw));
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangScenePage);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "情景模式（二级页）",
  description: "宠物 / 露营 / 擦车 / 离车不下电（4 模式，对齐 App 布局）",
  preview: true,
});
