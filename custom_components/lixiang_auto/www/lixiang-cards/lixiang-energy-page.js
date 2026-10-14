
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
 * lixiang-energy-page —— 里程能耗（二级页，对齐 App 真实版）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   顶栏：‹ 里程能耗 查询
 *   「理想L6已经陪伴您800天」（大字）
 *   主卡：环形图（绿=耗电行驶 87% + 蓝=耗油行驶 13%），中心大数字=陪伴里程
 *        底部两项：87% ⚡耗电行驶 | 13% 💧耗油行驶
 *   智驾卡：「已使用智能驾驶 N 天，行驶 N km」
 *          + 两个环形（36% 占总天数 / 14% 占总里程）
 *   免责文案
 *   年份折叠：2026年⌃ / 2025年⌃ / 2024年⌃
 */

const CARD_TAG = "lixiang-energy-page";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

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

const I18N = {
  title: "里程能耗", query: "查询",
  companion: "已经陪伴您", days: "天",
  partnerKm: "陪伴里程km",
  elec: "耗电行驶", fuel: "耗油行驶",
  adTitle: "已使用智能驾驶", adDrive: "，行驶",
  dayRatio: "占总天数", kmRatio: "占总里程",
  disclaimer: "数据在每次驾驶循环后更新，可能存在延迟，请以车端数据为准。",
  noData: "暂无数据", loading: "加载中…", retry: "重新加载",
  loadFail: "数据加载失败",
};

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
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

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; }
  .back { width:30px; height:30px; opacity:.75; cursor:pointer; }
  .topbar h1 { font-size:18px; font-weight:500; margin:0; flex:1; text-align:center; }
  .qbtn { font-size:15px; color:var(--lx-t1); cursor:pointer; min-width:40px;
          text-align:right; }
  .refresh { width:30px; height:30px; border-radius:50%; display:flex;
             align-items:center; justify-content:center; cursor:pointer; }
  .refresh img { width:17px; height:17px; opacity:.6; transform:rotate(-90deg); }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }

  /* 陪伴语 */
  .hello { font-size:21px; font-weight:500; padding:8px 20px 16px; line-height:1.35; }
  .hello b { font-family:"LxNum"; font-weight:600; }

  /* ── 主卡（环形）── */
  .card { margin:0 16px; background:var(--lx-card); border-radius:20px;
          padding:26px 20px 22px; text-align:center; }
  .ring2 { position:relative; display:inline-block; }
  .ring2 svg { display:block; }
  .ring2 .center { position:absolute; inset:0; display:flex; flex-direction:column;
                   align-items:center; justify-content:center; }
  .ring2 .center .n { font-family:"LxNum"; font-size:44px; font-weight:500;
                      letter-spacing:-1px; line-height:1; }
  .ring2 .center .l { font-size:12.5px; color:var(--lx-t3); margin-top:8px; }
  .legend { display:flex; justify-content:center; gap:44px; margin-top:20px; }
  .lg { text-align:center; }
  .lg .v { font-size:21px; font-weight:500; display:flex; align-items:center;
           justify-content:center; gap:4px; }
  .lg .v img { width:17px; height:17px; }
  .lg .l { font-size:12.5px; color:var(--lx-t3); margin-top:5px; }

  /* ── 智驾卡 ── */
  .adcard { margin:16px 16px 0; background:var(--lx-card); border-radius:20px;
            padding:24px 20px 26px; }
  .adcard .t { font-size:17px; text-align:center; line-height:1.5; }
  .adcard .t b { font-family:"LxNum"; font-weight:600; }
  .rings { display:flex; justify-content:center; gap:52px; margin-top:24px; }
  .ring1 { position:relative; }
  .ring1 .center { position:absolute; inset:0; display:flex; flex-direction:column;
                   align-items:center; justify-content:center; }
  .ring1 .center .n { font-family:"LxNum"; font-size:25px; font-weight:500; }
  .ring1 .center .l { font-size:11.5px; color:var(--lx-t3); margin-top:4px; }

  /* 免责 */
  .note { padding:18px 20px 6px; font-size:12.5px; color:var(--lx-t3);
          line-height:1.65; }

  /* ── 年份折叠 ── */
  .years { padding:6px 20px 0; }
  .year { border-bottom:1px solid var(--lx-line); }
  .year:last-child { border-bottom:none; }
  .yhead { display:flex; align-items:center; padding:17px 0; cursor:pointer; }
  .yhead .yn { font-size:17px; font-weight:500; }
  .yhead .ar { margin-left:auto; font-size:15px; color:var(--lx-t2);
               transition:transform .2s; }
  .year.open .yhead .ar { transform:rotate(180deg); }
  .ymonths { display:none; padding-bottom:8px; }
  .year.open .ymonths { display:block; }
  /* ★ 2026-10-12：改为 block —— .m 现在包着 .mh（行）+ .md（内联明细） */
  .m { display:block; padding:11px 0; }
  .yhead .ys { font-size:12px; color:var(--lx-t3); margin-left:10px; }
  .m .mh { display:flex; align-items:center; width:100%; cursor:pointer; }
  .m .mbar { flex:1; height:6px; border-radius:3px; background:var(--lx-line);
             overflow:hidden; margin:0 10px; min-width:30px; }
  .m .mbar > i { display:block; height:100%; border-radius:3px; background:#2C6BFF;
                 transition:width .3s ease; }
  .m .ar { margin-left:6px; color:var(--lx-t3); font-size:13px; transition:transform .2s; }
  .m.sel .ar { transform:rotate(90deg); }
  .m.top .mv { font-weight:600; color:var(--lx-t1); }
  .m.top .mbar > i { background:#1E5AE0; }
  /* ★ 内联明细（参考充电页）：点月份即在该月下方展开，不再跑到底部 */
  .m .md { display:none; padding:2px 0 8px; }
  .m.sel .md { display:block; }
  .m .mn { font-size:14px; color:var(--lx-t2); }
  .m .mt { font-size:11.5px; color:var(--lx-t3); margin-left:10px; }
  .m .mv { margin-left:auto; font-family:"LxNum"; font-size:14px; font-weight:500; }
  .m .mu { font-size:11px; color:var(--lx-t3); margin-left:3px; }
  .m.sel .mn { color:var(--lx-blue); font-weight:500; }
  .daily { padding:4px 0 8px; }
  .drow { display:flex; align-items:center; gap:8px; padding:7px 0; font-size:12.5px; }
  .drow .dd { color:var(--lx-t2); min-width:44px; }
  .drow .dn { font-family:"LxNum"; font-weight:500; min-width:64px; text-align:right; }
  /* ★ 2026-10-11 迷你条：一眼看出"哪天跑得多"（原来只有数字，要逐行对比） */
  .dbar { flex:1; height:6px; border-radius:3px; background:var(--lx-line,rgba(0,0,0,.06)); overflow:hidden; }
  .dbar > i { display:block; height:100%; border-radius:3px; background:#2C6BFF; }
  .drow.top .dd, .drow.top .dn { color:var(--lx-t1); font-weight:600; }
  .drow.top .dbar > i { background:#34C759; }
  .sortbtn { font-size:12px; color:var(--lx-t3); cursor:pointer; padding:2px 6px;
             border:1px solid var(--lx-line,rgba(0,0,0,.08)); border-radius:7px; }
  .sortbtn.on { color:#2C6BFF; border-color:#2C6BFF; }
  .tabs { display:flex; gap:8px; margin:6px 0 10px; }
  .tab { padding:6px 13px; border-radius:9px; font-size:12px; cursor:pointer;
         background:var(--lx-bg); color:var(--lx-t3); }
  .tab.on { background:rgba(10,88,246,.1); color:var(--lx-blue); font-weight:500; }
  .empty { text-align:center; color:var(--lx-t3); font-size:13px; padding:20px 0; }
  .state { text-align:center; padding:24px 16px; }
  .state .t { font-size:13.5px; color:var(--lx-t2); }
  .state .d { font-size:11.5px; color:var(--lx-t3); margin-top:7px; line-height:1.55; }
  .state .retry { display:inline-block; margin-top:13px; font-size:13px;
                  color:var(--lx-blue); padding:7px 17px; border-radius:10px;
                  background:rgba(10,88,246,.07); cursor:pointer; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  /* 无障碍：键盘焦点可见 */
  [role="button"]:focus-visible, .refresh:focus-visible,
  .yhead:focus-visible, .m:focus-visible, .tab:focus-visible {
    outline:2.5px solid var(--lx-blue); outline-offset:2px; border-radius:8px; }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration:.01ms !important;
      transition-duration:.01ms !important; } }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
`;

class LixiangEnergyPage extends HTMLElement {
  setConfig(c) {
    this._config = c || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base; this._openYears = new Set(); this._selMonth = null;
    this._tab = "mileage"; this._built = false;
  }
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
    root.innerHTML = `
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="返回">
        <h1>${I18N.title}</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
      </div>

      <div class="hello" id="hello">—</div>

      <!-- 主卡：双段环形 -->
      <div class="card">
        <div class="ring2">
          <svg id="ring2" width="272" height="272" viewBox="0 0 272 272"></svg>
          <div class="center">
            <div class="n" id="c-km">—</div>
            <div class="l">${I18N.partnerKm}</div>
          </div>
        </div>
        <div class="legend">
          <div class="lg">
            <div class="v"><span id="lg-elec-p">—</span><img src="${__iconBase}/ic_home_electricity.webp" onerror="__lxIconFallback(this)" alt=""></div>
            <div class="l">${I18N.elec}</div>
          </div>
          <div class="lg">
            <div class="v"><img src="${__iconBase}/ic_home_oil.webp" onerror="__lxIconFallback(this)" alt=""><span id="lg-fuel-p">—</span></div>
            <div class="l">${I18N.fuel}</div>
          </div>
        </div>
      </div>

      <!-- 智驾卡：两个环形 -->
      <div class="adcard">
        <div class="t" id="ad-text">—</div>
        <div class="rings">
          <div class="ring1">
            <svg id="ring-day" width="118" height="118" viewBox="0 0 118 118"></svg>
            <div class="center"><div class="n" id="c-day">—</div>
              <div class="l">${I18N.dayRatio}</div></div>
          </div>
          <div class="ring1">
            <svg id="ring-km" width="118" height="118" viewBox="0 0 118 118"></svg>
            <div class="center"><div class="n" id="c-km-pct">—</div>
              <div class="l">${I18N.kmRatio}</div></div>
          </div>
        </div>
      </div>

      <div class="note">${I18N.disclaimer}</div>

      <!-- 明细已改为内联到各月份下方（参考充电页），不再有底部 #daily -->
      <div class="years" id="years"><div class="empty">${I18N.loading}</div></div>
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
    const doRf = () => this._refreshAll();
    this._a11y(rf, "刷新", doRf);
    rf.addEventListener("click", doRf);

    this._built = true;
  }

  /** 画环形（支持双段：绿+蓝）*/
  _drawRing(svg, segments, opts) {
    if (!svg) return;
    const o = opts || {};
    const size = o.size || 118, sw = o.stroke || 12;
    const r = (size - sw) / 2, cx = size / 2, cy = size / 2;
    const C = 2 * Math.PI * r;
    const NS = "http://www.w3.org/2000/svg";
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    // 背景环
    const bg = document.createElementNS(NS, "circle");
    bg.setAttribute("cx", cx); bg.setAttribute("cy", cy); bg.setAttribute("r", r);
    bg.setAttribute("fill", "none");
    bg.setAttribute("stroke", o.trackColor || "rgba(0,0,0,.05)");
    bg.setAttribute("stroke-width", sw);
    svg.appendChild(bg);

    // 从顶部开始，顺时针
    let acc = 0;
    segments.forEach((seg) => {
      const frac = Math.max(0, Math.min(1, seg.value || 0));
      if (frac <= 0) { acc += frac; return; }
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", cx); c.setAttribute("cy", cy); c.setAttribute("r", r);
      c.setAttribute("fill", "none");
      c.setAttribute("stroke", seg.color);
      c.setAttribute("stroke-width", sw);
      c.setAttribute("stroke-linecap", "round");
      c.setAttribute("stroke-dasharray", `${frac * C} ${C}`);
      c.setAttribute("stroke-dashoffset", `${-acc * C}`);
      c.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
      svg.appendChild(c);
      acc += frac;
    });
  }

  _refreshAll() {
    const rf = this.querySelector("#refresh");
    if (rf) rf.classList.add("spin");
    this._years = null; this._monthDaily = null; this._fetchingYears = false;
    this._error = null;
    Promise.resolve(this._fetchYears()).finally(() => {
      if (rf) rf.classList.remove("spin");
      this._update();
    });
  }

  async _fetchYears() {
    if (!this._hass || this._years || this._fetchingYears) return;
    this._fetchingYears = true;
    try {
      const r = await this._hass.callService("lixiang_auto", "get_travel", {}, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const yl = first && first.data && first.data.yearEnergyList;
      if (Array.isArray(yl) && yl.length) {
        this._years = yl;
        this._openYears.add(String(yl[0].year));
        this._renderYears();
        const em = (yl[0].monthlyEnergyList || [])[0];
        if (em && em.month != null) this._fetchMonthDaily(yl[0].year, em.month, true);
      }
    } catch (e) { this._error = (e && e.message) || "网络请求失败"; }
    finally { this._fetchingYears = false; }
  }

  async _fetchMonthDaily(year, month, silent) {
    if (!this._hass) return;
    if (!silent) { this._monthDaily = null; this._renderDaily(); }
    try {
      const r = await this._hass.callService("lixiang_auto", "get_travel",
        { year, month }, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const dl = first && first.data && first.data.dailyList;
      if (Array.isArray(dl)) {
        this._monthDaily = dl.map((x) => ({
          dayOfMonth: Number(x.dayOfMonth) || 0,
          mileage: Number(x.mileage) || 0,
          elecEnergy: Number(x.elecEnergy) || 0,
          fuelConsumption: Number(x.fuelConsumption) || 0,
        })).sort((a, b) => a.dayOfMonth - b.dayOfMonth);
      }
    } catch (e) {}
    this._renderDaily();
  }

  _renderYears() {
    const box = this.querySelector("#years");
    if (!box) return;
    const yl = this._years;
    if (!yl || !yl.length) {
      box.innerHTML = this._error
        ? `<div class="state"><div class="t">${I18N.loadFail}</div>
           <div class="d">${this._error}</div>
           <div class="retry" id="retry1">${I18N.retry}</div></div>`
        : `<div class="state"><div class="t">${this._fetchingYears ? I18N.loading : I18N.noData}</div>
           <div class="d">${this._fetchingYears ? "正在获取里程数据…" : "车辆尚未产生行程数据"}</div></div>`;
      const r1 = box.querySelector("#retry1");
      if (r1) { this._a11y(r1, I18N.retry, () => this._refreshAll());
                r1.addEventListener("click", () => this._refreshAll()); }
      return;
    }
    box.innerHTML = yl.map((y) => {
      const ms = (y.monthlyEnergyList || []).filter((m) => Number(m.travelMil) > 0);
      const open = this._openYears.has(String(y.year));
      // 年份汇总（对齐充电页：N 个月 · 总计）
      const tot = ms.reduce((a, m) => a + (Number(m.travelMil) || 0), 0);
      // 条形按【所在年】归一（跨年不可比）
      const mx = Math.max(1, ...ms.map((m) => Number(m.travelMil) || 0));
      const rows = ms.map((m) => {
        const sel = this._selMonth && this._selMonth.year === y.year
                    && this._selMonth.month === m.month;
        const v = Number(m.travelMil) || 0;
        const w = v > 0 ? Math.max(3, Math.round((v / mx) * 100)) : 0;
        const isTop = v > 0 && v >= mx;
        // ★ 每行自带内联明细容器（参考充电页：点开即在该月下方，不再跑到底部）
        return `<div class="m${sel ? " sel" : ""}${isTop ? " top" : ""}"
                     data-y="${y.year}" data-m="${m.month}">
            <div class="mh" role="button" tabindex="0" aria-expanded="${sel ? "true" : "false"}">
              <span class="mn">${m.month} 月</span>
              <span class="mbar" aria-hidden="true"><i style="width:${w}%"></i></span>
              <span class="mv">${Number(m.travelMil).toFixed(1)}</span>
              <span class="mu">km</span>
              <span class="ar">›</span>
            </div>
            <div class="md" id="md-${y.year}-${m.month}"></div>
          </div>`;
      }).join("");
      return `<div class="year${open ? " open" : ""}" data-year="${y.year}">
          <div class="yhead" role="button" tabindex="0" aria-expanded="${open ? "true" : "false"}">
            <span class="yn">${y.year}年</span>
            <span class="ys">${ms.length} 个月 · ${tot.toFixed(1)} km</span>
            <span class="ar">⌃</span></div>
          <div class="ymonths">${rows || '<div class="empty">无记录</div>'}</div>
        </div>`;
    }).join("");

    box.querySelectorAll(".yhead").forEach((h) => {
      const act = () => {
        const y = h.parentElement.dataset.year;
        if (this._openYears.has(y)) this._openYears.delete(y); else this._openYears.add(y);
        this._renderYears();
      };
      this._a11y(h, `${h.parentElement.dataset.year} 年 展开收起`, act);
      h.addEventListener("click", act);
    });
    box.querySelectorAll(".m").forEach((m) => {
      const h = m.querySelector(".mh");
      const act = async () => {
        const yy = Number(m.dataset.y), mm = Number(m.dataset.m);
        const isOpen = this._selMonth && this._selMonth.year === yy
                       && this._selMonth.month === mm;
        if (isOpen) {
          // 再点一次收起
          this._selMonth = null; this._monthDaily = null;
          m.classList.remove("sel");
          if (h) h.setAttribute("aria-expanded", "false");
          const d = m.querySelector(".md"); if (d) d.innerHTML = "";
          return;
        }
        this._selMonth = { year: yy, month: mm };
        // 收起其它已展开的月份
        box.querySelectorAll(".m.sel").forEach((el) => {
          el.classList.remove("sel");
          const hh = el.querySelector(".mh");
          if (hh) hh.setAttribute("aria-expanded", "false");
          const dd = el.querySelector(".md"); if (dd) dd.innerHTML = "";
        });
        m.classList.add("sel");
        if (h) h.setAttribute("aria-expanded", "true");
        const target = m.querySelector(".md");
        if (target) target.innerHTML = `<div class="empty">${I18N.loading}</div>`;
        this._renderDaily(target);          // 先渲染 tabs（带 loading）
        await this._fetchMonthDaily(yy, mm, false);
      };
      this._a11y(h || m, `${m.dataset.y} 年 ${m.dataset.m} 月 明细`, act);
      (h || m).addEventListener("click", act);
    });
  }

  /** 渲染某月「每日」明细。
   *  ★ 2026-10-12：改为**内联**渲染到传入的容器（`box`）—— 参考充电页。
   *    此前渲染到页面底部的 `#daily`，用户点月份后要往下滚才看得到。
   *    `box` 缺省时按「当前选中月份」自动定位容器。
   */
  _renderDaily(box) {
    // ★ 未显式传容器时，自动定位"当前选中月份"的内联容器 ——
    //   这样排序/tabs/重新拉取等旧调用点无需改动即可正确重绘。
    if (!box && this._selMonth) {
      box = this.querySelector(`#md-${this._selMonth.year}-${this._selMonth.month}`);
    }
    if (!box) return;
    if (!this._selMonth) { box.innerHTML = ""; return; }
    const rows = this._monthDaily || [];
    const head = `<div class="tabs">
        <div class="tab${this._tab === "mileage" ? " on" : ""}" data-tab="mileage">每日里程</div>
        <div class="tab${this._tab === "elec" ? " on" : ""}" data-tab="elec">每日耗电</div>
        <div class="tab${this._tab === "fuel" ? " on" : ""}" data-tab="fuel">每日耗油</div>
      </div>
      <div class="sortbtn${this._sort ? " on" : ""}" role="button" tabindex="0"
           aria-label="按数值排序">${this._sort ? "按数值 ↓" : "按日期"}</div>`;
    if (!rows.length) { box.innerHTML = head + `<div class="empty">${I18N.noData}</div>`; this._bindTabs(box); return; }
    const pick = { mileage:"mileage", elec:"elecEnergy", fuel:"fuelConsumption" }[this._tab];
    const unit = this._tab === "mileage" ? "km" : (this._tab === "elec" ? "kWh" : "L");
    // ★ 迷你条以【当月最大值】为基准；排序可选（默认按日期）
    const max = Math.max(...rows.map(r => Number(r[pick]) || 0), 0);
    const list = this._sort
      ? rows.slice().sort((a, b) => (Number(b[pick]) || 0) - (Number(a[pick]) || 0))
      : rows;
    box.innerHTML = head + `<div style="font-size:12px;color:var(--lx-t3);padding:4px 0 6px">
        ${this._selMonth.year}年${this._selMonth.month}月</div>` +
      list.map((r) => {
        const v = Number(r[pick]) || 0;
        const pct = max > 0 ? Math.max(v > 0 ? 3 : 0, Math.round(v / max * 100)) : 0;
        const top = max > 0 && v === max;
        return `<div class="drow${top ? " top" : ""}">
          <span class="dd">${r.dayOfMonth} 日</span>
          <span class="dbar"><i style="width:${pct}%"></i></span>
          <span class="dn">${v ? v + " " + unit : "—"}</span></div>`;
      }).join("");
    this._bindTabs(box);
    this._bindSort(box);
  }

  /** 排序切换（按日期 / 按数值）——★ 2026-10-11 */
  _bindSort(scope) {
    const b = (scope || this).querySelector(".sortbtn");
    if (!b) return;
    const act = () => { this._sort = !this._sort; this._renderDaily(scope); };
    this._a11y(b, b.textContent, act);
    b.addEventListener("click", act);
  }

  _bindTabs(scope) {
    (scope || this).querySelectorAll(".tab").forEach((t) => {
      const act = () => { this._tab = t.dataset.tab; this._renderDaily(scope); };
      this._a11y(t, t.textContent, act);
      t.addEventListener("click", act);
    });
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);

    // 陪伴语：「理想L6已经陪伴您800天」
    const mdl = (window.LixiangAutoBind && this._hass)
      ? (() => {
          const c = this._config || {};
          for (const d of Object.values(this._hass.devices || {})) {
            if ((d.manufacturer || "").includes("理想") ||
                JSON.stringify(d.identifiers || []).includes("lixiang")) {
              const m = String(d.model || d.name || "").match(/(MEGA|L[6-9]|i[6-9])/i);
              return m ? `理想${m[1].toUpperCase()}` : (d.name || "理想汽车");
            }
          }
          return "理想汽车";
        })() : "理想汽车";
    const days = this._num(this._eid("partner_days"));
    q("#hello").innerHTML = days == null
      ? `${mdl}${I18N.companion} — ${I18N.days}`
      : `${mdl}${I18N.companion}<b>${Math.round(days)}</b>${I18N.days}`;

    // 主环：陪伴里程 + 电/油占比
    const km = this._num(this._eid("partner_km"));
    const elecKm = this._num(this._eid("elec_km"));
    const fuelL = this._num(this._eid("fuel_l"));
    q("#c-km").textContent = km == null ? "—" : Math.round(km).toLocaleString();

    // 占比：耗电行驶 vs 耗油（App 用里程/油耗的构成比）
    let elecFrac = 0.87, fuelFrac = 0.13;
    if (elecKm != null && km != null && km > 0) {
      elecFrac = Math.min(1, elecKm / km);
      fuelFrac = Math.max(0, 1 - elecFrac);
    }
    this._drawRing(q("#ring2"), [
      { value: elecFrac, color: "#34C759" },
      { value: fuelFrac, color: "#2C6BFF" },
    ], { size: 272, stroke: 20, trackColor: "rgba(0,0,0,.04)" });
    q("#lg-elec-p").textContent = Math.round(elecFrac * 100) + "%";
    q("#lg-fuel-p").textContent = Math.round(fuelFrac * 100) + "%";

    // 智驾卡
    const adDays = this._num(this._eid("ad_days"));
    const adKm = this._num(this._eid("ad_km"));
    const totalKm = this._num(this._eid("total_km"));
    q("#ad-text").innerHTML = (adDays != null || adKm != null)
      ? `${I18N.adTitle} <b>${adDays == null ? "—" : Math.round(adDays)}</b> 天${I18N.adDrive} <b>${adKm == null ? "—" : Math.round(adKm).toLocaleString()}</b> km`
      : I18N.loading;

    const dayPct = (adDays != null && days != null && days > 0) ? Math.min(1, adDays / days) : 0;
    const kmPct = (adKm != null && totalKm != null && totalKm > 0) ? Math.min(1, adKm / totalKm) : 0;
    this._drawRing(q("#ring-day"), [{ value: dayPct, color: "#2C6BFF" }],
      { size: 118, stroke: 11, trackColor: "rgba(44,107,255,.16)" });
    this._drawRing(q("#ring-km"), [{ value: kmPct, color: "#2C6BFF" }],
      { size: 118, stroke: 11, trackColor: "rgba(44,107,255,.16)" });
    q("#c-day").textContent = Math.round(dayPct * 100) + "%";
    q("#c-km-pct").textContent = Math.round(kmPct * 100) + "%";

    this._fetchYears();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangEnergyPage);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "里程能耗（二级页）",
  description: "环形图：陪伴里程 + 电/油占比 + 智驾占比 + 年份折叠 + 每日明细",
  preview: true,
});
