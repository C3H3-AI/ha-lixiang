
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
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
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

const BUILTIN_FONT_BASE = "/lixiang_auto/lixiang-fonts";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";   // 用户自定义优先
let __fontBase = DEFAULT_FONT_BASE;   // setConfig 可覆盖
const __fontFallback = BUILTIN_FONT_BASE;

const I18N = {
  title: "充电管理",          // ★ 官方标题（不是"充电"）
  status: "充电状态",
  notCharging: "等待充电",   // ★ 官方文案（不是"未充电"）
  charging: "充电中",
  done: "充电完成",        // ★ 官方文案（不是"已充满"）
  power: "充电效率",
  powerKw: "充电功率",
  volt: "输入电压",     // ★ 官方 4 项指标之三
  amp: "输入电流",      // ★ 官方 4 项指标之四  // ★ 官方 4 项指标之二（引擎键名 av = A×V）   // ★ 2026-10-14 官方文案（不是"充电功率"）
  remain: "剩余时间",
  records: "充电记录",        // ★ 官方右上角入口
  remainPrefix: "剩余",       // ★ 官方「剩余2小时7分钟」
  hour: "小时",
  apptEnd: "按时结束",        // ★ 官方文案
  hint: "日常快充建议最高设置为95%，95%以上充电功率较低。",
  footer: "适用于交流充电桩和理想20kW直流充电桩",
  limit: "充电上限",
  mode: "充电模式",
  appt: "预约充电",
  apptTime: "预约时间段",
  acGun: "交流慢充",
  dcGun: "直流快充",
  portCover: "充电口盖",
  coverOpen: "开",
  coverClose: "关",
  coverTapHint: "点开合",
  fault: "充电故障",
  monthKwh: "本月充电量",
  monthTimes: "本月次数",
  totalKwh: "累计充电量",
  history: "充电记录",
  dc: "直流",
  // ★ 2026-10-11：明细标签按充电类型显示（此前只有"直流/交流"两种，
  //   5C/4C 超充被错误地标成了"交流"）
  ctDc: "直流快充",
  ctAc: "交流慢充",
  ct5c: "5C超充",
  ct4c: "4C超充",
  ac: "交流",
  times: "次",
  chargePrefix: "充电",
  noData: "暂无数据",
  loading: "加载中…",
  settings: "充电设置",
  year: "年",
  min: "分钟",
};

/** ★ 2026-10-11：充电类型筛选（对齐 App）。
 *  value 直传服务端 charging_type：0=聚合全部 / 1=DC 直流 / 2=AC 交流 /
 *  "hpc"=理想超充(服务端聚合 5C+4C5C)。 */
