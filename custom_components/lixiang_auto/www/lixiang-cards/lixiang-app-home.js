/**
 * lixiang-app-home v3 —— 车控首页（严格对齐 App 截图 1260×2844 @3x = 420×948pt）
 *
 * 依据：实测截图 + 真实接口数据
 *   · 顶部：理想L6 | 162km 89% · 800km | 已驻车
 *   · 3D 车模：双态（展开大图 / 收起右上角缩略图）
 *   · 圆按钮 8 个（两排 ×4）：车锁/车窗/尾门/授权驾驶
 *                              直线召唤/寻车/充电口盖/后视镜加热
 *   · 收起箭头
 *   · 卡片行1：空调卡 | 位置卡
 *   · 卡片行2：本月陪伴里程+折线图 | 剩余电量 / 哨兵模式
 *   · 入口：车辆健康 | 任务大师 / 钥匙管理 | 情景模式 / 车辆设置
 *   · 服务专家大卡 + 理想AD学习平台
 *   · 图标用 _lisa 粗线版
 */

const CARD_TAG = "lixiang-app-home";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }

  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:14px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif;
    -webkit-tap-highlight-color:transparent; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  .head { padding:8px 20px 0; }
  .hrow { display:flex; align-items:flex-start; gap:10px; }
  .hleft { flex:1; min-width:0; }
  .title { font-size:25px; font-weight:600; letter-spacing:.2px; line-height:1.15; }
  .ranges { display:flex; align-items:baseline; gap:14px; margin-top:8px; flex-wrap:wrap; }
  .rg { display:flex; align-items:baseline; gap:4px; }
  .rg img { width:17px; height:17px; transform:translateY(2px); }
  .rg .v { font-family:"LxNum",sans-serif; font-size:17px; font-weight:600; }
  .rg .v.na { color:var(--lx-t3); font-size:15px; }
  .rg .u { font-size:12px; color:var(--lx-t3); }
  .parked { font-size:14px; color:var(--lx-t3); margin-top:5px; }
  .mini { width:150px; height:96px; flex:0 0 auto; border-radius:12px;
          overflow:hidden; display:none; align-items:center; justify-content:center;
          cursor:pointer; transition:transform .15s; }
  .mini:hover { transform:scale(1.03); }
  .mini iframe { width:100%; height:100%; border:0; }
  .mini img { width:100%; height:100%; object-fit:contain; }
  .root.collapsed3d .mini { display:flex; }

  .big3d { margin:8px 20px 0; border-radius:18px; overflow:hidden;
           background:linear-gradient(175deg,#FBFBFD 0%,#F1F1F5 100%);
           height:0; opacity:0; transition:height .3s cubic-bezier(.25,.8,.25,1), opacity .2s; }
  /* 展开态：由 .root 上的 .expanded3d 类控制（不用 :not() 避免优先级陷阱）*/
  .root.expanded3d .big3d { height:210px; opacity:1; }
  .root.expanded3d { --lx-3d-h: 200px; }
  .big3d iframe { width:100%; height:100%; border:0; display:block; }
  .big3d, .big3d iframe { touch-action:none; }
  .big3d img { width:100%; height:100%; object-fit:contain; }

  .quick { display:grid; grid-template-columns:repeat(4,1fr); gap:6px;
           padding:18px 12px 0; }
  .q { display:flex; flex-direction:column; align-items:center; gap:8px;
       min-height:52px; padding:6px 0 4px; border-radius:16px; cursor:pointer;
       position:relative; transition:background .15s; }
  .q:hover { background:var(--lx-card); }
  .q:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .q .c { width:56px; height:56px; border-radius:50%; background:var(--lx-bg);
          border:1.5px solid var(--lx-line); display:flex; align-items:center;
          justify-content:center; transition:transform .13s, border-color .18s, box-shadow .18s; }
  .q:hover .c { border-color:#D8D8DC; box-shadow:0 2px 10px rgba(0,0,0,.06); }
  .q:active .c { transform:scale(.9); }
  .q .c img { width:28px; height:28px; pointer-events:none; }
  .q .n { font-size:12px; color:var(--lx-t2); line-height:1.1; }
  .q.on .c { border-color:var(--lx-blue); background:rgba(10,88,246,.06); }
  .q.on .n { color:var(--lx-blue); font-weight:500; }
  .q.busy .c { border-color:var(--lx-blue); }
  .q .sp { position:absolute; top:16px; width:26px; height:26px; border-radius:50%;
           border:2.5px solid rgba(10,88,246,.2); border-top-color:var(--lx-blue);
           animation:spin .7s linear infinite; display:none; }
  .q.busy .sp { display:block; }
  .q.busy .c img { opacity:.25; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .q.dim { opacity:.35; cursor:not-allowed; }
  .q.dim:hover { background:transparent; }
  .q .sub { position:absolute; bottom:-2px; font-size:9px; color:var(--lx-blue);
            opacity:0; transition:opacity .2s; white-space:nowrap; }
  .q.done .sub { opacity:1; }

  .chev { display:flex; justify-content:center; padding:10px 0 2px; cursor:pointer; }
  .chev img { width:22px; height:22px; opacity:.55; transition:transform .25s; }
  .root.collapsed3d .chev img { transform:rotate(180deg); }

  .wrap { padding:12px 20px 0; display:grid; gap:12px; }
  .row2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .card { background:var(--lx-card); border-radius:18px; padding:16px;
          cursor:pointer; transition:transform .13s, box-shadow .18s; position:relative; }
  .card:hover { box-shadow:0 3px 14px rgba(0,0,0,.07); }
  .card:active { transform:scale(.985); }
  .card:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .card .lbl { font-size:13px; color:var(--lx-t3); }
  .ac { min-height:150px; display:flex; flex-direction:column;
        justify-content:space-between; }
  .ac .temp { font-family:"LxNum"; font-size:30px; font-weight:600; line-height:1.1; }
  .ac .temp sup { font-size:15px; font-weight:500; }
  .ac .target { font-size:11.5px; color:var(--lx-t3); margin-top:3px; }
  /* 风扇：右上角标（不占布局空间）*/
  .ac .fan { position:absolute; right:14px; top:14px; width:34px; height:34px;
             border-radius:50%; background:var(--lx-bg); display:flex;
             align-items:center; justify-content:center;
             box-shadow:0 1px 4px rgba(0,0,0,.06); }
  .ac .fan img { width:18px; height:18px; }
  .ac .fan.spin img { animation:spin 1.6s linear infinite; }
  /* 功能 chip：单行等分，不换行 */
  .ac .acrow { display:flex; gap:5px; margin-top:10px; }
  .ac .chip { flex:1; display:inline-flex; align-items:center; justify-content:center;
              gap:3px; font-size:10.5px; padding:5px 2px; border-radius:8px;
              background:var(--lx-bg); color:var(--lx-t3);
              border:1px solid var(--lx-line); transition:.2s; white-space:nowrap; }
  .ac .chip img { width:12px; height:12px; opacity:.7; flex:0 0 auto; }
  .ac .chip.on { background:rgba(10,88,246,.08); border-color:var(--lx-blue);
                 color:var(--lx-blue); }
  .ac .chip.on img { opacity:1; }
  .loc { min-height:150px; display:flex; flex-direction:column; overflow:hidden; }
  .loc .map { flex:1; border-radius:12px; background:#E8EEF4; overflow:hidden;
              position:relative; min-height:82px; }
  .loc .map iframe { width:100%; height:100%; border:0; }
  /* ── 自建地图（高德瓦片，免 key/免登录）── */
  .loc .map .tiles { position:absolute; inset:0; overflow:hidden; cursor:pointer; }
  .loc .map .tiles img { position:absolute; width:256px; height:256px;
                         user-select:none; pointer-events:none; }
  /* 车标：小车图形（对齐 App），小尺寸表达"车辆位置" */
  .loc .map .puck { position:absolute; width:18px; height:18px; margin:-9px 0 0 -9px;
                    display:flex; align-items:center; justify-content:center;
                    pointer-events:none; z-index:3; }
  .loc .map .puck img { width:18px; height:18px;
                        filter:drop-shadow(0 1px 3px rgba(0,0,0,.4)); }
  .loc .map .ph { position:absolute; inset:0; display:flex; flex-direction:column;
                  align-items:center; justify-content:center; text-align:center;
                  font-size:11px; color:var(--lx-t3); line-height:1.5; padding:0 12px; }
  .loc .addr { display:flex; align-items:flex-start; gap:6px; margin-top:10px; }
  .loc .addr img { width:15px; height:15px; flex:0 0 auto; margin-top:2px; }
  .loc .addr span { font-size:12.5px; color:var(--lx-t2); line-height:1.4;
                    display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
                    overflow:hidden; }
  .mile { min-height:150px; }
  .mile .big { font-family:"LxNum","Licium"; font-size:30px; font-weight:600; line-height:1.1; }
  .mile .big small { font-size:14px; font-weight:500; color:var(--lx-t2); margin-left:3px; }
  .mile .cap { font-size:13px; color:var(--lx-t3); margin-top:4px; }
  .mile .chart { margin-top:10px; height:46px; position:relative; }
  .mile .chart::after { content:""; position:absolute; left:0; right:0; bottom:0;
                        height:1px; background:var(--lx-line); }
  .mile .chart svg { width:100%; height:100%; display:block; }
  .mile .axis { display:flex; justify-content:space-between; font-size:10px;
                color:var(--lx-t3); margin-top:3px; }
  .batt .row { display:flex; align-items:center; gap:9px; }
  .batt .row img { width:26px; height:26px; }
  .batt .big { font-family:"LxNum","Licium"; font-size:28px; font-weight:600; line-height:1.05; }
  .batt .big small { font-size:15px; font-weight:500; color:var(--lx-t2); }
  .sentry { display:flex; align-items:center; gap:12px; min-height:76px; }
  .sentry img { width:26px; height:26px; }
  .sentry .t { font-size:15px; }
  .sentry .s { font-size:12px; color:var(--lx-t3); margin-top:3px; }
  .sentry.on .t { color:var(--lx-blue); }

  .entries { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .entry { background:var(--lx-card); border-radius:18px; padding:16px;
           display:flex; align-items:center; gap:12px; cursor:pointer;
           min-height:64px; transition:transform .13s, box-shadow .18s; }
  .entry:hover { box-shadow:0 3px 14px rgba(0,0,0,.07); }
  .entry:active { transform:scale(.985); }
  .entry:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .entry img.ic { width:24px; height:24px; flex:0 0 auto; }
  .entry .tx { min-width:0; }
  .entry .nm { font-size:15px; line-height:1.2; }
  .entry .sd { font-size:12px; color:var(--lx-t3); margin-top:3px; }

  .big { background:var(--lx-card); border-radius:18px; padding:18px 16px; }
  .srvrow { display:flex; align-items:center; gap:12px; }
  .srvrow > img.ic { width:26px; height:26px; }
  .srvrow .tx { flex:1; min-width:0; }
  .srvrow .nm { font-size:15px; }
  .srvrow .sd { font-size:12px; color:var(--lx-t3); margin-top:3px; }
  .cbtn { width:40px; height:40px; border-radius:50%; background:var(--lx-bg);
          display:flex; align-items:center; justify-content:center; cursor:pointer;
          box-shadow:0 1px 4px rgba(0,0,0,.06); transition:transform .13s; }
  .cbtn:active { transform:scale(.92); }
  .cbtn img { width:19px; height:19px; }
  .divider { height:1px; background:var(--lx-line); margin:16px 0; }
  .adrow { display:flex; align-items:center; gap:12px; cursor:pointer; }
  .adrow .ar { margin-left:auto; color:var(--lx-t3); font-size:18px; }

  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           white-space:nowrap; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.err { background:rgba(200,40,40,.92); }
  .toast.ok { background:rgba(28,150,70,.92); }

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

  /* ── 低电量告警 ── */
  .lowbat { margin:8px 20px 0; padding:11px 14px; border-radius:12px;
            display:flex; align-items:center; gap:9px; font-size:12.5px;
            background:rgba(255,149,0,.1); color:#B36B00; line-height:1.45; }
  .lowbat.crit { background:rgba(255,59,48,.1); color:#C0271D; }
  .lowbat img { width:17px; height:17px; flex:0 0 auto; }
  .lowbat b { font-family:"LxNum"; font-size:14px; }
  /* 电量数字着色 */
  .rg .v.low { color:#FF9500; }
  .rg .v.crit { color:#FF3B30; }
  /* 3D 加载中/失败占位 */
  .big3d .ph { position:absolute; inset:0; display:flex; flex-direction:column;
               align-items:center; justify-content:center; gap:8px;
               font-size:12px; color:var(--lx-t3); }
  .big3d { position:relative; }
  .big3d .ph .spin2 { width:22px; height:22px; border-radius:50%;
               border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
               animation:spin .8s linear infinite; }
`;

const QUICK = [
  { key:"lock",   name:"车锁",       off:"ic_home_lock_off_lisa.png",           on:"ic_home_lock_open_lisa.png" },
  { key:"window", name:"车窗",       off:"ic_home_window_off_lisa.png",         on:"ic_home_window_on_lisa.png" },
  { key:"trunk",  name:"尾门",       off:"ic_home_tail_w_off_2025.png",         on:"ic_home_tail_w_on_2025.png" },
  { key:"auth",   name:"授权驾驶",   off:"ic_home_authorization_off_lisa.png",  on:"ic_home_authorization_on_lisa.png" },
  { key:"summon", name:"直线召唤", note:"需车辆支持",   off:"ic_home_parkingout_off_lisa.png",     on:"ic_home_parkingout_on_lisa.png" },
  { key:"find",   name:"寻车",       off:"ic_summon_lisa.png",                  on:"ic_summon_lisa.png" },
  { key:"port",   name:"充电口盖",   off:"ic_home_chrgporlid_off_lisa.png",     on:"ic_home_chrgporlid_on_lisa.png" },
  { key:"mirror", name:"后视镜加热", off:"ic_home_rearmirroheat_off_lisa.png",  on:"ic_home_rearmirroheat_on_lisa.png" },
];

const FALLBACK = {
  "ic_home_tail_w_off_2025.png":"ic_home_tail_off_2025.png",
  "ic_home_tail_w_on_2025.png":"ic_home_tail_on_2025.png",
};

class LixiangAppHome extends HTMLElement {

  /** 让元素键盘可达（无障碍）：role/tabindex/aria-label + Enter/Space */
  _a11y(el, label, handler) {
    if (!el || !handler) return;
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    if (label) el.setAttribute("aria-label", label);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault(); e.stopPropagation(); handler(e);
      }
    });
  }

  /**
   * 自动绑定实体（用户不用手填 90 个 ID）。
   *   配置：vin（可选）—— 留空则认领第一辆理想车
   *   手填字段仍然优先（向后兼容）
   */
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

  /** 嵌套组（quick / switches / numbers …）也支持自动发现 */
  _eidIn(group, key) {
    const c = this._config || {};
    const m = (c[group] || {})[key];
    if (typeof m === "string" && m.includes(".")) return m;
    if (m && typeof m === "object" && m.entity) return m.entity;
    return (this._autoBind() || {})[key] || null;
  }

  /**
   * 车型识别（读 HA 设备注册表，避免硬编码）。
   * 返回 {name, model, series}
   */
  _detectModel() {
    if (this._modelCache !== undefined) return this._modelCache;
    const c = this._config || {};
    if (c.model_name) {
      this._modelCache = { name: c.model_name, model: c.model_name,
                           series: this._seriesOf(c.model_name) };
      return this._modelCache;
    }
    const h = this._hass;
    let out = null;
    if (h && h.devices) {
      const vin = c.vin || "";
      for (const d of Object.values(h.devices)) {
        const isLi = (d.manufacturer || "").includes("理想")
          || JSON.stringify(d.identifiers || []).includes("lixiang");
        if (!isLi) continue;
        if (vin && !JSON.stringify(d.identifiers || []).includes(vin)) continue;
        const mdl = d.model || d.name || "";
        out = { name: d.name || mdl, model: mdl, series: this._seriesOf(mdl) };
        break;
      }
    }
    this._modelCache = out;
    return out;
  }

  /** 车系代号（L6/L7/L8/L9/MEGA/i8） */
  _seriesOf(text) {
    const m = String(text || "").match(/(MEGA|L[6-9]|i[6-9]|ONE)/i);
    return m ? m[1].toUpperCase() : "";
  }

  /** 车型能力（优先实体属性「车型能力」，其次按车系兜底） */
  _modelCaps() {
    if (this._capsCache) return this._capsCache;
    const h = this._hass;
    let caps = null;
    if (h) {
      const probe = this._eid("battery") || this._eid("month_km");
      if (probe && h.states[probe] && h.states[probe].attributes["车型能力"]) {
        caps = h.states[probe].attributes["车型能力"];
      }
      if (!caps) {
        for (const id of Object.keys(h.states)) {
          if (id.indexOf("li_auto") < 0 && id.indexOf("li_xiang") < 0) continue;
          const a = h.states[id].attributes || {};
          if (a["车型能力"]) { caps = a["车型能力"]; break; }
        }
      }
    }
    if (caps && Object.keys(caps).length) { this._capsCache = caps; return caps; }
    // 兜底：按车系推断（保守，宁可多显示也不误隐藏）
    const series = (this._detectModel() || {}).series || "";
    const base = { 三排座椅: false, 冰箱: false, 侧滑门: false, 空气悬架: false };
    const by = { L6: {}, L7: { 冰箱: true }, L8: { 三排座椅: true, 冰箱: true },
                 L9: { 三排座椅: true, 冰箱: true, 空气悬架: true },
                 MEGA: { 三排座椅: true, 冰箱: true, 侧滑门: true, 空气悬架: true } };
    this._capsCache = Object.assign({}, base, by[series] || {});
    return this._capsCache;
  }

  setConfig(config) {
    if (!config) throw new Error("配置不能为空");
    this._config = config;
    // 资源路径可覆盖（用户把图标/字体放别处时）
    if (config.icon_base) __iconBase = config.icon_base;
    if (config.font_base) __fontBase = config.font_base; this._busy = {}; this._optim = {}; this._built = false;
  }
  set hass(hass) { this._hass = hass; if (!this._built) this._build(); this._update(); }
  getCardSize() { return 22; }

  disconnectedCallback() {
    if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; }
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
  }

  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id); return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }
  _on(id) {
    const v = this._txt(id); if (v == null) return false;
    return ["on","open","opening","locked","已锁定","开启","已连接","true","1"].some(x => String(v).includes(x));
  }
  _online() {
    const s = this._st(this._config.online); if (!s) return true;
    return !["离线","off","unavailable","unknown"].some(v => String(s.state).includes(v));
  }
  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2400);
  }
  _img(name) { return `${__iconBase}/${FALLBACK[name] || name}`; }

  _build() {
    while (this.firstChild) this.removeChild(this.firstChild);
    const st = document.createElement("style"); st.textContent = STYLE; this.appendChild(st);
    const c = this._config;
    const root = document.createElement("div");
    root.className = "root" + (c.car_default_collapsed ? " collapsed3d" : " expanded3d");
    root.dataset.theme = c.theme || "light";
    root.innerHTML = `
      <div class="head" id="head">
        <div class="hrow">
          <div class="hleft">
            <div class="title" id="t">理想汽车</div>
            <div class="ranges">
              <span class="rg"><img src="${__iconBase}/ic_home_electricity.webp" alt="">
                <span class="v" id="v-range">—</span><span class="u">km</span>
                <span class="v" id="v-soc" style="margin-left:6px">—</span><span class="u">%</span></span>
              <span class="rg" id="rg-fuel"><img src="${__iconBase}/ic_home_oil.webp" alt="">
                <span class="v" id="v-fuel">—</span><span class="u">km</span></span>
            </div>
            <div class="parked" id="v-status">—</div>
          </div>
          <div class="mini" id="mini" role="button" tabindex="0" aria-label="展开车辆 3D"></div>
        </div>
      </div>
      <div class="lowbat" id="lowbat" style="display:none" role="alert" aria-live="polite">
        <img src="${__iconBase}/ic_home_battery.webp" alt="">
        <span id="lowbat-t"></span>
      </div>
      <div class="big3d" id="big3d">
        <div class="ph" id="b3ph"><div class="spin2"></div><div>车辆 3D 加载中…</div></div>
      </div>
      <div class="quick" id="quick" role="group" aria-label="快捷操作"></div>
      <div class="chev" id="chev" role="button" tabindex="0" aria-label="收起车辆视图">
        <img src="${__iconBase}/ic_home_pulldown.png" alt="">
      </div>
      <div class="wrap">
        <div class="row2">
          <div class="card ac" id="c-ac" role="button" tabindex="0">
            <div class="temp"><span id="v-room">—</span><sup>°C</sup></div>
            <div class="target">目标温度 <span id="v-target">—</span>°C</div>
            <div class="acrow" id="acrow">
              <span class="chip" id="ch-seat"><img src="${__iconBase}/ic_home_seat_heating3.webp" alt="" onerror="this.style.visibility='hidden'"><b>座椅</b></span>
              <span class="chip" id="ch-fan"><img src="${__iconBase}/ic_home_fan_on.webp" alt=""><b>吹风</b></span>
              <span class="chip" id="ch-defrost"><img src="${__iconBase}/ic_home_ice_cool.webp" alt=""><b>除霜</b></span>
            </div>
            <div class="fan" id="fan"><img src="${__iconBase}/ic_home_fan_on.webp" alt=""></div>
          </div>
          <div class="card loc" id="c-loc" role="button" tabindex="0">
            <div class="map" id="map">
              <div class="tiles" id="hm-tiles"></div>
              <div class="puck" id="hm-puck" style="display:none">
                <img src="${__iconBase}/icon_car_loc.webp" alt="车辆位置"></div>
            </div>
            <div class="addr"><img src="${__iconBase}/icon_vehicle_my_location.webp" alt="" onerror="this.style.display='none'">
              <span id="v-addr">定位获取中…</span></div>
          </div>
        </div>
        <div class="row2">
          <div class="card mile" id="c-mile" role="button" tabindex="0">
            <div class="big"><span id="v-mile">—</span><small>km</small></div>
            <div class="cap">本月陪伴里程</div>
            <div class="chart"><svg id="spark" viewBox="0 0 100 40" preserveAspectRatio="none">
              <polyline id="sparkline" fill="none" stroke="#8A8A8E" stroke-width="1.6"
                        stroke-linejoin="round" points=""></polyline></svg></div>
            <div class="axis"><span>01</span><span>08</span><span>15</span><span>22</span><span>29</span></div>
          </div>
          <div style="display:grid; gap:12px; grid-template-rows:1fr auto;">
            <div class="card batt" id="c-batt" role="button" tabindex="0">
              <div class="row"><img src="${__iconBase}/ic_home_battery.webp" alt="">
                <div><div class="big"><span id="v-batt">—</span><small>%</small></div>
                <div class="lbl" style="margin-top:2px">剩余电量</div></div></div>
            </div>
            <div class="card sentry" id="c-sentry" role="button" tabindex="0">
              <img src="${__iconBase}/ic_home_sentry.png" alt="" onerror="this.style.visibility='hidden'">
              <div><div class="t">哨兵模式</div><div class="s" id="v-sentry">—</div></div>
            </div>
          </div>
        </div>
        <div class="entries">
          <div class="entry" id="e-health" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_health.webp" alt="">
            <div class="tx"><div class="nm">车辆健康</div></div></div>
          <div class="entry" id="e-task" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_control_off_lisa.png" alt="" onerror="this.src='${__iconBase}/ic_home_control.webp'">
            <div class="tx"><div class="nm">任务大师</div></div></div>
          <div class="entry" id="e-key" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_bluetooth.webp" alt="">
            <div class="tx"><div class="nm">钥匙管理</div><div class="sd" id="v-key">未连接</div></div></div>
          <div class="entry" id="e-scene" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_scene_mode_lisa.png" alt="" onerror="this.src='${__iconBase}/ic_home_control.webp'">
            <div class="tx"><div class="nm">情景模式</div></div></div>
          <div class="entry" id="e-setting" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_control.webp" alt="">
            <div class="tx"><div class="nm">车辆设置</div></div></div>
        </div>
        <div class="big">
          <div class="srvrow">
            <img class="ic" src="${__iconBase}/icon_car_owner_consultant.png" alt="" onerror="this.style.visibility='hidden'">
            <div class="tx"><div class="nm">服务专家</div><div class="sd">7x24小时为您服务</div></div>
            <div class="cbtn" id="btn-chat" role="button" tabindex="0" aria-label="在线客服">
              <img src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'"></div>
            <div class="cbtn" id="btn-call" role="button" tabindex="0" aria-label="电话客服">
              <img src="${__iconBase}/ic_home_telephone.png" alt=""></div>
          </div>
          <div class="divider"></div>
          <div class="adrow" id="btn-ad" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_navigation.webp" alt="">
            <div class="tx"><div class="nm">理想AD学习平台</div>
              <div class="sd">辅助驾驶必修课</div></div>
            <span class="ar">›</span>
          </div>
        </div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const b3 = this.querySelector("#big3d"), mini = this.querySelector("#mini");
    // 3D URL：自动加 minimal=1（隐藏 3D 页里重复的按钮/HUD）
    let url3d = c.car_iframe || "";
    if (url3d && url3d.indexOf("minimal=") < 0) {
      url3d += (url3d.indexOf("?") < 0 ? "?" : "&") + "minimal=1";
    }
    const frame = (title, extra) =>
      `<iframe src="${url3d}" title="${title}" loading="lazy" ${extra}
         sandbox="allow-scripts allow-same-origin allow-pointer-lock"></iframe>`;
    const still = `<img src="${c.car_image || __iconBase + '/icon_car_loc.webp'}" alt="车辆">`;
    if (url3d) {
      const f3 = document.createElement("iframe");
      f3.src = url3d; f3.title = "车辆 3D"; f3.loading = "lazy";
      f3.setAttribute("sandbox","allow-scripts allow-same-origin allow-pointer-lock");
      f3.addEventListener("load", () => { const ph=this.querySelector("#b3ph"); if(ph) ph.remove(); });
      // 超时兜底：8 秒后若仍未加载完，显示提示可点刷新
      setTimeout(() => {
        const ph = this.querySelector("#b3ph");
        if (ph) ph.innerHTML = '<div style="text-align:center;line-height:1.5">3D 模型加载较慢<br><span style="font-size:11px;opacity:.7">（首次约需 10–30 秒）</span></div>';
      }, 8000);
      b3.appendChild(f3);
      mini.innerHTML = frame("车辆 3D 缩略图", 'scrolling="no"');
    } else {
      b3.innerHTML = still; mini.innerHTML = still;
    }

    const toggle = () => {
      this._userToggled = true;    // 用户手动操作后，停止自动跟随
      const collapsed = !root.classList.contains("collapsed3d");
      root.classList.toggle("collapsed3d", collapsed);
      root.classList.toggle("expanded3d", !collapsed);
      try { localStorage.setItem("lx_3d_collapsed", collapsed ? "1" : "0"); } catch (e) {}
    };
    [this.querySelector("#chev"), this.querySelector("#mini")].forEach(el => {
      if (!el) return;
      el.addEventListener("click", e => { e.stopPropagation(); toggle(); });
      el.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); toggle(); }
      });
    });

    // ★ 上拉自动收起 3D（对齐 App 交互）
    //   App 用滚动驱动：页面下滑 → 3D 收起；回到顶部 → 3D 展开
    //   HA 是文档级滚动，监听 window 的 scroll 即可
    if (c.car_scroll_collapse !== false) {
      const THRESHOLD = Number(c.car_scroll_threshold || 60);
      let lastY = 0, scheduled = false;
      const apply = () => {
        scheduled = false;
        const y = window.scrollY || document.documentElement.scrollTop || 0;
        if (Math.abs(y - lastY) < 4) return;
        lastY = y;
        const collapsed = root.classList.contains("collapsed3d");
        if (y > THRESHOLD && !collapsed && !this._userToggled) {
          root.classList.add("collapsed3d"); root.classList.remove("expanded3d");
          try { localStorage.setItem("lx_3d_collapsed", "1"); } catch (e) {}
        } else if (y <= 8 && collapsed && !this._userToggled) {
          root.classList.remove("collapsed3d"); root.classList.add("expanded3d");
          try { localStorage.setItem("lx_3d_collapsed", "0"); } catch (e) {}
        }
      };
      // 不用 rAF（无头/后台标签下可能被节流），直接同步执行 + 微任务合并
      const onScroll = () => apply();   // 直接执行（scroll 本身已节流）
      window.addEventListener("scroll", onScroll, { passive: true });
      document.addEventListener("scroll", onScroll, { passive: true, capture: true });
      this._cleanupScroll = () => {
        window.removeEventListener("scroll", onScroll);
        document.removeEventListener("scroll", onScroll, { capture: true });
      };

    }

    const q = this.querySelector("#quick");
    QUICK.forEach(it => {
      const d = document.createElement("div");
      d.className = "q"; d.dataset.key = it.key;
      d.setAttribute("role","button"); d.setAttribute("tabindex","0");
      d.setAttribute("aria-label", it.name);
      d.innerHTML = `<div class="c"><img src="${this._img(it.off)}" alt=""></div>
                     <div class="n">${it.name}</div><div class="sp"></div><div class="sub"></div>`;
      d.addEventListener("click", () => this._tap(it.key));
      d.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this._tap(it.key); }
      });
      q.appendChild(d);
    });

    const nav = c.nav || {};
    const go = p => { if (!p) return; history.pushState(null,"",p);
      this.dispatchEvent(new CustomEvent("location-changed",{bubbles:true,composed:true})); };
    const wire = (sel, path, moreKey) => {
      const el = this.querySelector(sel); if (!el) return;
      const act = () => path ? go(path) : this._more(moreKey);
      el.addEventListener("click", act);
      el.addEventListener("keydown", e => {
        if (e.key==="Enter"||e.key===" ") { e.preventDefault(); act(); }
      });
    };
    wire("#c-mile", nav.energy || "/lixiang/energy");
    // ★ 新页面入口（2026-10-02 补齐）
    wire("#c-ac", nav.climate || "/lixiang/climate");
    wire("#c-loc", nav.location || "/lixiang/location");
    wire("#c-batt", nav.charge || "/lixiang/charge");
    wire("#t", nav.vinfo || "/lixiang/vinfo");
    wire("#e-key", nav.vinfo || "/lixiang/vinfo");
    wire("#e-task", nav.task || "/lixiang/task");
    wire("#e-scene", nav.scene || "/lixiang/scene");
    wire("#e-health", nav.health);
    wire("#e-setting", nav.setting);
    // 哨兵卡：点击直接切换（可控制），键盘同样支持
    const senEl = this.querySelector("#c-sentry");
    if (senEl) {
      const act = async () => {
        const eid = this._eid("sentry");
        if (!eid) { this._toast("哨兵模式未接入", "err"); return; }
        if (!this._online()) { this._toast("车辆离线，操作不可用", "err"); return; }
        const on = this._on(eid);
        try {
          await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: eid });
          this._toast(on ? "哨兵模式已关闭" : "哨兵模式已开启", "ok");
        } catch (e) { this._toast("切换失败：" + ((e && e.message) || "未知"), "err"); }
      };
      this._a11y(senEl, "切换哨兵模式", act);
      senEl.addEventListener("click", act);
    }
    wire("#btn-chat", nav.service); wire("#btn-ad", nav.ad);

    this._built = true;
  }

  _more(key) {
    const eid = (this._config.more || {})[key];
    if (eid) {
      this.dispatchEvent(new CustomEvent("hass-more-info",
        { bubbles:true, composed:true, detail:{ entityId: eid } }));
    } else this._toast("该功能尚未接入");
  }

  async _tap(key) {
    if (this._busy[key]) return;
    const c = this._config;
    const eid = this._eidIn("quick", key);
    const el = this.querySelector(`.q[data-key="${key}"]`);
    const def = QUICK.find(x => x.key === key);
    if (!eid) { this._toast(`${def.name} 尚未接入`, "err"); return; }
    if (!this._online()) { this._toast("车辆离线，操作不可用", "err"); return; }
    const s = this._hass.states[eid];
    if (!s) { this._toast("实体不存在", "err"); return; }

    this._busy[key] = true; el.classList.add("busy");
    const dom = eid.split(".")[0];
    try {
      if (key === "find") {
        await this._hass.callService("button","press",{entity_id:eid});
      } else if (dom === "lock") {
        const unlocked = ["unlocked","已解锁","开锁"].some(v => String(s.state).includes(v));
        await this._hass.callService("lock", unlocked ? "lock" : "unlock", { entity_id: eid });
        this._optim[key] = !unlocked;
      } else if (dom === "cover" || dom === "switch") {
        const opened = ["open","opening","on","开启","已连接"].some(v => String(s.state).includes(v));
        await this._hass.callService(dom, opened ? "close" : "open", { entity_id: eid });
        this._optim[key] = !opened;
      } else if (dom === "select") {
        const opts = (s.attributes && s.attributes.options) || [];
        const cur = opts.indexOf(s.state);
        const next = opts[(cur + 1) % opts.length];
        await this._hass.callService("select","select_option",{entity_id:eid, option:next});
        this._toast(`${def.name} → ${next}`, "ok");
      } else if (dom === "button") {
        await this._hass.callService("button","press",{entity_id:eid});
      } else if (dom === "binary_sensor") {
        // 只读实体：不能控制，明确告知
        this._toast(`${def.name} 为只读状态，无法远程控制`, "err");
        return;
      } else {
        await this._hass.callService("homeassistant","toggle",{entity_id:eid});
      }
      const sub = el.querySelector(".sub");
      if (sub) sub.textContent = "✓ 已执行";
      el.classList.add("done");
      setTimeout(() => el.classList.remove("done"), 2400);
      this._toast(`${def.name} 已执行`, "ok");
      this._applyQuick();
      setTimeout(() => { delete this._optim[key]; this._applyQuick(); }, 3500);
    } catch (err) {
      this._toast(`${def.name} 失败：${(err && err.message) || "未知"}`, "err");
    } finally {
      delete this._busy[key]; el.classList.remove("busy");
    }
  }

  _applyQuick() {
    const c = this._config, offline = !this._online();
    QUICK.forEach(it => {
      const el = this.querySelector(`.q[data-key="${it.key}"]`);
      if (!el) return;
      const eid = this._eidIn("quick", it.key);
      let active = false; const missing = !eid || !this._st(eid);
      if (eid && this._st(eid)) {
        if (it.key in this._optim) active = this._optim[it.key];
        else if (it.key === "lock") {
          const v = String((this._st(eid) || {}).state || "");
          active = ["unlocked","已解锁"].some(x => v.includes(x));
        } else active = this._on(eid);
      }
      el.className = "q" + (active ? " on" : "") + ((missing || offline) ? " dim" : "")
                   + (this._busy[it.key] ? " busy" : "");
      el.setAttribute("aria-pressed", active ? "true" : "false");
      const img = el.querySelector("img");
      if (img) img.src = this._img(active ? it.on : it.off);
    });
  }

  _spark() {
    const el = this.querySelector("#sparkline"); if (!el) return;
    // 优先用服务拉取的日明细（属性常因 recorder 未落库而为空）
    let cached = this._dailyCache;
    const s = this._st(this._config.mile_chart || this._config.month_km);
    let vals = null;
    if (Array.isArray(cached) && cached.length) {
      vals = cached.map(r => Number(r.mileage) || 0);
    }
    if (!vals && s && s.attributes) {
      for (const k of ["month_daily","daily_list"]) {
        const raw = s.attributes[k];
        if (Array.isArray(raw) && raw.length) { vals = raw.map(r => Number(r.mileage) || 0); break; }
      }
    }
    if (!vals || !vals.length) { el.setAttribute("points",""); return; }
    const max = Math.max.apply(null, vals.concat([1]));
    const n = vals.length;
    el.setAttribute("points", vals.map((v, i) => {
      const x = (i / Math.max(n - 1, 1)) * 100;
      const y = 40 - (v / max) * 36 - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" "));
  }

  _update() {
    if (!this._built) return;
    const c = this._config, q = s => this.querySelector(s);

        // 标题：手填 > 自动识别的车型 > 兜底
    const _mdl = this._detectModel();
    const _title = this._config.title
      || (_mdl && (_mdl.series ? `理想${_mdl.series}` : (_mdl.model || _mdl.name)))
      || "理想汽车";
    q("#t").textContent = _title;
    if (_mdl) q("#t").setAttribute("title", `${_title}（自动识别）`);
    const rg = this._num(this._eid("range_elec")), soc = this._num(this._eid("battery")), fu = this._num(this._eid("range_fuel"));
    const vR = q("#v-range"), vS = q("#v-soc");
    vR.textContent = rg == null ? "—" : Math.round(rg);
    vR.className = "v" + (rg == null ? " na" : "");
    vS.textContent = soc == null ? "—" : soc;
    vS.className = "v" + (soc == null ? " na" : "");
    const rgf = q("#rg-fuel");
    if (this._eid("range_fuel") && this._st(this._eid("range_fuel"))) {
      rgf.style.display = "";
      q("#v-fuel").textContent = fu == null ? "—" : Math.round(fu);
    } else rgf.style.display = "none";

    q("#v-status").textContent = this._txt(this._eid("status")) || "—";

    // ★ 低电量告警（续航/电量异常时醒目提示）
    const lb = q("#lowbat");
    if (lb) {
      const socLow = soc != null && soc <= 20;
      const rngLow = rg != null && rg <= 50;
      if (socLow || rngLow) {
        lb.style.display = "";
        lb.className = "lowbat" + (soc != null && soc <= 10 ? " crit" : "");
        const parts = [];
        if (soc != null && soc <= 20) parts.push(`电量仅 <b>${soc}%</b>`);
        if (rg != null && rg <= 50) parts.push(`剩余续航 <b>${Math.round(rg)}km</b>`);
        q("#lowbat-t").innerHTML = parts.join("，") + "，建议尽快充电";
      } else lb.style.display = "none";
    }
    // 电量数字着色
    const socEl = q("#v-soc");
    if (socEl && soc != null) {
      socEl.className = "v" + (soc <= 10 ? " crit" : (soc <= 20 ? " low" : ""));
    }
    const rgEl = q("#v-range");
    if (rgEl && rg != null) {
      rgEl.className = "v" + (rg <= 30 ? " crit" : (rg <= 50 ? " low" : (rg == null ? " na" : "")));
    }

    const room = this._num(this._eid("room_temp")), tgt = this._num(this._eid("target_temp"));
    q("#v-room").textContent = room == null ? "—" : room.toFixed(1);
    q("#v-target").textContent = tgt == null ? "—" : tgt;
    const acOn = this._eid("ac") ? this._on(this._eid("ac")) : false;
    const fan = q("#fan"); if (fan) fan.className = "fan" + (acOn ? " spin" : "");
    // 功能状态 chip（有实体且开启时点亮；无实体则隐藏）
    const _chip = (sel, eid) => {
      const el = q(sel); if (!el) return;
      if (!eid) { el.style.display = "none"; return; }
      el.style.display = "";
      el.className = "chip" + (this._on(eid) ? " on" : "");
    };
    _chip("#ch-seat", this._eid("steer_heat") || this._eid("ac_fast_hot"));
    _chip("#ch-fan", this._eid("ac_fast_cold"));
    _chip("#ch-defrost", this._eid("ac_defrost"));

    // 地址：device_tracker 的 attributes 里可能有 address / 也支持坐标回退
    let addr = null;
    const dt = this._st(this._eid("tracker"));
    if (dt && dt.attributes) {
      addr = dt.attributes.address || dt.attributes.friendly_name && dt.attributes.address;
      if (!addr && dt.attributes.latitude != null) {
        addr = `${Number(dt.attributes.latitude).toFixed(4)}, ${Number(dt.attributes.longitude).toFixed(4)}`;
      }
    }
    if (!addr) {
      const sv = this._txt(this._eid("address"));
      addr = (sv && !/^\d+$/.test(String(sv))) ? sv : "暂无定位";
    }
    q("#v-addr").textContent = addr;
    // ★ 2026-10-03：自建地图（高德瓦片，免 key/免登录）。
    //   原 iframe（uri.amap.com/marker）在 iframe 里会弹登录页。
    this._drawHomeMap(
      dt && dt.attributes ? dt.attributes.latitude : null,
      dt && dt.attributes ? dt.attributes.longitude : null);

    q("#v-mile").textContent = (mk => mk == null ? "—" : mk)(this._num(this._eid("month_km")));
    q("#v-batt").textContent = soc == null ? "—" : soc;

    const sen = this._eid("sentry") ? this._on(this._eid("sentry")) : false;
    const senEl = q("#c-sentry"); if (senEl) senEl.className = "card sentry" + (sen ? " on" : "");
    q("#v-sentry").textContent = this._eid("sentry") ? (sen ? "已激活" : "未激活") : "未接入";

    const keyOn = this._eid("key_connected") ? this._on(this._eid("key_connected")) : false;
    q("#v-key").textContent = this._eid("key_connected") ? (keyOn ? "已连接" : "未连接") : "未连接";

    this._applyQuick(); this._spark();
    this._fetchDaily();
  }

  /** 拉当月日明细（折线图用）—— 必须带 year/month，无参只返回年列表 */
  async _fetchDaily() {
    if (this._dailyCache || this._fetchingDaily || !this._hass) return;
    this._fetchingDaily = true;
    try {
      const now = new Date();
      const r = await this._hass.callService(
        "lixiang_auto", "get_travel",
        { year: now.getFullYear(), month: now.getMonth() + 1 },
        undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const dl = first && first.data && first.data.dailyList;
      if (Array.isArray(dl) && dl.length) {
        this._dailyCache = dl.map((x) => ({
          dayOfMonth: Number(x.dayOfMonth) || 0,
          mileage: Number(x.mileage) || 0,
        })).sort((a, b) => a.dayOfMonth - b.dayOfMonth);
        this._spark();
      }
    } catch (e) { /* 折线图非关键路径，静默 */ }
    finally { this._fetchingDaily = false; }
  }
  // ── 自建地图（高德瓦片）────────────────────────────────────────────
  /** WGS84 → GCJ-02（大陆偏移 300~600m）。 */
  _wgs2gcj(lat, lon) {
    const a = 6378245.0, ee = 0.00669342162296594323;
    if (lon < 72.004 || lon > 137.8347 || lat < 0.8293 || lat > 55.8271) return [lat, lon];
    const tfLat = (x, y) => {
      let r = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
      r += (20*Math.sin(y*Math.PI) + 40*Math.sin(y/3*Math.PI)) * 2/3;
      r += (160*Math.sin(y/12*Math.PI) + 320*Math.sin(y*Math.PI/30)) * 2/3;
      return r;
    };
    const tfLon = (x, y) => {
      let r = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
      r += (20*Math.sin(x*Math.PI) + 40*Math.sin(x/3*Math.PI)) * 2/3;
      r += (150*Math.sin(x/12*Math.PI) + 300*Math.sin(x/30*Math.PI)) * 2/3;
      return r;
    };
    const dLat0 = tfLat(lon - 105, lat - 35), dLon0 = tfLon(lon - 105, lat - 35);
    const radLat = lat / 180 * Math.PI;
    let magic = Math.sin(radLat); magic = 1 - ee*magic*magic;
    const sm = Math.sqrt(magic);
    const dLat = (dLat0 * 180) / ((a * (1 - ee)) / (magic * sm) * Math.PI);
    const dLon = (dLon0 * 180) / (a / sm * Math.cos(radLat) * Math.PI);
    return [lat + dLat, lon + dLon];
  }

  _llToTile(lat, lon, z) {
    const n = 2 ** z;
    return [(lon + 180) / 360 * n,
            (1 - Math.log(Math.tan(lat*Math.PI/180) + 1/Math.cos(lat*Math.PI/180)) / Math.PI) / 2 * n];
  }

  /** 首页迷你地图：车辆居中，铺满容器。 */
  _drawHomeMap(la, lo) {
    const box = this.querySelector("#hm-tiles");
    const wrap = this.querySelector("#map");
    const puck = this.querySelector("#hm-puck");
    if (!box || !wrap) return;
    // ★ 车标位置【每次都更新】—— 不能放在"位置没变就 return"之后，
    //   否则第二次渲染就直接 return，车标永远停在 display:none。
    if (la == null || lo == null) {
      if (puck) puck.style.display = "none";
      return;
    }
    const [glat, glon] = this._wgs2gcj(Number(la), Number(lo));
    const key = `${glat.toFixed(6)},${glon.toFixed(6)}`;
    const _W0 = wrap.clientWidth || 180, _H0 = wrap.clientHeight || 90;
    if (puck) {
      puck.style.display = "";
      puck.style.left = _W0 / 2 + "px";
      puck.style.top = _H0 / 2 + "px";
    }
    if (box.dataset.pt === key) return;          // 瓦片不重绘（仅更新车标）
    box.dataset.pt = key;
    const z = 15;                                 // 首页小图：看大致位置
    const W = wrap.clientWidth || 180, H = wrap.clientHeight || 90;
    const [cxE, cyE] = this._llToTile(glat, glon, z);
    const cxI = Math.floor(cxE), cyI = Math.floor(cyE);
    const offX = (cxE - cxI) * 256, offY = (cyE - cyI) * 256;
    const cpx = W / 2, cpy = H / 2;
    const x0 = cxI - Math.ceil((cpx - offX) / 256);
    const x1 = cxI + Math.ceil((W - cpx + offX) / 256);
    const y0 = cyI - Math.ceil((cpy - offY) / 256);
    const y1 = cyI + Math.ceil((H - cpy + offY) / 256);
    const n = 2 ** z;
    const frag = [];
    for (let tx = x0; tx <= x1; tx++) {
      for (let ty = y0; ty <= y1; ty++) {
        if (tx < 0 || ty < 0 || tx >= n || ty >= n) continue;
        const left = cpx - offX + (tx - cxI) * 256;
        const top = cpy - offY + (ty - cyI) * 256;
        const s2 = (tx + ty) % 4 + 1;
        frag.push(`<img src="https://webrd0${s2}.is.autonavi.com/appmaptile`
                + `?lang=zh_cn&size=1&scale=1&style=8&x=${tx}&y=${ty}&z=${z}"`
                + ` style="left:${Math.round(left)}px;top:${Math.round(top)}px" alt="">`);
      }
    }
    box.innerHTML = frag.join("");
  }

}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangAppHome);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "理想车控首页（v3 · 对齐 App）",
  description: "8 圆按钮 · 双态 3D · 空调/位置/里程/电量/哨兵 · 入口 + 服务专家",
  preview: true,
});
