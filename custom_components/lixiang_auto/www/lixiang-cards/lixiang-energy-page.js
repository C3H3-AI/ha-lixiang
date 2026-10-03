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
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
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
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#3CC75A; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F5F5F7; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
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
  .m { display:flex; align-items:center; padding:11px 0; cursor:pointer; }
  .m .mn { font-size:14px; color:var(--lx-t2); }
  .m .mt { font-size:11.5px; color:var(--lx-t3); margin-left:10px; }
  .m .mv { margin-left:auto; font-family:"LxNum"; font-size:14px; font-weight:500; }
  .m .mu { font-size:11px; color:var(--lx-t3); margin-left:3px; }
  .m.sel .mn { color:var(--lx-blue); font-weight:500; }
  .daily { padding:4px 0 8px; }
  .drow { display:flex; justify-content:space-between; padding:7px 0; font-size:12.5px; }
  .drow .dd { color:var(--lx-t2); }
  .drow .dn { font-family:"LxNum"; font-weight:500; }
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
    root.className = "root";
    root.innerHTML = `
      <div class="topbar">
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" alt="返回">
        <h1>${I18N.title}</h1>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
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
            <div class="v"><span id="lg-elec-p">—</span><img src="${__iconBase}/ic_home_electricity.webp" alt=""></div>
            <div class="l">${I18N.elec}</div>
          </div>
          <div class="lg">
            <div class="v"><img src="${__iconBase}/ic_home_oil.webp" alt=""><span id="lg-fuel-p">—</span></div>
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

      <div class="years" id="years"><div class="empty">${I18N.loading}</div></div>
      <div class="daily" id="daily" style="display:none"></div>
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
      const rows = ms.map((m) => {
        const sel = this._selMonth && this._selMonth.year === y.year && this._selMonth.month === m.month;
        return `<div class="m${sel ? " sel" : ""}" data-y="${y.year}" data-m="${m.month}">
            <span class="mn">${m.month} 月</span>
            <span class="mv">${Number(m.travelMil).toFixed(1)}</span>
            <span class="mu">km</span></div>`;
      }).join("");
      return `<div class="year${open ? " open" : ""}" data-year="${y.year}">
          <div class="yhead"><span class="yn">${y.year}年</span>
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
      const act = () => {
        this._selMonth = { year: Number(m.dataset.y), month: Number(m.dataset.m) };
        this._renderYears(); this._renderDaily();
        this._fetchMonthDaily(this._selMonth.year, this._selMonth.month, false);
      };
      this._a11y(m, `${m.dataset.y} 年 ${m.dataset.m} 月`, act);
      m.addEventListener("click", act);
    });
  }

  _renderDaily() {
    const box = this.querySelector("#daily");
    if (!box) return;
    if (!this._selMonth) { box.style.display = "none"; return; }
    box.style.display = "";
    const rows = this._monthDaily || [];
    const head = `<div class="tabs">
        <div class="tab${this._tab === "mileage" ? " on" : ""}" data-tab="mileage">每日里程</div>
        <div class="tab${this._tab === "elec" ? " on" : ""}" data-tab="elec">每日耗电</div>
        <div class="tab${this._tab === "fuel" ? " on" : ""}" data-tab="fuel">每日耗油</div>
      </div>`;
    if (!rows.length) { box.innerHTML = head + `<div class="empty">${I18N.noData}</div>`; this._bindTabs(); return; }
    const pick = { mileage:"mileage", elec:"elecEnergy", fuel:"fuelConsumption" }[this._tab];
    const unit = this._tab === "mileage" ? "km" : (this._tab === "elec" ? "kWh" : "L");
    box.innerHTML = head + `<div style="font-size:12px;color:var(--lx-t3);padding:4px 0 6px">
        ${this._selMonth.year}年${this._selMonth.month}月</div>` +
      rows.map((r) => {
        const v = r[pick];
        return `<div class="drow"><span class="dd">${r.dayOfMonth} 日</span>
          <span class="dn">${v ? v + " " + unit : "—"}</span></div>`;
      }).join("");
    this._bindTabs();
  }

  _bindTabs() {
    this.querySelectorAll(".tab").forEach((t) => {
      const act = () => { this._tab = t.dataset.tab; this._renderDaily(); };
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
      { value: elecFrac, color: "#3CC75A" },
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
