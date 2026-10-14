/* lixiang-overview-card —— 理想汽车「车辆总览」卡片
 *
 * ★ 2026-10-13 新增
 *
 * 设计参考社区「尊界 S800 车辆总览」卡的深色玻璃风格：
 *   三栏（身份 / 能量 / 车况）→ 窄屏两栏 → 手机单栏。
 * 但数据来源完全不同：
 *   · 尊界卡要求用户手填 28 个实体 ID；本卡走**实体自动发现**，
 *     默认零配置（可选用 config.entities 覆盖个别字段）。
 *   · 车型名、车图、车漆色都由集成接口给，与实车一致。
 *
 * 只读展示卡：不发送任何车辆控制指令。
 */
const CARD_TAG = "lixiang-overview-card";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先

// 内置图标回退（与其它卡片一致）
const __lxIconFallback = (typeof window !== "undefined" && (window.__lxIconFallback = window.__lxIconFallback || function (img) {
  if (img.dataset.lxFb) return;
  img.dataset.lxFb = "1";
  const s = img.getAttribute("src") || "";
  const rel = s.replace(/^\/local\/lixiang-icons\//, "");
  if (rel === s) return;
  img.src = "/lixiang_auto/lixiang-icons/" + rel;
})) || function () {};

const STYLE = `
  :host { display:block; container-type:inline-size; color:#eef2f8;
          font-family:"Licium",-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
          -webkit-tap-highlight-color:transparent; }
  * { box-sizing:border-box; }
  ha-card { display:block; overflow:hidden; border-radius:26px!important;
            border:1px solid #c2cce535!important; color:#eef2f8!important;
            background:radial-gradient(ellipse at 8% 0%,#5b7a9c3d,transparent 52%),
                       linear-gradient(120deg,#243444eb,#232840eb)!important;
            box-shadow:0 12px 36px #0002!important; }
  .main { display:grid; grid-template-columns:minmax(0,1.26fr) minmax(0,1fr) minmax(0,.86fr);
          gap:26px; padding:22px 26px 16px; }
  .identity,.energy,.condition { min-width:0; }
  .eyebrow { font-size:10px; color:#9fb6d6; letter-spacing:4px; font-weight:650; }
  .title { font-size:29px; font-weight:600; letter-spacing:1.5px; margin:5px 0 3px; }
  .title b { font-weight:350; letter-spacing:1px; margin-left:8px; }
  .subtitle { color:#adbbcd; font-size:12px; letter-spacing:.6px; }
  .badges { display:flex; gap:7px; flex-wrap:wrap; margin-top:12px; }
  .badge { font-size:11px; padding:4px 10px; border:1px solid #ffffff26; border-radius:30px;
           color:#d4dceb; background:#ffffff08; white-space:nowrap; }
  .badge.online { color:#a5e3d2; border-color:#91d8c333; background:#89d5bc12; }
  .badge.offline { color:#cfd6e0; }
  .dot { display:inline-block; width:5px; height:5px; border-radius:50%;
         background:currentColor; margin-right:5px; vertical-align:middle; }
  .art { position:relative; height:170px; margin:6px 0 0; overflow:hidden;
         border-radius:16px; }
  .art.has-photo { border:1px solid #ffffff14; background:#0d1622; }
  .art:before { content:''; position:absolute; inset:22px 12px 4px;
                background:radial-gradient(ellipse,#c9d6ea1a,transparent 68%); }
  .art img { position:absolute; inset:0; width:100%; height:100%;
             object-fit:contain; pointer-events:none; }
  .art-note { color:#9fadc2; font-size:9px; text-align:right; margin-top:6px; }
  .range-main { display:flex; align-items:baseline; gap:8px; margin-bottom:13px; flex-wrap:wrap; }
  .range-main>span { color:#b6c4d6; font-size:12px; flex:1; }
  .range-main>b { font-size:36px; font-weight:550; letter-spacing:-1.2px; line-height:1.3; }
  .range-main small { font-size:13px; color:#bcc8d8; letter-spacing:0; }
  .meter { padding:12px 15px; margin-top:10px; border-radius:15px;
           background:#ffffff06; border:1px solid #ffffff10; }
  .meter-top { display:flex; align-items:baseline; justify-content:space-between;
               font-size:12px; color:#cbd7e5; }
  .meter-top strong { font-size:23px; font-weight:500; line-height:1.15; }
  .meter-top small { font-size:12px; color:#b7c5d6; }
  .track { height:5px; background:#ffffff12; border-radius:10px; margin:10px 0; overflow:hidden; }
  .track i { display:block; height:100%; border-radius:10px;
             background:linear-gradient(90deg,#4c9aff,#9fd0ff); }
  .fuel .track i { background:linear-gradient(90deg,#a98d63,#e6d2ab); }
  .range { display:flex; justify-content:space-between; font-size:11px; color:#aebed0; }
  .range b { font-size:16px; color:#eef4fc; font-weight:500; }
  .range small { font-size:11px; font-weight:400; color:#b4c2d4; }
  .charge { display:flex; justify-content:space-between; gap:8px; margin:12px 2px 0;
            font-size:11px; color:#c0cddd; }
  .charge b { color:#e2e9f5; font-weight:500; }
  .section-label { display:flex; justify-content:space-between; align-items:center;
                   color:#c1cddd; font-size:12px; margin:6px 0 10px; }
  .section-label small { font-size:10px; color:#8d9db3; }
  .tire-grid { height:158px; display:grid; grid-template-columns:1fr 72px 1fr;
               grid-template-rows:1fr 1fr; gap:6px 4px; align-items:center; text-align:center; }
  .tire { display:flex; flex-direction:column; align-items:center; }
  .tire span { font-size:10px; color:#a5b6cb; }
  .tire b { font-size:22px; font-weight:450; line-height:1.35; }
  .tire.low b { color:#e8b96b; }
  .tire small { font-size:9px; color:#8fa3bb; }
  .top-car { grid-column:2; grid-row:1/3; width:72px; height:148px; opacity:.92; }
  .cabin { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:13px; }
  .cabin .detail-stat { padding:10px 9px; border:1px solid #ffffff10; border-radius:12px;
                        background:#ffffff03; }
  .detail-stat { min-width:0; display:flex; flex-direction:column; gap:4px; }
  .detail-stat span { font-size:10px; color:#a3b2c6; }
  .detail-stat b { font-size:15px; font-weight:500; color:#e9eff8; white-space:nowrap;
                   overflow:hidden; text-overflow:ellipsis; }
  .footer { display:flex; justify-content:space-between; gap:12px; align-items:center;
            padding:10px 26px; border-top:1px solid #ffffff12; background:#0000000c;
            flex-wrap:wrap; font-size:10px; color:#a8b6c8; }
  .fresh { color:#b2c9b9; }
  .stale { color:#dfba83; }
  .details { border-top:1px solid #ffffff0c; }
  .details summary { font-size:11px; color:#bac7d7; padding:11px 26px; cursor:pointer;
                     user-select:none; }
  .details summary:focus-visible { outline:2px solid #a9d7ed; outline-offset:-4px; }
  .detail-grid { padding:4px 26px 16px; display:grid;
                 grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }
  .note { font-size:10px; color:#98a7bb; padding:0 26px 15px; line-height:1.7; }

  /* ── 超宽屏（电脑/分区视图占满整行）────────────────────────────
     ★ 2026-10-14：卡片拉到 1400px+ 时三栏被拉散、内容稀疏（大片空白）。
     处理：① 内容区限宽 1440px 居中，避免无限拉伸；
           ② 同档放大车图与字号，让宽屏有"大屏该有的信息密度"。 */
  @container (min-width: 1250px) {
    .main { max-width:1440px; margin:0 auto; gap:34px; padding:26px 34px 20px; }
    .title { font-size:34px; }
    .subtitle { font-size:13px; }
    .badge { font-size:12px; padding:5px 12px; }
    .art { height:214px; }
    .art-note { font-size:10px; }
    .range-main>b { font-size:44px; }
    .range-main>span { font-size:13px; }
    .meter { padding:15px 18px; margin-top:12px; border-radius:17px; }
    .meter-top strong { font-size:26px; }
    .track { height:6px; margin:12px 0; }
    .range b { font-size:18px; }
    .charge { font-size:12px; margin-top:14px; }
    .section-label { font-size:13px; margin:8px 0 12px; }
    .tire-grid { height:196px; grid-template-columns:1fr 96px 1fr; gap:8px 6px; }
    .top-car { width:96px; height:184px; }
    .tire b { font-size:25px; }
    .tire span { font-size:11px; }
    .cabin { gap:10px; margin-top:16px; }
    .cabin .detail-stat { padding:12px 11px; }
    .cabin .detail-stat b { font-size:17px; }
    .cabin .detail-stat span { font-size:11px; }
    .footer, .details summary, .detail-grid, .note { max-width:1440px; margin-left:auto; margin-right:auto; }
    .footer { padding:12px 34px; font-size:11px; }
    .detail-grid { gap:20px; }
  }

  @container (max-width: 950px) {
    .main { gap:18px; padding:20px; }
    .title { font-size:25px; }
    .art { height:160px; }
    .tire-grid { grid-template-columns:1fr 58px 1fr; }
    .top-car { width:58px; }
    .footer { padding:10px 20px; }
  }
  /* 中等宽度（HA masonry 单列 ≈500-750px）：身份区与能量区**并排**，
     而不是把身份区拉满整行（那样在电脑上像手机版）。车况整行放下面。 */
  @container (max-width: 750px) {
    .main { grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px 18px; }
    .condition { grid-column:1/-1; padding-top:14px; border-top:1px solid #ffffff12; }
    .tire-grid { grid-template-columns:minmax(0,1fr) 84px minmax(0,1fr); height:170px; }
    .top-car { width:84px; height:158px; }
    .title { font-size:26px; }
    .art { height:150px; }
    .detail-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
  }
  @container (max-width: 480px) {
    .main { grid-template-columns:1fr; padding:20px 18px 14px; gap:18px; }
    .identity { grid-column:auto; }
    .art { height:158px; margin:2px -4px 0; }
    .energy { border-top:1px solid #ffffff12; padding-top:14px; }
    .condition { border-top:1px solid #ffffff12; padding-top:10px; }
    .tire-grid { grid-template-columns:1fr 88px 1fr; height:164px; }
    .top-car { width:88px; height:156px; }
    .footer { padding:12px 18px; gap:5px; }
    .detail-grid { grid-template-columns:repeat(2,minmax(0,1fr)); padding:4px 18px 16px; }
    .details summary { padding:12px 18px; }
    .note { padding:0 18px 14px; }
  }
  @media (prefers-reduced-motion: reduce) { * { transition:none!important; } }
`;

// 无 DOM 环境（Node 单测）也能导入：HTMLElement 缺失时退化为普通类
const __Base = (typeof HTMLElement !== "undefined") ? HTMLElement : class {};

class LixiangOverviewCard extends __Base {
  constructor() {
    super();
    // ★ shadow DOM：与尊界卡同款做法。同时 `:host{container-type:inline-size}`
    //   只有在 shadow root 里才成立 —— 用 light DOM 时容器查询不会生效，
    //   窄屏断点会失效（实测：400px 下仍是三栏、数字被挤断）。
    if (typeof this.attachShadow === "function") this.attachShadow({ mode: "open" });
    this._built = false;
    this._bindCache = null;
    this._artDone = false;
  }

  setConfig(config) {
    if (config && config.entities && typeof config.entities !== "object") {
      throw new Error("entities 必须是「字段: 实体ID」的对象");
    }
    this._config = config || {};
    this._built = false;
    this._bindCache = null;
    if (this._hass) this._build();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    const sig = this._signature();
    if (sig !== this._sig) { this._sig = sig; this._render(); }
  }

  connectedCallback() {
    this._tm = setInterval(() => { if (this._hass) this._render(); }, 60000);
  }
  disconnectedCallback() { clearInterval(this._tm); }
  getCardSize() { return 6; }
  getGridOptions() { return { columns: 48, rows: "auto", min_columns: 12 }; }

  /* ---------- 实体解析：手填 > 自动发现 ---------- */
  _autoBind() {
    if (this._bindCache) return this._bindCache;
    let out = {};
    try {
      const AB = window.LixiangAutoBind;
      if (AB && this._hass) out = new AB(this._hass, this._config || {}).resolve() || {};
    } catch (e) { /* 引擎不可用 → 全走手填 */ }
    if (out && Object.keys(out).length) this._bindCache = out;
    return out;
  }

  _eid(field) {
    const m = (this._config.entities || {})[field];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[field] || null;
  }

  _st(field) { const id = this._eid(field); return (id && this._hass) ? this._hass.states[id] : null; }
  state(field) { const s = this._st(field); return s ? s.state : undefined; }
  _num(v) {
    if (v === undefined || v === null || v === "" || v === "unknown" || v === "unavailable") return null;
    const n = Number(String(v).replace(/[^\d.\-+]/g, ""));
    return Number.isFinite(n) ? n : null;
  }
  num(field) { return this._num(this.state(field)); }
  fmt(field, d = 0) {
    const n = this.num(field);
    if (n === null) return "—";
    return n.toLocaleString("zh-CN", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  /** 实体单位（小写）—— 不假设单位，按实体实际单位换算/显示 */
  _unit(field) {
    const st = this._st(field);
    return String(((st && st.attributes) || {}).unit_of_measurement || "").toLowerCase();
  }

  /** 胎压 → {v, unit}：实体是 kPa 时换算成 bar（与「车辆健康」页同一规则） */
  _pressure(field) {
    const v = this.num(field);
    if (v === null) return { v: null, unit: "bar" };
    const u = this._unit(field);
    if (u.includes("kpa")) return { v: v / 100, unit: "bar" };
    if (u.includes("psi")) return { v: v / 14.5038, unit: "bar" };
    if (u.includes("bar")) return { v, unit: "bar" };
    return { v, unit: u || "bar" };
  }

  /** 百分比类字段：只有实体单位确实是 % 才当作百分比（可画进度条） */
  _pct(field) {
    const v = this.num(field);
    if (v === null) return null;
    const u = this._unit(field);
    if (u && !u.includes("%")) return null;
    return Math.max(0, Math.min(100, v));
  }

  esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* 车型（读设备注册表；config.model_name 可覆盖） */
  _model() {
    const c = this._config || {};
    if (c.model_name) return { name: c.model_name, series: this._series(c.model_name) };
    const h = this._hass;
    if (h && h.devices) {
      for (const d of Object.values(h.devices)) {
        const isLi = (d.manufacturer || "").includes("理想")
          || JSON.stringify(d.identifiers || []).includes("lixiang");
        if (!isLi) continue;
        if (c.vin && !JSON.stringify(d.identifiers || []).includes(c.vin)) continue;
        const mdl = d.model || d.name || "";
        return { name: d.name || mdl, series: this._series(mdl) };
      }
    }
    return { name: "", series: "" };
  }
  _series(text) {
    const m = String(text || "").match(/(MEGA|L[6-9]|i[6-9]|ONE)/i);
    return m ? m[1].toUpperCase() : "";
  }

  /* 数据新鲜度：取已用实体的最新 last_updated */
  _lastUpdated() {
    const h = this._hass; if (!h) return null;
    let best = 0;
    for (const f of ["battery", "range_total", "range_elec", "online", "status"]) {
      const s = this._st(f);
      if (s && s.last_updated) {
        const t = Date.parse(s.last_updated);
        if (Number.isFinite(t) && t > best) best = t;
      }
    }
    return best || null;
  }
  _fmtTime(ts) {
    if (!ts) return "暂无时间";
    const tz = (this._hass && this._hass.config && this._hass.config.time_zone) || "Asia/Shanghai";
    return new Date(ts).toLocaleString("zh-CN", {
      timeZone: tz, month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  }

  _signature() {
    const h = this._hass;
    if (!h) return "";
    const fields = ["battery", "range_total", "range_elec", "range_fuel", "fuel",
      "tire_lf", "tire_rf", "tire_lr", "tire_rr", "room_temp", "target_temp",
      "ac", "charge_status", "charge_power", "charge_remain", "online", "status",
      "sentry", "total_km", "month_km", "wltc_total", "charge_voltage",
      "charge_current", "pack_voltage", "total_kwh"];
    const parts = fields.map((f) => this.state(f));
    return JSON.stringify(parts) + "|" + Math.floor(Date.now() / 60000);
  }

  /* ---------- 渲染 ---------- */
  _build() {
    const root = this.shadowRoot;
    while (root.firstChild) root.removeChild(root.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; root.appendChild(st);
    const card = document.createElement("ha-card");
    card.innerHTML = '<div class="body"></div>';
    root.appendChild(card);
    this._body = card.querySelector(".body");
    this._built = true;
    this._render();
  }

  _render() {
    if (!this._built || !this._body) return;
    const open = this._body.querySelector("details") ? this._body.querySelector("details").open : false;

    const online = this.state("online");
    const onlineOn = online === "在线" || online === "on" || online === "true";
    const onlineOff = online === "离线" || online === "off" || online === "false";
    const sentry = this.state("sentry");
    const acState = this.state("ac");
    const charge = this.state("charge_status");
    const drive = this.state("status");

    const w = (v) => Math.max(0, Math.min(100, v || 0));

    // pct=null 表示该实体不是百分比（例如油量若按升上报）→ 只显示带单位的数值，不画误导性进度条
    const meter = (label, field, rangeField, color, pct) => `
      <section class="meter ${color}">
        <div class="meter-top"><span>${label}</span><strong>${this.num(field) === null ? "—"
          : pct === null ? `${this.fmt(field, 1)}<small> ${this._unit(field) || ""}</small>`
          : `${this.fmt(field)}<small> %</small>`}</strong></div>
        ${pct === null ? "" : `<div class="track" role="meter" aria-label="${label}" aria-valuemin="0" aria-valuemax="100"
             aria-valuenow="${pct}"><i style="width:${w(pct)}%"></i></div>`}
        <div class="range"><span>${color === "electric" ? "纯电续航" : "燃油续航"}</span>
          <b>${this.fmt(rangeField)} <small>km</small></b></div>
      </section>`;

    const tire = (field, label) => {
      const p = this._pressure(field);          // ★ kPa → bar（之前直接显示 kPa 数值当 bar）
      const bad = p.v !== null && p.v > 0 && (p.v < 2.0 || p.v > 2.9);   // 与健康页同阈值
      // 低压时多给一位小数，避免"显示 2.0 却标黄"的困惑（如 1.977 bar）
      const txt = p.v === null ? "—" : (bad && p.v < 2.0 ? p.v.toFixed(2) : p.v.toFixed(1));
      return `<div class="tire${bad ? " low" : ""}"><span>${label}</span>
        <b>${txt}</b><small>${p.unit}</small></div>`;
    };
    const stat = (label, value) =>
      `<div class="detail-stat"><span>${label}</span><b>${value}</b></div>`;
    const avail = (field, unit, d = 1) =>
      this.num(field) === null ? "暂未提供" : `${this.fmt(field, d)} ${unit}`;

    const updated = this._lastUpdated();
    const stale = !updated || (Date.now() - updated > 300000);
    const model = this._model();
    const series = this._config.series || model.series || "";
    const titleMain = "理想";
    const acText = acState === undefined ? "未知"
      : (acState === "off" ? "已关闭" : acState === "on" || acState === "auto" ? "运行中" : String(acState));
    const sentryText = sentry === "on" ? "哨兵开启" : sentry === "off" ? "哨兵关闭" : "哨兵未知";
    const chargeText = charge === undefined ? "充电状态未知" : String(charge);

    this._body.innerHTML = `
      <div class="main">
        <section class="identity">
          <div class="eyebrow">LI AUTO · 车辆总览</div>
          <div class="title">${titleMain}${series ? ` <b>${this.esc(series)}</b>` : ""}</div>
          <div class="subtitle">${this.esc(model.name || "数据来自理想汽车官方接口")}</div>
          <div class="badges">
            <span class="badge ${onlineOn ? "online" : onlineOff ? "offline" : ""}"><i class="dot"></i>${onlineOn ? "车辆在线" : onlineOff ? "车辆离线" : "在线状态未知"}</span>
            <span class="badge">${this.esc(drive || "状态未知")}</span>
            <span class="badge">${sentryText}</span>
          </div>
          <div class="art"><img alt="爱车车型示意图" src="${this.esc(this._config.image || "")}"></div>
          <div class="art-note">车型示意 · 以实车为准</div>
        </section>

        <section class="energy">
          <div class="range-main"><span>总续航</span>
            <b>${this.fmt("range_total")} <small>km</small></b></div>
          ${meter("电池电量", "battery", "range_elec", "electric", this._pct("battery"))}
          ${meter("油量", "fuel", "range_fuel", "fuel", this._pct("fuel"))}
          <div class="charge"><span>${this.esc(chargeText)}</span>
            <b>${this.num("charge_power") === null ? "—" : this.fmt("charge_power", 1) + " kW"}</b></div>
        </section>

        <section class="condition">
          <div class="section-label"><span>四轮胎压</span><small>车头 ↑</small></div>
          <div class="tire-grid">
            ${tire("tire_lf", "左前")}
            ${LixiangOverviewCard.TOP_CAR_SVG}
            ${tire("tire_rf", "右前")}
            ${tire("tire_lr", "左后")}
            ${tire("tire_rr", "右后")}
          </div>
          <div class="cabin">
            ${stat("车内温度", this.num("room_temp") === null ? "—" : this.fmt("room_temp", 1) + " °C")}
            ${stat("空调状态", acText)}
          </div>
        </section>
      </div>

      <div class="footer">
        <span class="${stale ? "stale" : "fresh"}"><i class="dot"></i>数据更新 ${this._fmtTime(updated)}${stale ? " · 数据较旧" : ""}</span>
        <span>总里程 ${this.fmt("total_km", 1)} km</span>
      </div>

      <details class="details" ${open ? "open" : ""}>
        <summary>更多车辆数据</summary>
        <div class="detail-grid">
          ${stat("WLTC 总续航", avail("wltc_total", "km", 0))}
          ${stat("充电电压", avail("charge_voltage", "V", 0))}
          ${stat("充电电流", avail("charge_current", "A", 1))}
          ${stat("剩余充电时间", this.num("charge_remain") === null ? "—" : this.fmt("charge_remain", 0) + " 分钟")}
          ${stat("空调设定温度", this.num("target_temp") === null ? "—" : this.fmt("target_temp", 0) + " °C")}
          ${stat("电池包电压", avail("pack_voltage", "V", 0))}
          ${stat("本月里程", avail("month_km", "km", 1))}
          ${stat("累计充电量", avail("total_kwh", "kWh", 1))}
        </div>
        <div class="note">
          续航分别取自车辆上报的「总续航 / 纯电续航 / 燃油续航」，不混用或自行相加。
          胎压低于 2.0 bar 会标黄提示。数据较旧时请以车机及官方 App 为准。<br>
          实体由本集成的「自动发现」匹配（按实体中文名），个别字段可用卡片配置里的
          <code>entities:</code> 手动指定。
        </div>
      </details>`;
    if (!this._artDone) { this._artDone = true; this._loadArt(); }
  }

  /* 车图：config.image > 侧视 > 横版 > 竖版（后端 /lixiang_auto/car-image.json） */
  async _loadArt() {
    if (this._config.image) return;             // 用户显式指定 → 不覆盖
    if (this._artLoading) return;
    this._artLoading = true;
    let data = null;
    try {
      const r = await fetch("/lixiang_auto/car-image.json", { cache: "no-store" });
      if (r.ok) data = await r.json();
    } catch (e) { /* 保持空图，不显示破图 */ }
    this._artLoading = false;
    if (!data || !data.ok) return;
    const d = data.side || data.horizontal || data.vertical || null;
    const src = d && d.static ? d.static : "";
    if (!src) return;
    const img = this._body && this._body.querySelector(".art img");
    if (img) { img.src = src; img.alt = "爱车车型示意图" + (data.color_code ? " · " + data.color_code : ""); }
  }

  static getConfigElement() { return null; }
  static getStubConfig() { return {}; }
}

/* 车辆俯视示意（车头向上）——胎压网格中间那辆车 */
LixiangOverviewCard.TOP_CAR_SVG = `
  <svg class="top-car" viewBox="0 0 80 160" role="img" aria-label="车辆俯视示意，车头向上">
    <defs>
      <linearGradient id="lxbody" x2="1" y2="1">
        <stop stop-color="#9fb0c6"/><stop offset=".5" stop-color="#4f6076"/><stop offset="1" stop-color="#94a3b8"/>
      </linearGradient>
    </defs>
    <rect x="3" y="27" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <rect x="68" y="27" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <rect x="3" y="110" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <rect x="68" y="110" width="9" height="27" rx="3.5" fill="#18202e" stroke="#8494aa"/>
    <path d="M13 23 Q14 5 40 5 Q66 5 67 23 L67 137 Q65 154 40 155 Q15 154 13 137Z"
          fill="url(#lxbody)" stroke="#c3cddb" stroke-width="1"/>
    <path d="M20 47 Q40 37 60 47 L57 68 L23 68Z" fill="#182a3c" stroke="#91a5bc"/>
    <path d="M23 73 H57 L58 110 Q40 119 22 110Z" fill="#22344a" stroke="#8196ad"/>
    <path d="M22 117 Q40 126 58 117 L58 131 Q40 141 22 131Z" fill="#1b2a3d"/>
    <path d="M21 15L33 12M47 12L59 15" stroke="#dde8ef" stroke-width="3" stroke-linecap="round"/>
    <path d="M24 145Q40 149 56 145" stroke="#4C9AFF" stroke-width="2" fill="none"/>
  </svg>`;

// 无 DOM 环境（Node 单测）下安全：只在浏览器注册自定义元素
if (typeof customElements !== "undefined" && !customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, LixiangOverviewCard);
}
if (typeof window !== "undefined") {
  window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
if (!window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
    type: CARD_TAG,
    name: "理想汽车 · 车辆总览",
    description: "电量 / 续航 / 胎压 / 车况的只读总览卡（深色玻璃风格，实体自动发现，零配置）",
    preview: true,
  });
}

export { LixiangOverviewCard, CARD_TAG };
