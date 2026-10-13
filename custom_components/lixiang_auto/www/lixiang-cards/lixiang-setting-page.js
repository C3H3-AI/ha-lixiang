
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
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖
const __fontFallback = BUILTIN_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
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
      history.pushState(null,"",p);
      this.dispatchEvent(new CustomEvent("location-changed",{bubbles:true,composed:true}));
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
window.customCards.push({
  type: CARD_TAG,
  name: "车辆设置（二级页）",
  description: "空调/充电/安全/远程操作 —— 全部可控制",
  preview: true,
});