const _CTYPES = [
  { value: 0,     label: "全部" },
  { value: 2,     label: "交流慢充" },
  { value: 1,     label: "直流快充" },
  { value: "hpc", label: "理想超充" },
];

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }
  lixiang-charge-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-charge-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { container-type:inline-size; position:relative; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:16px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
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
    /* ★ 2026-10-14 官方充电管理页：环形电量表 */
    .ringwrap { position:relative; width:150px; height:150px; margin:14px auto 4px; }
    .ring { width:100%; height:100%; display:block; }
    .ring .rbg { fill:none; stroke:#e8eaee; stroke-width:9; }
    .ring .rfg { fill:none; stroke:var(--lx-green); stroke-width:9; stroke-linecap:round;
                 transform:rotate(-90deg); transform-origin:50% 50%;
                 transition:stroke-dashoffset .5s ease; }
    .ringwrap .bolt { position:absolute; left:50%; top:-13px; width:34px; margin-left:-17px; }
    .ringwrap .rtx { position:absolute; inset:0; display:flex; align-items:center;
                     justify-content:center; font-weight:600; }
    .ringwrap .rtx span { font-size:42px; letter-spacing:-1px; }
    .ringwrap .rtx small { font-size:15px; margin:12px 0 0 3px; }
    .remline { text-align:center; font-size:15px; color:var(--lx-t2); margin:2px 0 12px; }
    /* 上限滑杆块（官方） */
    .limitbox { margin:12px 20px 0; background:var(--lx-card); border-radius:18px; padding:16px; }
    .limitbox .lbrow1 { display:flex; align-items:baseline; justify-content:space-between;
                        font-size:16px; font-weight:500; }
    .limitbox .lbrow1 b { font-size:16px; font-weight:600; }
    .limitbox .rng { -webkit-appearance:none; appearance:none; width:100%; height:6px;
                     margin:16px 0 6px; border-radius:3px; background:linear-gradient(
                       to right, var(--lx-green) 0%, var(--lx-green) var(--fill,100%),
                       #e8eaee var(--fill,100%), #e8eaee 100%); outline:none; }
    .limitbox .rng::-webkit-slider-thumb { -webkit-appearance:none; width:20px; height:20px;
                      border-radius:50%; background:#fff; box-shadow:0 1px 4px rgba(0,0,0,.25); }
    .limitbox .rng::-moz-range-thumb { width:18px; height:18px; border:0; border-radius:50%;
                      background:#fff; box-shadow:0 1px 4px rgba(0,0,0,.25); }
    .limitbox .lbrow2 { display:flex; justify-content:space-between; font-size:12px; color:var(--lx-t3); }
    .limitbox .hint { margin-top:12px; font-size:12px; line-height:1.6; color:var(--lx-t3); }
    /* 设置行（预约充电 / 按时结束） */
    .setcard { margin:12px 20px 0; background:var(--lx-card); border-radius:18px; padding:0 16px; }
    .setcard .setrow { display:flex; align-items:center; justify-content:space-between;
                       min-height:56px; border-bottom:1px solid rgba(0,0,0,.05); }
    .setcard .setrow:last-child { border-bottom:0; }
    .setcard .sl { font-size:16px; }
    .setcard .tg { position:relative; width:50px; height:30px; border-radius:15px;
                   background:#dfe3e9; transition:background .2s; cursor:pointer; flex:0 0 auto; }
    .setcard .tg i { position:absolute; top:3px; left:3px; width:24px; height:24px; border-radius:50%;
                     background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.2); transition:left .2s; }
    .setcard .tg.on { background:var(--lx-blue); }
    .setcard .tg.on i { left:23px; }
    .setcard .tmin { border:0; background:transparent; font-size:16px; color:var(--lx-t2);
                     text-align:right; font-family:inherit; }
    .pfoot { margin:14px 20px 26px; text-align:center; font-size:12px; color:var(--lx-t3); }
    .topbar .reclink { margin-left:auto; margin-right:10px; border:0; background:transparent;
                       font-size:15px; color:var(--lx-t1); font-family:inherit; cursor:pointer; }
  .hero .dot { width:9px; height:9px; border-radius:50%; background:var(--lx-t3); }
  .hero .dot.on { background:var(--lx-green); box-shadow:0 0 0 4px rgba(52,199,89,.16); }
  .hero .dot.err { background:var(--lx-red); }
  .hero .st { font-size:16px; font-weight:500; }
  .hero .sub { margin-left:auto; font-size:12px; color:var(--lx-t3); }
  /* 三栏：前两个数值等宽，第三个（模式·文字）给更多空间 */
  /* ★ 2026-10-14 车主："剩余时间下面，一行直接显示四个，跟 app 保持一致"
     官方充电管理页 4 项指标就是【一行四列】（44km/hr · 8.8kW · 24A · 373V）。 */
  .hero .metrics { display:grid; grid-template-columns:repeat(4, minmax(0,1fr));
                   gap:6px; margin-top:14px; }
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
  /* ★ 2026-10-09：充电口盖胶囊可点开合（switch cpCtrl 实车实测可用）*/
  .pill.act { cursor:pointer; -webkit-tap-highlight-color:transparent; }
  .pill.act:hover { background:var(--lx-line); }
  .pill.act:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .pill.busy { opacity:.55; }
  .pill.ro { opacity:.75; }
  .pill .hint { font-size:10px; color:var(--lx-t3); }

  /* ★ 2026-10-09 新增：本卡片此前没有 toast 能力（无 .toast 元素/方法），
     而充电口盖开合必须给出明确反馈（下发中/失败原因），故补齐。 */
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:80%; text-align:center; }
  .toast.show { opacity:1; transform:translate(-50%,0); }
  .toast.ok { background:rgba(28,150,70,.92); }
  .toast.err { background:rgba(200,40,40,.92); }

  /* ── 记录（年折叠）── */
  .sect { padding:18px 20px 0; }
  /* ★ 2026-10-11：充电类型筛选（对齐 App 的「全部/交流慢充/直流快充/理想超充」）*/
  .ctabs { display:flex; gap:22px; padding:2px 16px 0; overflow-x:auto;
           -webkit-overflow-scrolling:touch; }
  .ctab { font-size:14px; color:var(--lx-t3); padding:9px 0 11px; cursor:pointer;
          white-space:nowrap; position:relative; transition:color .15s; }
  .ctab:hover { color:var(--lx-t2); }
  .ctab.on { color:var(--lx-t1); font-weight:600; }
  .ctab.on::after { content:""; position:absolute; left:0; right:0; bottom:5px;
                    height:2.5px; border-radius:2px; background:var(--lx-blue); }
  .rec .tag.hpc { color:#B45309; background:rgba(180,83,9,.10); }
  @media (prefers-color-scheme: dark) {
    .rec .tag.hpc { color:#FBBF24; background:rgba(251,191,36,.14); }
  }
  .sect h2 { font-size:14px; font-weight:500; margin:0 0 10px; }
  /* ── 年份折叠卡片 ── */
  .year { border-radius:14px; background:var(--lx-card); margin-bottom:10px;
          overflow:hidden; }
  .year .yh { display:flex; align-items:center; min-height:52px; padding:0 16px;
              cursor:pointer; transition:background .15s; }
  .year .yh:hover { background:rgba(0,0,0,.03); }
  .year .yn { font-size:15px; font-weight:600; }
  .year .ys { margin-left:10px; font-size:12px; color:var(--lx-t3); }
  .year .ar { margin-left:auto; color:var(--lx-t3); transition:transform .2s;
              display:inline-block; }
  .year.open .yh .ar { transform:rotate(90deg); }
  /* 年内月份区（折叠） */
  .year .ym { display:none; }
  .year.open .ym { display:block; }

  /* ── 月份行（在年份卡片内，不再是独立卡片） ── */
  .month { border-top:1px solid var(--lx-line); }
  .month .mh { display:flex; align-items:center; min-height:48px; padding:0 16px;
               cursor:pointer; transition:background .15s; }
  .month .mh:hover { background:rgba(0,0,0,.03); }
  .month .mn { font-size:14px; color:var(--lx-t2); white-space:nowrap; min-width:52px; }
  .month .ar { margin-left:6px; color:var(--lx-t3); transition:transform .2s;
               display:inline-block; }
  .month.open .ar { transform:rotate(90deg); }
  /* ★ 内联明细：点开即在该月下方（车主明确要求的交互） */
  .month .md { display:none; padding:0 16px 8px 16px; }
  .month.open .md { display:block; }
  .month .md .rec { display:flex; align-items:center; min-height:40px;
                    border-top:1px dashed var(--lx-line); font-size:13px; }
  .month .md .rec .t { color:var(--lx-t2); min-width:104px; }
  .month .md .rec .tag { font-size:11px; padding:2px 7px; border-radius:6px;
                         color:var(--lx-t3); background:var(--lx-line); margin-right:8px; }
  .month .md .rec .tag.ac { color:#0A7B3E; background:rgba(10,123,62,.10); }
  .month .md .rec .tag.hpc { color:#B45309; background:rgba(180,83,9,.10); }
  .month .md .rec .c { margin-left:auto; font-family:"LxNum"; font-weight:500; }
  .month .md .rec .u { font-size:11px; color:var(--lx-t3); margin-left:3px; }
  .month .mbar { flex:1; height:6px; border-radius:3px; background:var(--lx-line);
                 overflow:hidden; margin:0 10px; min-width:30px; }
  .month .mbar > i { display:block; height:100%; border-radius:3px; background:#2C6BFF;
                     transition:width .3s ease; }
  .month.top .mv { color:var(--lx-t1); font-weight:600; }
  .month.top .mbar > i { background:#1E5AE0; }
  .month .mt { font-size:11px; color:var(--lx-t3); margin-left:8px; min-width:52px;
               text-align:right; white-space:nowrap; }
  .month .mv { font-family:"LxNum"; font-size:14px; font-weight:500; }
  .month .mu { font-size:11px; color:var(--lx-t3); margin-left:3px; }
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
  .row.click:focus-visible, .m:focus-visible,
  button:focus-visible, input:focus-visible {
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

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }

    /* ── 手机断点（≤480px）── */
    @container (max-width: 480px) {
      /* 官方在手机宽度也是【一行四列】，不压成两行 */
      .hero .metrics { grid-template-columns: repeat(4, minmax(0,1fr)); gap:4px; }
      .hero .m .v { font-size:19px; }
      .hero .m .v small { font-size:10px; margin-left:1px; }
      .hero .m .l { font-size:10.5px; }
      .stat3 { grid-template-columns: minmax(0,1fr) minmax(0,1fr); }
      .grid, .row3 { grid-template-columns: minmax(0,1fr); }
    }
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
    // ★ 充电类型筛选：默认 0=全部（聚合 4 种类型，与 App 一致）
    if (this._ctIdx === undefined) { this._ctIdx = 0; }
    if (this._ctype === undefined) { this._ctype = _CTYPES[0].value; }
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
        <img class="back" id="back" src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="返回">
        <h1>${I18N.title}</h1>
        <button class="reclink" id="go-records" type="button">${I18N.records}</button>
        <div class="refresh" id="refresh" role="button" tabindex="0" aria-label="刷新数据">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt="" style="transform:rotate(-90deg)">
        </div>
      </div>
      <div class="hero">
        <div class="row1">
          <span class="dot" id="dot"></span>
          <span class="st" id="st">—</span>
          <span class="sub" id="sub"></span>
        </div>
        <!-- ★ 2026-10-14 对齐官方「充电管理」页：环形电量表（SOC + 绿弧 + 闪电） -->
        <div class="ringwrap">
          <svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
            <circle class="rbg" cx="60" cy="60" r="52"></circle>
            <circle class="rfg" id="ring-arc" cx="60" cy="60" r="52"></circle>
          </svg>
          <img class="bolt" src="${__iconBase}/ic_home_lightning.png" onerror="__lxIconFallback(this)" alt="">
          <div class="rtx"><span id="ring-soc">—</span><small>%</small></div>
        </div>
        <div class="remline" id="rem-text">—</div>
        <div class="metrics">
          <div class="m"><div class="v"><span id="m-power">—</span><small id="u-power">km/hr</small></div>
            <div class="l">${I18N.power}</div></div>
        <div class="m"><div class="v"><span id="m-pw">—</span><small>kW</small></div>
          <div class="l">${I18N.powerKw}</div></div>
        <div class="m"><div class="v"><span id="m-amp">—</span><small id="u-amp">A</small></div>
          <div class="l">${I18N.amp}</div></div>
        <div class="m"><div class="v"><span id="m-volt">—</span><small id="u-volt">V</small></div>
          <div class="l">${I18N.volt}</div></div>
        </div>
      </div>
      <!-- ★ 2026-10-14 对齐官方：充电上限可拖滑杆 + 提示原文 -->
      <div class="limitbox">
        <div class="lbrow1"><span>${I18N.limit}</span><b id="limitp">—</b></div>
        <input class="rng" type="range" id="limit-range" min="50" max="100" step="1" value="100"
               aria-label="${I18N.limit}">
        <div class="lbrow2"><span id="limit-min">50%</span><span id="limit-max">100%</span></div>
        <div class="hint">${I18N.hint}</div>
      </div>
      <div class="setcard">
        <div class="setrow"><span class="sl">${I18N.appt}</span>
          <span class="tg" id="tg-appt" role="switch" tabindex="0" aria-checked="false"><i></i></span></div>
        <div class="setrow"><span class="sl">${I18N.apptEnd}</span>
          <input class="tmin" type="time" id="end-time" aria-label="${I18N.apptEnd}"></div>
      </div>
      <div class="pfoot">${I18N.footer}</div>
      <div class="stat3">
        <div class="st"><div class="v"><span id="m-mode">—</span></div>
            <div class="l">${I18N.mode}</div></div>
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
        <span class="pill" id="p-cover" role="button" tabindex="0"
              aria-label="${I18N.portCover} ${I18N.coverTapHint}"><span class="d"></span>${I18N.portCover} <b id="v-cover">—</b></span>
        <span class="pill" id="p-appt"><span class="d"></span>${I18N.appt} <b id="v-appt">—</b></span>
        <span class="pill" id="p-fault"><span class="d"></span>${I18N.fault} <b id="v-fault">—</b></span>
      </div>
      <div class="ctabs" id="ctabs" role="tablist"
           aria-label="${I18N.history}${I18N.chargeType}">
        ${_CTYPES.map((c, i) => `<span class="ctab${i === 0 ? " on" : ""}" role="tab"
            data-ct="${i}" tabindex="0"
            aria-selected="${i === 0 ? "true" : "false"}">${c.label}</span>`).join("")}
      </div>
      <div class="sect">
        <h2>${I18N.history}</h2>
        <div id="years"><div class="empty">${I18N.loading}</div></div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    const _bk = this.querySelector("#back");
    this._a11y(_bk, "返回", () => _bk.click());
    _bk.addEventListener("click", () => {
      const p = (this._config.nav || {}).back || "/lixiang/app";
      lxNavigate(this, p);
    });
    // ★ 2026-10-14 官方充电管理页：上限滑杆 / 预约开关 / 按时结束 / 记录入口
    const rng = this.querySelector("#limit-range");
    if (rng) {
      rng.addEventListener("change", async () => {
        const eid = this._eid("limit_num");
        if (!eid) { this._toast("充电上限不可设置", "err"); return; }
        const v = Number(rng.value);
        try {
          await this._hass.callService("number", "set_value", { entity_id: eid, value: v });
          this._toast("充电上限已设为 " + v + "%", "ok");
        } catch (err) { this._toast("设置失败：" + ((err && err.message) || "未知"), "err"); }
      });
    }
    const tgEl = this.querySelector("#tg-appt");
    if (tgEl) {
      const flip = async () => {
        const eid = this._eid("appt_sw");
        if (!eid) { this._toast("预约充电不可用", "err"); return; }
        const st = this._hass && this._hass.states ? this._hass.states[eid] : null;
        const on = !!(st && st.state === "on");
        try {
          await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: eid });
          tgEl.classList.toggle("on", !on);
          tgEl.setAttribute("aria-checked", !on ? "true" : "false");
          this._toast(I18N.appt + (on ? "已关闭" : "已开启"), "ok");
        } catch (err) { this._toast("操作失败：" + ((err && err.message) || "未知"), "err"); }
      };
      this._a11y(tgEl, I18N.appt, flip);
      tgEl.addEventListener("click", flip);
    }
    const teEl = this.querySelector("#end-time");
    if (teEl) {
      teEl.addEventListener("change", async () => {
        const eid = this._eid("end_time");
        if (!eid || !teEl.value) { this._toast("按时结束不可设置", "err"); return; }
        try {
          await this._hass.callService("time", "set_value", { entity_id: eid, time: teEl.value + ":00" });
          this._toast(I18N.apptEnd + " " + teEl.value, "ok");
        } catch (err) { this._toast("设置失败：" + ((err && err.message) || "未知"), "err"); }
      });
    }
    const rec = this.querySelector("#go-records");
    if (rec) {
      const go = () => {
        const t = this.querySelector("#ctabs") || this.querySelector("#years");
        if (t && t.scrollIntoView) t.scrollIntoView({ behavior: "smooth", block: "start" });
      };
      this._a11y(rec, I18N.records, go);
      rec.addEventListener("click", go);
    }
    // ★ 2026-10-11：充电类型筛选绑定（漏了这行就只是"画了不响应"）
    this._bindCTypes();
    const rf2 = this.querySelector("#refresh");
    const doRefresh2 = () => this._refreshAll();
    this._a11y(rf2, "刷新数据", doRefresh2);
    rf2.addEventListener("click", doRefresh2);

    // ★ 2026-10-09：充电口盖胶囊可点开合（switch cpCtrl，实车实测可用）
    const pcv = this.querySelector("#p-cover");
    if (pcv) {
      const doCover = () => this._toggleCover();
      this._a11y(pcv, `${I18N.portCover} ${I18N.coverTapHint}`, doCover);
      pcv.addEventListener("click", doCover);
    }

    
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
          Promise.resolve(this._refreshAll()).finally(() => {
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

  /** ★ 2026-10-14 时长格式化：官方「剩余2小时7分钟」（不是 185 min）。 */
  _fmtDur(minutes) {
    const t = Math.max(0, Math.round(Number(minutes) || 0));
    const h = Math.floor(t / 60), m = t % 60;
    if (h <= 0) return m + I18N.min;
    if (m === 0) return h + I18N.hour;
    return h + I18N.hour + m + I18N.min;
  }

  /** ★ 2026-10-14 上限滑杆：范围取 number 实体的 min/max（官方页显示 80%–100%）。 */
  _syncLimitSlider(lim) {
    const r = this.querySelector("#limit-range");
    if (!r) return;
    const st = this._hass && this._hass.states ? this._hass.states[this._eid("limit_num")] : null;
    const a = (st && st.attributes) || {};
    const mn = Number.isFinite(Number(a.min)) ? Number(a.min) : 50;
    const mx = Number.isFinite(Number(a.max)) ? Number(a.max) : 100;
    r.min = String(mn); r.max = String(mx);
    const v = lim == null ? mx : Math.max(mn, Math.min(mx, lim));
    if (document.activeElement !== r) r.value = String(Math.round(v));
    const pct = mx > mn ? ((v - mn) / (mx - mn)) * 100 : 100;
    r.style.setProperty("--fill", pct + "%");
    const la = this.querySelector("#limit-min"), lb = this.querySelector("#limit-max");
    if (la) la.textContent = mn + "%";
    if (lb) lb.textContent = mx + "%";
  }

  /** 轻提示（★ 2026-10-09 新增：充电口盖开合需要"已下发/失败原因"的明确反馈） */
  _toast(msg, kind) {
    const t = this.querySelector(".toast");
    if (!t) return;
    t.textContent = msg;
    t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2600);
  }

  /** ★ 2026-10-09：开合充电口盖（switch 域，cmdKey=cpCtrl；实车实测可用）。
   *  不可控时（旧版本 / 车型无此实体）给出明确说明，不静默失败。 */
  async _toggleCover() {
    const sw = this._eid("port");
    if (!sw) {
      this._toast(`${I18N.portCover}控制未接入（仅显示状态）`, "err");
      return;
    }
    const st = this._st(sw);
    if (!st) { this._toast("实体不存在", "err"); return; }
    if (this._coverBusy) return;
    const on = ["on", "open", "opening", "开启", "true"].some(
      (v) => String(st.state).includes(v));
    this._coverBusy = true;
    const el = this.querySelector("#p-cover");
    if (el) el.classList.add("busy");
    try {
      await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: sw });
      // 开合需要数秒，服务端状态回读更慢 → 用 12s 乐观值
      this._coverOptim = !on; this._coverOptimUntil = Date.now() + 12000;
      this._toast(`${I18N.portCover}${on ? "关闭" : "开启"}指令已下发`, "ok");
      this._update();
      setTimeout(() => { this._coverOptim = null; this._update(); }, 12000);
    } catch (e) {
      this._toast(`${I18N.portCover}操作失败：` + ((e && e.message) || "未知"), "err");
    } finally {
      this._coverBusy = false;
      if (el) el.classList.remove("busy");
    }
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

  /** ★ 2026-10-09：充电口盖胶囊 = 可点开合（有 switch 时）+ 状态显示。
   *  状态优先取可控制的 switch（cpCtrl），无则退到只读 binary_sensor（旧版本）。 */
  _updateCover() {
    const q = (s) => this.querySelector(s);
    const sw = this._eid("port");
    const ro = this._eid("port_cover");
    let on = null;
    if (this._coverOptim != null && Date.now() < (this._coverOptimUntil || 0)) {
      on = this._coverOptim;                       // 乐观值（开合需数秒）
    } else {
      const src = (sw && this._st(sw)) ? sw : ro;
      const v = this._txt(src);
      if (v != null) {
        on = ["on", "open", "opening", "开启", "true"].some(
          (x) => String(v).includes(x));
      }
    }
    const val = q("#v-cover");
    if (val) {
      val.textContent = on == null ? "—" : (on ? I18N.coverOpen : I18N.coverClose);
    }
    const el = q("#p-cover");
    if (el) {
      el.className = "pill" + (on === true ? " on" : "")
                   + (sw ? " act" : " ro")
                   + (this._coverBusy ? " busy" : "");
      el.setAttribute("aria-pressed", on === true ? "true" : "false");
      el.title = sw ? `${I18N.portCover}${I18N.coverTapHint}` : "该版本仅支持查看状态";
    }
  }

  /** ★ 2026-10-11：绑定充电类型筛选（切换后重新拉取该类型的统计）。 */
  _bindCTypes() {
    const box = this.querySelector("#ctabs");
    if (!box) return;
    box.querySelectorAll(".ctab").forEach((el) => {
      const i = Number(el.dataset.ct);
      const a = () => this._switchCType(i);
      this._a11y(el, _CTYPES[i] ? _CTYPES[i].label : "筛选", a);
      el.addEventListener("click", a);
      // 键盘可达（role=tab）
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); a(); }
      });
    });
  }

  _switchCType(i) {
    if (!_CTYPES[i] || this._ctIdx === i) return;
    this._ctIdx = i;
    this._ctype = _CTYPES[i].value;
    // 视觉：选中态 + aria
    this.querySelectorAll(".ctab").forEach((el, k) => {
      const on = k === i;
      el.classList.toggle("on", on);
      el.setAttribute("aria-selected", on ? "true" : "false");
    });
    // 数据：清缓存 → 重新拉该类型（_fetchStats 的守卫依赖 _years 为空）
    this._years = null;
    this._selMonth = null;
    this._error = null;
    // ★ 新一轮数据：重置年份展开状态，让其重新默认展开最新年
    this._yearsInited = false;
    this._openYears = new Set();
    const box = this.querySelector("#years");
    if (box) box.innerHTML = `<div class="empty">${I18N.loading}</div>`;
    this._fetchStats();
  }

  async _fetchStats() {
    if (!this._hass || this._years || this._fetching) return;
    this._fetching = true;
    try {
      // ★ 带上当前筛选类型（0=全部聚合 / 1=DC / 2=AC / "hpc"=理想超充）
      const r = await this._hass.callService("lixiang_auto", "get_charge",
        { charging_type: this._ctype }, undefined, true, true);
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
      // ★★ 2026-10-11 修复（与月度统计同类）：
      //   原来手写两次请求，只拉 AC(2) + DC(1) —— **漏掉 5C(3)/4C(4) 超充**，
      //   且**不跟随筛选**（选「理想超充」仍显示全部类型）。
      //   服务端 charging_type=0 会聚合全部 4 种；"hpc" 聚合 3+4。
      //   故一次请求即可，并把当前筛选传下去。
      const r = await this._hass.callService("lixiang_auto", "get_charge",
        { dt: `${year}-${month}`, charging_type: this._ctype }, undefined, true, true);
      const payload = (r && r.response) || r;
      const first = payload && Object.values(payload)[0];
      const rows = first && first.data;
      if (Array.isArray(rows)) this._monthRecords = rows;
    } catch (e) { /* 静默 */ }
    this._renderList();
  }

  /** 渲染月度列表。
   *
   * ★★ 2026-10-11 结构重构（车主反馈：「点击10月，明细在下面，根本看不到」）：
   *   原先按【年折叠】+ 明细渲染在页面底部的另一个区域（#list）→ 用户点完
   *   要滚到页面下方才看得到，体验很差。
   *   现改为 App 的结构：**扁平月度列表 + 点击月份内联展开明细**。
   *   · 非最新年份显示「2025年8月」前缀（同年只显示「8月」），与 App 一致
   *   · 明细插在该月**下方**，点开即见
   */
  /** 渲染月度列表。
   *
   * 结构演进（两次都由车主反馈驱动）：
   *  ① 原先「按年折叠 + 明细渲染在页面底部」→ 车主："点击10月，明细在下面，根本看不到"
   *     → 改为扁平 + 内联明细
   *  ② 但扁平列表在年份多时会很长 → 车主："充电明细建议按年也折叠"
   *     → **年份折叠 + 月份内联明细**（兼顾：列表短 + 点开即见）
   *
   * 年份头带汇总（月数 / 总次数 / 总电量）；默认展开最新年份。
   */
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
    if (!(this._openYears instanceof Set)) this._openYears = new Set();
    // ★★ 2026-10-12 修复（车主："26年好像折叠不了"）：
    //   原写法 `if (!this._openYears.size) add(latest)` 会在**每次渲染**时检查，
    //   于是「折叠唯一展开的年份 → 集合变空 → 重渲染又被自动展开」→ **永远折不上**。
    //   改为【每个数据周期只初始化一次】：切换筛选/重新拉取时才重置。
    const latest = yl[0] && yl[0].year;
    if (!this._yearsInited) {
      this._yearsInited = true;
      if (latest != null) this._openYears.add(String(latest));
    }

    box.innerHTML = yl.map((y) => {
      const months = y.months || [];
      const open = this._openYears.has(String(y.year));
      const totKwh = months.reduce((a, m) => a + (Number(m.chargingCapacity) || 0), 0);
      const totTimes = months.reduce((a, m) => a + (Number(m.chargingTimes) || 0), 0);
      // 条形按【所在年】归一（跨年不可比）
      const mx = Math.max(1, ...months.map((m) => Number(m.chargingCapacity) || 0));
      const rows = months.map((m) => {
        const sel = this._selMonth && this._selMonth.year === y.year
                    && this._selMonth.month === m.month;
        const v = Number(m.chargingCapacity) || 0;
        const w = v > 0 ? Math.max(3, Math.round((v / mx) * 100)) : 0;
        const isTop = v > 0 && v >= mx;
        return `<div class="month${sel ? " open" : ""}${isTop ? " top" : ""}"
                     data-y="${y.year}" data-m="${m.month}">
            <div class="mh" role="button" tabindex="0"
                 aria-expanded="${sel ? "true" : "false"}">
              <span class="mn">${m.month} 月</span>
              <span class="mt">${I18N.chargePrefix || ""}${m.chargingTimes} ${I18N.times}</span>
              <span class="mbar" aria-hidden="true"><i style="width:${w}%"></i></span>
              <span class="mv">${Number(m.chargingCapacity).toFixed(2)}</span>
              <span class="mu">kW·h</span>
              <span class="ar">›</span>
            </div>
            <div class="md" id="md-${y.year}-${m.month}"></div>
          </div>`;
      }).join("");
      if (!months.length) return "";
      return `<div class="year${open ? " open" : ""}" data-year="${y.year}">
          <div class="yh" role="button" tabindex="0" aria-expanded="${open ? "true" : "false"}">
            <span class="yn">${y.year} 年</span>
            <span class="ys">${months.length} 个月 · ${totTimes} ${I18N.times} · ${totKwh.toFixed(1)} kW·h</span>
            <span class="ar">›</span>
          </div>
          <div class="ym">${rows}</div>
        </div>`;
    }).join("");

    // 年份头：折叠/展开
    box.querySelectorAll(".yh").forEach((h) => {
      const wrap = h.parentElement;
      const yy = wrap.dataset.year;
      const toggle = () => {
        if (this._openYears.has(yy)) this._openYears.delete(yy);
        else this._openYears.add(yy);
        this._renderYears();
      };
      this._a11y(h, `${yy} 年 展开/收起`, toggle);
      h.addEventListener("click", toggle);
      h.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    });

    // 月份行：内联展开明细（保留车主认可的交互）
    box.querySelectorAll(".mh").forEach((h) => {
      const wrap = h.parentElement;
      const yy = Number(wrap.dataset.y), mm = Number(wrap.dataset.m);
      const toggle = async () => {
        const isOpen = this._selMonth && this._selMonth.year === yy
                       && this._selMonth.month === mm;
        if (isOpen) {
          this._selMonth = null; this._monthRecords = null;
          wrap.classList.remove("open");
          h.setAttribute("aria-expanded", "false");
          const d = wrap.querySelector(".md"); if (d) d.innerHTML = "";
          return;
        }
        this._selMonth = { year: yy, month: mm };
        box.querySelectorAll(".month.open").forEach((el) => {
          el.classList.remove("open");
          const hh = el.querySelector(".mh");
          if (hh) hh.setAttribute("aria-expanded", "false");
          const dd = el.querySelector(".md"); if (dd) dd.innerHTML = "";
        });
        wrap.classList.add("open");
        h.setAttribute("aria-expanded", "true");
        const container = wrap.querySelector(".md");
        if (container) container.innerHTML = `<div class="empty">${I18N.loading}</div>`;
        await this._fetchMonth(yy, mm);
      };
      this._a11y(h, `${yy} 年 ${mm} 月 充电明细`, toggle);
      h.addEventListener("click", toggle);
      h.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    });
  }

  _renderList() {
    if (!this._selMonth) return;
    const box = this.querySelector(
      `#md-${this._selMonth.year}-${this._selMonth.month}`);
    if (!box) return;
    const rows = this._monthRecords || [];
    if (!rows.length) {
      box.innerHTML = `<div class="empty">${I18N.noData}</div>`;
      return;
    }
    const sorted = rows.slice().sort((a, b) => Number(b.startTime) - Number(a.startTime));
    box.innerHTML = sorted.map((r) => {
      const d = new Date(Number(r.startTime));
      const mm = `${d.getMonth() + 1}月${d.getDate()}日`;
      const hh = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      // ★ 按 chargingType 给出准确类型名（1=DC / 2=AC / 3=5C / 4=4C超充）
      const ct = Number(r.chargingType);
      const _names = { 1: I18N.ctDc, 2: I18N.ctAc, 3: I18N.ct5c, 4: I18N.ct4c };
      const _cls = { 1: "", 2: " ac", 3: " hpc", 4: " hpc" };
      const tagName = _names[ct] || I18N.ctDc;
      return `<div class="rec">
          <span class="t">${mm} ${hh}</span>
          <span class="tag${_cls[ct] !== undefined ? _cls[ct] : ""}">${tagName}</span>
          <span class="c">${Number(r.chargingCapacity).toFixed(2)}</span><span class="u">kW·h</span>
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
    // ★ 2026-10-14：状态行已显示「充电中」，这里不再重复一遍（官方页状态由环形表表达）
    q("#sub").textContent = fault && String(fault) !== "off" && String(fault) !== "正常" ? "充电故障" : "";

    // ★ 2026-10-14 对齐官方：环形电量表（SOC）+ 上限滑杆
    const lim = this._num(this._eid("limit") || this._eid("limit_sensor"));
    const soc = this._num(this._eid("soc"));
    const arc = q("#ring-arc");
    if (arc) {
      const C = 2 * Math.PI * 52;
      const frac = soc == null ? 0 : Math.max(0, Math.min(100, soc)) / 100;
      arc.style.strokeDasharray = C + " " + C;
      arc.style.strokeDashoffset = String(C * (1 - frac));
    }
    const rs = q("#ring-soc");
    if (rs) rs.textContent = soc == null ? "—" : String(Math.round(soc));
    q("#limitp").textContent = lim == null ? "—" : lim + "%";
    this._syncLimitSlider(lim);
    // 预约充电开关 / 按时结束
    const apptEid = this._eid("appt_sw");
    const apptSt = apptEid && this._hass && this._hass.states ? this._hass.states[apptEid] : null;
    const tg0 = q("#tg-appt");
    if (tg0) {
      const on = !!(apptSt && apptSt.state === "on");
      tg0.classList.toggle("on", on);
      tg0.setAttribute("aria-checked", on ? "true" : "false");
      tg0.setAttribute("aria-label", I18N.appt + (on ? "（已开启）" : "（已关闭）"));
    }
    const te0 = q("#end-time");
    if (te0 && document.activeElement !== te0) {
      const tSt = this._hass && this._hass.states[this._eid("end_time")];
      const tv = tSt && tSt.state && /^\d{1,2}:\d{2}/.test(tSt.state) ? tSt.state.slice(0, 5) : "";
      te0.value = tv;
    }

    // 三项
    const p = this._num(this._eid("power")), rm = this._num(this._eid("remain")), md = this._txt(this._eid("mode"));
    q("#m-power").textContent = p == null ? "—" : p;
      // ★ 2026-10-14 单位跟随实体（官方是 km/hr；原来写死 kW 是错的）
      const pSt = this._hass && this._hass.states[this._eid("power")];
      const pU = (pSt && pSt.attributes && pSt.attributes.unit_of_measurement) || "km/hr";
      const uEl = q("#u-power"); if (uEl) uEl.textContent = pU;
    // ★ 2026-10-14 官方格式：「剩余2小时7分钟」（原来显示 185 min）
    const rEl = q("#rem-text");
    if (rEl) rEl.textContent = rm == null ? I18N.remainPrefix + " —" : I18N.remainPrefix + this._fmtDur(rm);
      // ★ 官方 4 项指标之三/四：输入电压 / 输入电流（单位跟随实体）
      const Sx = (id) => (id && this._hass && this._hass.states) ? this._hass.states[id] : null;
      const vSt = Sx(this._eid("charge_voltage")), aSt = Sx(this._eid("charge_current"));
      const okv = (x) => x && x.state && !["unknown", "unavailable"].includes(x.state);
      q("#m-volt").textContent = okv(vSt) ? vSt.state : "—";
      q("#m-amp").textContent = okv(aSt) ? aSt.state : "—";
      const uv = q("#u-volt"), ua = q("#u-amp");
      if (uv && vSt && vSt.attributes && vSt.attributes.unit_of_measurement) uv.textContent = vSt.attributes.unit_of_measurement;
      if (ua && aSt && aSt.attributes && aSt.attributes.unit_of_measurement) ua.textContent = aSt.attributes.unit_of_measurement;
      q("#m-pw").textContent = this._num(this._eid("charge_power")) == null ? "—" : this._num(this._eid("charge_power"));
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
    this._updateCover();
    set("#p-appt", "#v-appt", this._eid("appointment"));
    const fv = this._txt(this._eid("fault"));
    q("#v-fault").textContent = fv == null ? "—" : (fv === "off" ? "正常" : fv);
    q("#p-fault").className = "pill" + (fv && fv !== "off" ? " warn" : "");

    this._fetchStats();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangChargePage);

window.customCards = window.customCards || [];
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "充电（二级页）",
  description: "充电实时状态 + 按月记录（年折叠）+ 单次明细",
  preview: true,
});
