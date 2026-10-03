/**
 * lixiang-charge-page  —— 充电（二级页）
 *
 * ★ 结构对齐里程能耗页（App 同款）：
 *   顶栏 → 实时状态卡 → 本月统计 → 按月折叠（年→月）→ 明细 → 充电设置
 *
 * 数据源（全部实测可用）：
 *   实时状态 → VSS 实体（charging_status / limit / mode / appointment / guns）
 *   历史统计 → lixiang_auto.get_charge 服务（按月次数 + 电量）
 *   单次明细 → 同上（startTime / chargingType / chargingCapacity）
 */

const CARD_TAG = "lixiang-charge-page";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖

const I18N = {
  title: "充电",
  status: "充电状态",
  notCharging: "未充电",
  charging: "充电中",
  done: "已充满",
  power: "充电功率",
  remain: "剩余时间",
  limit: "充电上限",
  mode: "充电模式",
  appt: "预约充电",
  apptTime: "预约时段",
  acGun: "交流枪",
  dcGun: "直流枪",
  portCover: "充电口盖",
  fault: "充电故障",
  monthKwh: "本月充电量",
  monthTimes: "本月次数",
  totalKwh: "累计充电量",
  history: "充电记录",
  dc: "直流",
  ac: "交流",
  times: "次",
  noData: "暂无数据",
  loading: "加载中…",
  settings: "充电设置",
  year: "年",
  min: "分钟",
};

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#ECECEF; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { position:relative; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:16px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#ECECEF; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  .topbar { display:flex; align-items:center; height:48px; padding:0 16px; }
  .back { width:24px; height:24px; opacity:.75; cursor:pointer; }
  .topbar h1 { font-size:17px; font-weight:500; margin:0; flex:1; text-align:center; }
  .topbar .r { width:24px; }

  /* ── 实时状态大卡 ── */
  .hero { margin:6px 20px 0; border-radius:18px; padding:16px;
          background:linear-gradient(150deg,var(--lx-card) 0%,var(--lx-bg) 100%); }
  .hero .row1 { display:flex; align-items:center; gap:9px; }
  .hero .dot { width:9px; height:9px; border-radius:50%; background:var(--lx-t3); }
  .hero .dot.on { background:var(--lx-green); box-shadow:0 0 0 4px rgba(52,199,89,.16); }
  .hero .dot.err { background:var(--lx-red); }
  .hero .st { font-size:16px; font-weight:500; }
  .hero .sub { margin-left:auto; font-size:12px; color:var(--lx-t3); }
  /* 三栏：前两个数值等宽，第三个（模式·文字）给更多空间 */
  .hero .metrics { display:grid; grid-template-columns:1fr 1fr 1.5fr; gap:8px; margin-top:14px; }
  .hero .m .v { font-family:"LxNum","Licium"; font-size:21px; font-weight:600;
                white-space:nowrap; }
  .hero .m .v.txt { font-family:"Licium"; font-size:14px; font-weight:500;
                    white-space:normal; line-height:1.25; word-break:break-word; }
  .hero .m .l { white-space:nowrap; }
  .hero .m .v small { font-size:11px; color:var(--lx-t2); margin-left:2px; }
  /* 文字型值（如"低价充电"）用较小字号，避免换行 */
  .hero .m .v.txt { font-size:15px; font-weight:500; font-family:"Licium"; }
  .hero .m .l { font-size:11px; color:var(--lx-t3); margin-top:3px; }
  .hero .bar { height:7px; border-radius:20px; background:var(--lx-line);
               overflow:hidden; margin-top:14px; }
  .hero .bar > i { display:block; height:100%; border-radius:20px;
                   background:var(--lx-green); transition:width .45s; }
  .hero .barrow { display:flex; align-items:center; gap:10px; margin-top:12px; }
  .hero .barrow .p { font-family:"LxNum"; font-size:13px; font-weight:600; min-width:42px;
                     text-align:right; }
  .hero .barrow .lb { font-size:11px; color:var(--lx-t3); min-width:56px; }

  /* ── 统计三栏 ── */
  .stat3 { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; padding:14px 20px 0; }
  .st { background:var(--lx-card); border-radius:14px; padding:12px 10px; text-align:center; }
  .st .v { font-family:"LxNum","Licium"; font-size:20px; font-weight:600; }
  .st .v small { font-size:11px; color:var(--lx-t2); margin-left:2px; }
  .st .l { font-size:11px; color:var(--lx-t3); margin-top:5px; }

  /* ── 枪/盖状态胶囊 ── */
  .pills { display:flex; gap:8px; padding:14px 20px 0; flex-wrap:wrap; }
  .pill { display:inline-flex; align-items:center; gap:6px; font-size:12px;
          padding:6px 12px; border-radius:20px; background:var(--lx-card); color:var(--lx-t2); }
  .pill .d { width:6px; height:6px; border-radius:50%; background:var(--lx-t3); }
  .pill.on .d { background:var(--lx-green); }
  .pill.warn .d { background:var(--lx-orange); }

  /* ── 记录（年折叠）── */
  .sect { padding:18px 20px 0; }
  .sect h2 { font-size:14px; font-weight:500; margin:0 0 10px; }
  .year { border-radius:14px; background:var(--lx-card); margin-bottom:10px; overflow:hidden; }
  .yhead { display:flex; align-items:center; min-height:52px; padding:0 16px;
           cursor:pointer; transition:background .15s; }
  .yhead:hover { background:rgba(0,0,0,.03); }
  .yhead .yn { font-size:15px; font-weight:500; }
  .yhead .ys { margin-left:10px; font-size:12px; color:var(--lx-t3); }
  .yhead .ar { margin-left:auto; color:var(--lx-t3); transition:transform .2s; }
  .year.open .yhead .ar { transform:rotate(90deg); }
  .ymonths { display:none; padding:0 16px 8px; }
  .year.open .ymonths { display:block; }
  .m { display:flex; align-items:center; min-height:46px; cursor:pointer;
       border-top:1px solid var(--lx-line); }
  .m:hover { background:rgba(0,0,0,.02); }
  .m .mn { font-size:14px; color:var(--lx-t2); }
  .m .mv { margin-left:auto; font-family:"LxNum"; font-size:14px; font-weight:500; }
  .m .mu { font-size:11px; color:var(--lx-t3); margin-left:3px; }
  .m .mt { font-size:11px; color:var(--lx-t3); margin-left:8px; min-width:34px; text-align:right; }
  .empty { text-align:center; color:var(--lx-t3); font-size:13px; padding:16px 0; }

  /* ── 明细列表 ── */
  .list { padding:0 20px; }
  .listhead { font-size:12px; color:var(--lx-t3); padding:12px 0 6px; }
  .rec { display:flex; align-items:center; padding:10px 0;
         border-bottom:1px solid var(--lx-line); font-size:13px; }
  .rec:last-child { border-bottom:none; }
  .rec .tag { font-size:11px; padding:2px 7px; border-radius:6px;
              background:#EAF1FF; color:var(--lx-blue); margin-right:8px; }
  .rec .tag.ac { background:#E9F7EE; color:#2C9E4B; }
  .rec .t { color:var(--lx-t2); }
  .rec .c { margin-left:auto; font-family:"LxNum"; font-weight:500; }
  .rec .u { font-size:11px; color:var(--lx-t3); margin-left:3px; }

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

  /* ── 刷新按钮 ── */
  .refresh { width:30px; height:30px; border-radius:50%; display:flex;
             align-items:center; justify-content:center; cursor:pointer;
             transition:background .15s, transform .3s; }
  .refresh:hover { background:var(--lx-card); }
  .refresh:active { transform:scale(.9); }
  .refresh img { width:17px; height:17px; opacity:.6; }
  .refresh.spin { animation:lspin .9s linear infinite; }
  @keyframes lspin { to { transform:rotate(360deg); } }
  /* ── 状态提示（错误/空态）── */
  .state { text-align:center; padding:20px 16px; }
  .state .t { font-size:13.5px; color:var(--lx-t2); }
  .state .d { font-size:11.5px; color:var(--lx-t3); margin-top:6px; line-height:1.55; }
  .state .retry { display:inline-block; margin-top:12px; font-size:13px;
                  color:var(--lx-blue); cursor:pointer; padding:6px 16px;
                  border-radius:10px; background:rgba(10,88,246,.07); }
  .state .retry:hover { background:rgba(10,88,246,.12); }

  /* ── 下拉刷新 ── */
  .ptr { position:absolute; left:0; right:0; top:0; height:0; overflow:hidden;
         display:flex; align-items:center; justify-content:center;
         transition:height .2s ease; pointer-events:none; }
  .ptr .sp { width:20px; height:20px; border-radius:50%;
             border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
             animation:lspin .8s linear infinite; }
  .ptr .tx { font-size:11.5px; color:var(--lx-t3); margin-left:8px; }
`;

class LixiangChargePage extends HTMLElement {

  /* ── 自动绑定（与 app-home 同一引擎，用户不用手填实体 ID）── */
  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) {
        out = new AB(this._hass, this._config || {}).resolve() || {};
      }
    } catch (e) { /* 引擎不可用时退回手填 */ }
    // ★ 只有非空结果才缓存：hass.entities 未就绪时返回 {} ，
    //   若缓存会导致永久空绑定（真实踩过的坑）
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  /** 取实体：手填配置 > 自动发现 */
  _eid(field) {
    const c = this._config || {};
    const manual = c[field];
    if (typeof manual === "string" && manual.includes(".")) return manual;
    return (this._autoBind() || {})[field] || null;
  }

  /** 嵌套组也支持自动发现 */
  _eidIn(group, key) {
    const c = this._config || {};
    const m = (c[group] || {})[key];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[key] || null;
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
  setConfig(config) {
    this._config = config || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base;
    this._openYears = new Set();
    this._selMonth = null;
    this._years = null;
    this._monthRecords = null;
    this._built = false;
  }
  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    this._update();
  }
  getCardSize() { return 16; }

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
    if (!s || ["unknown", "unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id); return s ? s.state : null; }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style");
    st.textContent = STYLE; this.appendChild(st);
    const c = this._config;
    const root = document.createElement("div");
    root.className = "root";
    root.dataset.theme = c.theme || "light";
    root.innerHTML = `
      <div class="ptr" id="ptr"><div class="sp"></div><div class="tx">下拉刷新</div></div>
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" alt="返回">
        <h1>${I18N.title}</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新数据">
          <img src="${__iconBase}/ic_home_return.webp" alt="" style="transform:rotate(-90deg)">
        </div>
      </div>
      <div class="hero">
        <div class="row1">
          <span class="dot" id="dot"></span>
          <span class="st" id="st">—</span>
          <span class="sub" id="sub"></span>
        </div>
        <div class="barrow">
          <span class="lb">${I18N.limit}</span>
          <div class="bar"><i id="bar" style="width:0%"></i></div>
          <span class="p" id="limitp">—</span>
        </div>
        <div class="metrics">
          <div class="m"><div class="v"><span id="m-power">—</span><small>kW</small></div>
            <div class="l">${I18N.power}</div></div>
          <div class="m"><div class="v"><span id="m-remain">—</span><small>min</small></div>
            <div class="l">${I18N.remain}</div></div>
          <div class="m"><div class="v"><span id="m-mode">—</span></div>
            <div class="l">${I18N.mode}</div></div>
        </div>
      </div>
      <div class="stat3">
        <div class="st"><div class="v"><span id="s-month">—</span><small>kWh</small></div>
          <div class="l">${I18N.monthKwh}</div></div>
        <div class="st"><div class="v"><span id="s-times">—</span><small>${I18N.times}</small></div>
          <div class="l">${I18N.monthTimes}</div></div>
        <div class="st"><div class="v"><span id="s-total">—</span><small>kWh</small></div>
          <div class="l">${I18N.totalKwh}</div></div>
      </div>
      <div class="pills">
        <span class="pill" id="p-ac"><span class="d"></span>${I18N.acGun} <b id="v-ac">—</b></span>
        <span class="pill" id="p-dc"><span class="d"></span>${I18N.dcGun} <b id="v-dc">—</b></span>
        <span class="pill" id="p-cover"><span class="d"></span>${I18N.portCover} <b id="v-cover">—</b></span>
        <span class="pill" id="p-appt"><span class="d"></span>${I18N.appt} <b id="v-appt">—</b></span>
        <span class="pill" id="p-fault"><span class="d"></span>${I18N.fault} <b id="v-fault">—</b></span>
      </div>
      <div class="sect">
        <h2>${I18N.history}</h2>
        <div id="years"><div class="empty">${I18N.loading}</div></div>
      </div>
      <div class="list" id="list"></div>
    `;
    this.appendChild(root);

    const _bk = this.querySelector("#back");
    this._a11y(_bk, "返回", () => _bk.click());
    _bk.addEventListener("click", () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      history.pushState(null, "", p);
      this.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
    });
    const rf2 = this.querySelector("#refresh");
    const doRefresh2 = () => this._refreshAll();
    this._a11y(rf2, "刷新数据", doRefresh2);
    rf2.addEventListener("click", doRefresh2);

    
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
          Promise.resolve(this.this._refreshAll()).finally(() => {
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

  /** 手动刷新 */
  async _refreshAll() {
    const rf = this.querySelector("#refresh");
    if (rf) rf.classList.add("spin");
    this._years = null; this._monthRecords = null; this._fetching = false;
    this._error = null;
    try {
      await this._fetchStats();
      if (this._selMonth) await this._fetchMonth(this._selMonth.year, this._selMonth.month);
    } finally {
      if (rf) rf.classList.remove("spin");
      this._renderYears(); this._renderList();
    }
  }

  async _fetchStats() {
    if (!this._hass || this._years || this._fetching) return;
    this._fetching = true;
    try {
      const r = await this._hass.callService("lixiang_auto", "get_charge", {}, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const rows = first && first.data;   // [{year, month, chargingTimes, chargingCapacity}]
      if (Array.isArray(rows) && rows.length) {
        // 按年分组
        const byYear = {};
        rows.forEach((x) => {
          const y = String(x.year);
          (byYear[y] = byYear[y] || []).push(x);
        });
        this._years = Object.keys(byYear).sort((a, b) => b - a).map((y) => ({
          year: Number(y),
          months: byYear[y].sort((a, b) => b.month - a.month),
        }));
        const y0 = this._years[0] && this._years[0].year;
        if (y0 != null) this._openYears.add(String(y0));
        this._renderYears();
      }
    } catch (e) {
      this._error = (e && e.message) || "网络请求失败";
    } finally { this._fetching = false; }
  }

  async _fetchMonth(year, month) {
    if (!this._hass) return;
    this._monthRecords = null; this._renderList();
    try {
      const r = await this._hass.callService("lixiang_auto", "get_charge",
        { dt: `${year}-${month}`, charging_type: 2 }, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const rows = first && first.data;
      if (Array.isArray(rows)) this._monthRecords = rows;
      // 也拉直流
      const r2 = await this._hass.callService("lixiang_auto", "get_charge",
        { dt: `${year}-${month}`, charging_type: 1 }, undefined, true, true);
      const p2 = (r2 && r2.response) || r2;
      const f2 = p2 && Object.values(p2)[0];
      if (Array.isArray(f2 && f2.data)) {
        this._monthRecords = (this._monthRecords || []).concat(f2.data);
      }
    } catch (e) { /* 静默 */ }
    this._renderList();
  }

  _renderYears() {
    const box = this.querySelector("#years");
    if (!box) return;
    const yl = this._years;
    if (!yl || !yl.length) {
      if (this._error) {
        box.innerHTML = `<div class="state"><div class="t">充电记录加载失败</div>
          <div class="d">${this._error}<br>可能是网络波动或车辆服务暂时不可用</div>
          <div class="retry" id="retry2">重新加载</div></div>`;
        const r = box.querySelector("#retry2");
        if (r) { this._a11y(r, "重新加载", () => this._refreshAll());
                 r.addEventListener("click", () => this._refreshAll()); }
      } else if (this._fetching) {
        box.innerHTML = `<div class="state"><div class="t">${I18N.loading}</div>
          <div class="d">正在从车辆获取充电记录…</div></div>`;
      } else {
        box.innerHTML = `<div class="state"><div class="t">暂无充电记录</div>
          <div class="d">车辆尚未产生充电数据</div></div>`;
      }
      return;
    }
    box.innerHTML = yl.map((y) => {
      const tot = y.months.reduce((a, m) => a + Number(m.chargingCapacity || 0), 0);
      const cnt = y.months.reduce((a, m) => a + Number(m.chargingTimes || 0), 0);
      const open = this._openYears.has(String(y.year));
      const rows = y.months.map((m) => {
        const sel = this._selMonth && this._selMonth.year === y.year && this._selMonth.month === m.month;
        return `<div class="m${sel ? " sel" : ""}" data-y="${y.year}" data-m="${m.month}">
            <span class="mn">${m.month} 月</span>
            <span class="mt">${m.chargingTimes} ${I18N.times}</span>
            <span class="mv">${Number(m.chargingCapacity).toFixed(1)}</span>
            <span class="mu">kWh</span></div>`;
      }).join("");
      return `<div class="year${open ? " open" : ""}" data-year="${y.year}">
          <div class="yhead"><span class="yn">${y.year} ${I18N.year}</span>
            <span class="ys">${y.months.length} 个月 · ${cnt} ${I18N.times} · ${tot.toFixed(0)} kWh</span>
            <span class="ar">›</span></div>
          <div class="ymonths">${rows}</div></div>`;
    }).join("");
    box.querySelectorAll(".yhead").forEach((h) => {
      this._a11y(h, `${h.parentElement.dataset.year} 年 展开/收起`, () => h.click());
      h.addEventListener("click", () => {
        const y = h.parentElement.dataset.year;
        if (this._openYears.has(y)) this._openYears.delete(y); else this._openYears.add(y);
        this._renderYears();
      });
    });
    box.querySelectorAll(".m").forEach((m) => {
      this._a11y(m, `${m.dataset.y} 年 ${m.dataset.m} 月 充电明细`, () => m.click());
      m.addEventListener("click", async () => {
        this._selMonth = { year: Number(m.dataset.y), month: Number(m.dataset.m) };
        this._renderYears();
        await this._fetchMonth(this._selMonth.year, this._selMonth.month);
      });
    });
  }

  _renderList() {
    const box = this.querySelector("#list");
    if (!box) return;
    if (!this._selMonth) { box.innerHTML = ""; return; }
    const rows = this._monthRecords || [];
    const head = `<div class="listhead">${this._selMonth.year} 年 ${this._selMonth.month} 月 · 充电明细</div>`;
    if (!rows.length) { box.innerHTML = head + `<div class="empty">${I18N.noData}</div>`; return; }
    const sorted = rows.slice().sort((a, b) => Number(b.startTime) - Number(a.startTime));
    box.innerHTML = head + sorted.map((r) => {
      const d = new Date(Number(r.startTime));
      const mm = `${d.getMonth() + 1}/${d.getDate()}`;
      const hh = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      const isDC = Number(r.chargingType) === 1;
      return `<div class="rec">
          <span class="tag${isDC ? "" : " ac"}">${isDC ? I18N.dc : I18N.ac}</span>
          <span class="t">${mm} ${hh}</span>
          <span class="c">${Number(r.chargingCapacity).toFixed(2)}</span><span class="u">kWh</span>
        </div>`;
    }).join("");
  }

  _update() {
    if (!this._built) return;
    const c = this._config, q = (s) => this.querySelector(s);

    // 充电状态
    const stt = this._txt(this._eid("status_charge"));
    const done = this._txt(this._eid("complete"));
    const isCharging = stt && String(stt).includes("充电中");
    const isDone = done && String(done).includes("完成");
    q("#st").textContent = isCharging ? I18N.charging : (isDone ? I18N.done : (stt || "—"));
    q("#dot").className = "dot" + (isCharging ? " on" : "");
    const fault = this._txt(this._eid("fault"));
    if (fault && String(fault) !== "off" && String(fault) !== "正常") {
      q("#dot").className = "dot err";
    }
    q("#sub").textContent = isCharging ? "⚡ 充电中" : "";

    // 上限 + 电量
    const lim = this._num(this._eid("limit"));
    const soc = this._num(this._eid("soc"));
    q("#limitp").textContent = lim == null ? "—" : lim + "%";
    const bar = q("#bar");
    if (soc != null) { bar.style.width = Math.max(0, Math.min(100, soc)) + "%"; }
    else if (lim != null) { bar.style.width = lim + "%"; }

    // 三项
    const p = this._num(this._eid("power")), rm = this._num(this._eid("remain")), md = this._txt(this._eid("mode"));
    q("#m-power").textContent = p == null ? "—" : p;
    q("#m-remain").textContent = rm == null ? "—" : rm;
    q("#m-mode").textContent = md || "—";
    q("#m-mode").className = "v" + ((md && isNaN(parseFloat(md))) ? " txt" : "");

    // 电量三栏
    const mk = this._num(this._eid("month_kwh"));
    let tk = this._num(this._eid("month_times"));      // ★ let（下方可能回填）
    const tot = this._num(this._eid("total_kwh"));
    q("#s-month").textContent = mk == null ? "—" : mk;
    if (tk == null && this._years && this._years.length) {
      const y0 = this._years[0];
      const mCur = new Date().getMonth() + 1;
      const hit = (y0.months || []).find((x) => x.month === mCur);
      tk = hit ? Number(hit.chargingTimes) : null;
    }
    if (tk == null && this._years && this._years.length) {
      const cur = new Date().getMonth() + 1;
      const y0 = this._years[0] || {};
      const hit = (y0.months || []).find((x) => Number(x.month) === cur);
      if (hit && hit.chargingTimes != null) tk = hit.chargingTimes;
    }
    q("#s-times").textContent = tk == null ? "—" : tk;
    q("#s-total").textContent = tot == null ? "—" : tot;

    // 胶囊
    const set = (pill, val, eid) => {
      const v = this._txt(eid);
      q(val).textContent = v == null ? "—" : (v === "on" ? "已连接" : (v === "off" ? "未连接" : v));
      const el = q(pill);
      if (el) el.className = "pill" + (v === "on" ? " on" : "");
    };
    set("#p-ac", "#v-ac", this._eid("ac_gun"));
    set("#p-dc", "#v-dc", this._eid("dc_gun"));
    set("#p-cover", "#v-cover", this._eid("port_cover"));
    set("#p-appt", "#v-appt", this._eid("appointment"));
    const fv = this._txt(this._eid("fault"));
    q("#v-fault").textContent = fv == null ? "—" : (fv === "off" ? "正常" : fv);
    q("#p-fault").className = "pill" + (fv && fv !== "off" ? " warn" : "");

    this._fetchStats();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangChargePage);

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "充电（二级页）",
  description: "充电实时状态 + 按月记录（年折叠）+ 单次明细",
  preview: true,
});
