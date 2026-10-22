
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

/* ★ 2026-10-21 新增：座椅底图基址。
   底图是官方按车型出图的 PNG/WebP（1086×1467），位于集成
   www/lixiang-climate/。与图标一样：/local 优先（用户可覆盖），
   缺失时回退集成内置。 */
const BUILTIN_SEAT_BASE = "/lixiang_auto/lixiang-climate";
const DEFAULT_SEAT_BASE = "/local/lixiang-climate";
/* ★ 座椅底图**随集成分发**（在 www/lixiang-climate/，共 360KB），
   不像图标那样需要用户自备 → 默认直接用集成内置路径。
   /local 仅作"用户想换图"时的覆盖位。 */
let __seatBase = BUILTIN_SEAT_BASE;

/* ★ 座椅按钮坐标表（百分比，相对底图显示区）
   来源：官方空调页截图（1260×2844）实测 10 个圆钮中心。

   ★★ 2026-10-22 修正（车主："风扇和加热位置不对，需要往上挪"）：
     之前 y 用 `y_center×1086/1260/1467` 换算 —— **错了**。
     那个系数假设"底图比屏幕窄"，但底图实际是**铺满屏宽**的：
       底图 1086×1467，铺满屏宽 1260 时显示高 = 1260×1467/1086 = 1702
       起点 y0 = 302（顶栏下方），终点 2004（温度面板上方，实测吻合）
     正确换算：
       x% = x_center / 1260 × 100
       y% = (y_center − 302) / 1702 × 100
     修正后 y 全部上移约 17.7 个百分点（此前整体偏低，正是"要往上挪"）。
     x 方向原来就是对的（屏宽比例），未变。

   说明：5 座(i6) 与 6 座(i8) 前排相同；后排 5 座有中间座，6 座无。 */
const SEAT_POS = {
  /* ★★ 2026-10-22 第四次校准（车主："图片用的有问题…跟app相差很大"）：
     底图换成了 **ic_temperature_bg_x3.webp** —— 经与官方截图逐像素比对，
     这张才是官方空调页用的那张（清晰带描边、后排连体长椅、5 座布局）。
     原来的 ictemperaturebgi6 对比度极低（min 123 / std 14.6）是错的图
     （x3 为 min 96 / std 18.0，与官方一致）。
     坐标直接在新底图上目视标定：.research/app-icons/x3_calib.png（全部套准）。 */
  front: { heatL:[33,31], heatR:[67,31],
           ventL:[33,42], ventR:[67,42] },
  rear5: { heatL:[33,66], heatM:[50,66], heatR:[67,66],
           ventL:[33,78], ventR:[67,78] },
  rear6: { heatL:[33,66], heatR:[67,66],
           ventL:[33,78], ventR:[67,78] },
  strg:  [33,17],
};

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
  lixiang-climate-page { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    lixiang-climate-page { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
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

  /* ── ★ 座椅可视化区（2026-10-21 新增，对齐官方空调页）─────────────
     官方实测（1260×2844 截图，画框验证）：
       · 座椅区占整页约 55~60%，是空调页的**主体**
       · 圆形按钮直径 182px = 屏宽 14.4%，间距 210px = 16.7%
       · 按钮叠在座椅图上，浮于其上
     座椅底图：www/lixiang-climate/seatmap-*.webp（1086×1467，官方按车型出图）
     按钮坐标：由官方截图坐标 ÷1260 得到百分比 → 缩放不跑位。 */
  .seatbox { position:relative; margin:8px 16px 0; border-radius:18px;
             overflow:hidden; background:var(--lx-card); }
  /* ★ 2026-10-22：官方 L6 座椅底图对比度很低（亮度 123~250，std 仅 14.6）。
     ⚠️ 用 CSS contrast() 加强会**把浅色座椅整体推到纯白**、反而更看不见
        （实测 contrast(2.6) 后整个底图消失，按钮浮在空白上）——
        PIL 的 ImageEnhance.Contrast 与 CSS filter 行为不同，不能照搬。
     改为：轻微提对比 + 略压暗，保留座椅明暗层次。 */
  .seatbox img.bg { display:block; width:100%; height:auto; }
  /* 按钮：绝对定位，尺寸/位置全用百分比（相对底图 1086×1467） */
  /* ★ 2026-10-22 修复方向盘按钮变椭圆：
     原来只给 width:14.4% + aspect-ratio:1/1 —— 但按钮是 flex 容器，
     内含 <img> 时 aspect-ratio 会被内容高度撑破 → 变成竖椭圆（实测）。
     改为同时锁死 height（用 padding-bottom 技巧不行，直接算比例）：
       按钮是正方形，边长 = 底图宽 × 14.4%；容器宽度 = 底图宽
       → 高度用同样的百分比不可行（% 相对高度而非宽度）
     解法：用 aspect-ratio + overflow:hidden + 禁止内容撑高。 */
  /* 正方形按钮：width + aspect-ratio 定形；
     用 grid 居中而非 flex，避免内容（尤其 <img>）把高度撑破成椭圆。 */
  .seatbox .sbtn {
    position:absolute; width:14.4%; aspect-ratio:1/1;
    box-sizing:border-box; overflow:hidden;
    transform:translate(-50%,-50%);
    border-radius:50%; border:none; cursor:pointer;
    background:#FFF; box-shadow:0 2px 8px rgba(0,0,0,.12);
    display:grid; place-items:center;
    padding:0; transition:transform .12s, box-shadow .16s;
  }
  .seatbox .sbtn:active { transform:translate(-50%,-50%) scale(.92); }
  /* ★ 2026-10-22：**只有方向盘**开启时整圆变蓝（它只有 1 档）。
     座椅按钮保持白底，靠图标颜色深浅/数量表达档位（官方就是这样），
     否则深灰图标压在蓝底上看不清（实测踩到）。 */
  .seatbox .sbtn.on:has(img.strgi) { background:var(--lx-blue); }
  .seatbox .sbtn.on svg { stroke:#FFF; fill:#FFF; }
  /* 加热=描边波浪；通风=实心风扇（官方风格） */
  /* 方向盘用的是官方位图（96×96 正方形）——必须 object-fit:contain，
     否则被 width/height 双百分比拉成椭圆（实测踩到：蓝色胶囊形）。 */
  .seatbox .sbtn img.strgi { width:58%; height:58%; object-fit:contain; display:block; }
  .seatbox .sbtn.on img.strgi { filter:brightness(0) invert(1); }
  .seatbox .sbtn svg { width:52%; height:52%; stroke:#3A3A3A;
                       fill:none; stroke-width:1.7; stroke-linecap:round;
                       stroke-linejoin:round; }
  .seatbox .sbtn svg g, .seatbox .sbtn svg use,
  .seatbox .sbtn svg path, .seatbox .sbtn svg circle { fill:#3A3A3A; stroke:none; }
  /* ★ 2026-10-22 档位色阶（车主："扇叶颜色数量会变化"）：
     1档浅灰 → 2档中灰 → 3档深黑；激活(白底圆)时仍用深色，
     只有方向盘"已开启"才整圆变蓝+图标转白。 */
  .seatbox .sbtn[data-level="1"] svg path,
  .seatbox .sbtn[data-level="1"] svg use,
  .seatbox .sbtn[data-level="1"] svg circle { fill:#B9BFC7; }
  .seatbox .sbtn[data-level="1"] svg > path { stroke:#B9BFC7; fill:none; }
  .seatbox .sbtn[data-level="2"] svg path,
  .seatbox .sbtn[data-level="2"] svg use,
  .seatbox .sbtn[data-level="2"] svg circle { fill:#7B838D; }
  .seatbox .sbtn[data-level="2"] svg > path { stroke:#7B838D; fill:none; }
  .seatbox .sbtn[data-level="3"] svg path,
  .seatbox .sbtn[data-level="3"] svg use,
  .seatbox .sbtn[data-level="3"] svg circle { fill:#1F2430; }
  .seatbox .sbtn[data-level="3"] svg > path { stroke:#1F2430; fill:none; }
  /* 方向盘只有 1 档：开启时整圆蓝色 + 图标转白 */
  .seatbox .sbtn.on img.strgi { filter:brightness(0) invert(1); }
  /* 加热(波浪)是描边型：只对第一层 path 恢复描边 */
  .seatbox .sbtn svg > path { fill:none; stroke:#3A3A3A; }
  .seatbox .sbtn:disabled { opacity:.35; cursor:not-allowed; }
  /* 方向盘加热：顶部居中 */
  .seatbox .sbtn.strg { left:48.5%; top:12.5%; }

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
  /**
   * ★ 2026-10-22 新增：按「中文名 + domain」在 hass.states 里兜底查找实体。
   *
   * 背景：本卡主要靠 LixiangAutoBind 自动绑定（按 original_name 匹配），
   *   但 bind 依赖 hass.entities/hass.devices，某些场景（如 DOM 复用、
   *   bind 池为空）会解析失败 → 字段静默为 null → 按钮消失。
   *   对"方向盘加热"这类**唯一且必需**的控件，补一层直接名称匹配。
   *
   * 匹配规则：entity_id 以 `domain.` 开头 且 friendly_name 完全等于 name
   *           （必要时退化为包含匹配）。只在本集成实体里找，避免误命中。
   */
  _findByFriendly(name, domain) {
    const st = (this._hass && this._hass.states) || {};
    let loose = null;
    for (const id of Object.keys(st)) {
      if (domain && id.indexOf(domain + ".") !== 0) continue;
      // 只在理想汽车集成实体里找（entity_id 含 lixiang 或 li_xiang）
      if (!/li_?xiang|li_?xiang_auto/i.test(id)) continue;
      const fn = (st[id] && st[id].attributes && st[id].attributes.friendly_name) || "";
      if (fn === name) return id;
      if (!loose && fn && fn.indexOf(name) >= 0) loose = id;
    }
    return loose;
  }

  /**
   * ★ 2026-10-22：读座椅档位 0~3。
   * 实体是 fan 域，档位体现在 preset_mode（low/medium/high）或 percentage。
   * 实测 capabilities.preset_modes = ["low","medium","high"] → 三档。
   */
  _seatLevel(eid) {
    const st = this._st(eid);
    if (!st || ["off", "unknown", "unavailable"].includes(st.state)) return 0;
    const pm = (st.attributes && st.attributes.preset_mode) || "";
    const idx = ["low", "medium", "high"].indexOf(String(pm).toLowerCase());
    if (idx >= 0) return idx + 1;
    // 退化：用 percentage 反推（1~33→1，34~66→2，>=67→3）
    const p = Number(st.attributes && st.attributes.percentage);
    if (Number.isFinite(p) && p > 0) return p >= 67 ? 3 : (p >= 34 ? 2 : 1);
    return this._on(eid) ? 1 : 0;
  }

  /**
   * ★ 2026-10-22：按档位重绘座椅按钮图标（车主："风速扇叶颜色数量会变化，热风也一样"）。
   *
   * 表现方式：
   *   加热 = 竖直波浪线，**档位越高条数越多**（1档1条 / 2档2条 / 3档3条）
   *   通风 = 三叶风扇，**档位越高叶片越多**（1档1叶 / 2档2叶 / 3档3叶）
   *   颜色：档位越高越深（1档浅灰 / 2档中灰 / 3档近黑），激活时统一白色
   * 方向盘（strg）只有 1 档，用官方位图，不参与档位绘制。
   */
  _paintSeatIcon(btn, kind, lv) {
    if (!btn || kind === "strg") return;
    const n = Math.max(1, Math.min(3, lv || 1));   // 条数/叶数 1~3
    const isHeat = kind === "heat";
    const parts = [];
    if (isHeat) {
      // 竖直 S 曲线，均匀分布
      const xs = n === 1 ? [12] : (n === 2 ? [9, 15] : [7, 12, 17]);
      for (const x of xs) {
        parts.push(`<path d="M${x} 4c-2 1.6-2 3.4 0 5s2 3.4 0 5 2 3.4 0 5"/>`);
      }
    } else {
      // 三叶扇：按数量取 0° / 120° / 240° 的叶片
      const angles = n === 1 ? [0] : (n === 2 ? [0, 120] : [0, 120, 240]);
      parts.push('<circle cx="12" cy="12" r="1.5" class="hub"/>');
      for (const a of angles) {
        parts.push(`<use href="#lxblade" transform="rotate(${a} 12 12)"/>`);
      }
    }
    btn.innerHTML = `<svg viewBox="0 0 24 24" data-lv="${n}">`
      + '<defs><path id="lxblade" d="M12 12 C12 8.5 13 6 15.2 6 C17.6 6 19 7.8 19 9.8 C19 11.6 17.4 12.6 15 12.6 C13.8 12.6 12.8 12.4 12 12 Z"/></defs>'
      + parts.join("") + "</svg>";
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

      <div class="seatbox" id="seatbox">
        <img class="bg" id="seatbg" src="${__seatBase}/seatmap-l6.webp" alt="座椅布局">
        <div class="sbtns" id="sbtns"></div>
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
        <h2>按时出发</h2>
        <div id="scheds"></div>
      </div>

      <div class="notice">
        <img src="${__iconBase}/ic_home_control.webp" onerror="__lxIconFallback(this)" alt="" style="width:17px;height:17px;flex:0 0 auto;margin-top:1px">
        <div><b>按时出发暂不可用。</b>该功能的控制指令走 LiNdn（JOB）通道，集成尚未打通，
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
    const add = () => this._toast("按时出发需在理想 App 内设置（JOB 通道未打通）");
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

  /**
   * ★ 座椅可视化区渲染（2026-10-21 新增，对齐官方空调页）。
   *
   * 三件事：
   *   ① 按车型选底图：5座→seatmap-l6（连体长椅）/ 6座→seatmap-l8（两独立座）
   *      判据沿用集成 `fan.py` 已按能力表生成的实体（有三排实体=6座）
   *   ② 按实体有无渲染按钮：集成已按车型过滤，无实体=该座位不存在
   *   ③ 按钮位置用 SEAT_POS 百分比，缩放不跑位
   *
   * 官方实测：按钮直径 182px = 屏宽 14.4%（即底图宽 14.4%），
   *           加热=三条波浪，通风=三叶扇。
   */
  _renderSeats() {
    const box = this.querySelector("#seatbox");
    const bg = this.querySelector("#seatbg");
    const host = this.querySelector("#sbtns");
    if (!box || !bg || !host) return;

    // —— ① 选底图 ——
    // 集成 fan.py 已按能力表生成实体：6座车才有三排座椅实体
    const is6 = !!(this._eid("seat_tl_heat") || this._eid("seat_tr_heat"));
    const map = is6 ? "seatmap-l8.webp" : "seatmap-l6.webp";
    const want = `${__seatBase}/${map}`;
    if (bg.getAttribute("src") !== want) {
      bg.onerror = () => {
        // /local 缺失 → 回退集成内置
        bg.onerror = null;
        bg.src = `${BUILTIN_SEAT_BASE}/${map}`;
      };
      bg.src = want;
    }

    // —— ② 按钮定义（field 对应 fan.py 的 SEAT_FANS key）——
    const P = SEAT_POS;
    const rear = is6 ? P.rear6 : P.rear5;
    const defs = [];
    /* ★ 2026-10-22 修复（车主："方向盘没有"）：
       bind 的 steer_heat 规则是 {name:"方向盘加热", domain:"switch"}，
       但若该车型 bind 未解析出（或 field 被 config 覆盖成 null），
       方向盘按钮就整个消失 —— 属于"静默缺失"，用户只会看到少一个钮。
       加实体名兜底：bind 拿不到时直接按名称在 hass.states 里找 switch。 */
    const _steer = this._eid("steer_heat") || this._findByFriendly("方向盘加热", "switch");
    if (_steer) {
      defs.push({ k: "strg", pos: P.strg, field: "steer_heat", kind: "strg",
                  title: "方向盘加热", eid: _steer });
    }
    defs.push({ k: "fl_heat", pos: P.front.heatL, field: "seat_fl_heat", kind: "heat", title: "主驾座椅加热" });
    defs.push({ k: "fr_heat", pos: P.front.heatR, field: "seat_fr_heat", kind: "heat", title: "副驾座椅加热" });
    defs.push({ k: "fl_vent", pos: P.front.ventL, field: "seat_fl_vent", kind: "vent", title: "主驾座椅通风" });
    defs.push({ k: "fr_vent", pos: P.front.ventR, field: "seat_fr_vent", kind: "vent", title: "副驾座椅通风" });
    defs.push({ k: "sl_heat", pos: rear.heatL, field: "seat_rl_heat", kind: "heat", title: "二排左座椅加热" });
    if (!is6) defs.push({ k: "sm_heat", pos: rear.heatM, field: "seat_rc_heat", kind: "heat", title: "二排中座椅加热" });
    defs.push({ k: "sr_heat", pos: rear.heatR, field: "seat_rr_heat", kind: "heat", title: "二排右座椅加热" });
    defs.push({ k: "sl_vent", pos: rear.ventL, field: "seat_rl_vent", kind: "vent", title: "二排左座椅通风" });
    defs.push({ k: "sr_vent", pos: rear.ventR, field: "seat_rr_vent", kind: "vent", title: "二排右座椅通风" });

    // —— ③ 渲染（只建一次，后续只更新状态）——
    if (!host.__built) {
      host.innerHTML = "";
      defs.forEach(d => {
        const eid = d.eid || this._eid(d.field);
        if (!eid) return;                       // 该车型无此座位 → 不渲染
        d.eid = eid;                            // 记下，状态同步时复用
        const b = document.createElement("button");
        b.type = "button";
        b.className = "sbtn";
        b.dataset.field = d.field;
        b.dataset.eid = eid;
        b.dataset.kind = d.kind;
        b.style.left = d.pos[0] + "%";
        b.style.top = d.pos[1] + "%";
        b.title = d.title;
        b.setAttribute("aria-label", d.title);
        // 图标：加热=三条波浪 / 通风=三叶扇（官方是这两个符号，APK 无位图→自绘 SVG）
        b.innerHTML = d.kind === "strg"
          /* ★ 2026-10-22：方向盘加热用**官方素材** ic_home_steering_on/off.webp
             （方向盘 + 三条橙色竖直波浪），比自绘 SVG 更准且与 App 一致。 */
          ? `<img src="${__iconBase}/ic_home_steering_on.webp" alt=""
                 onerror="__lxIconFallback(this)" class="strgi">`
          : d.kind === "heat"
          /* ★ 2026-10-22（车主："加热的方向要转90度"）：
             原来画的是**横向**波浪（M4 9c2-2... 水平走向），
             官方是**竖直**的三条 S 曲线（ic_home_steering_on 里那三条橙色波浪）。
             改为竖向：每条从 (x,4) 到 (x,20)，中段左右摆动。 */
          ? '<svg viewBox="0 0 24 24"><path d="M8 4c-2 1.6-2 3.4 0 5s2 3.4 0 5 2 3.4 0 5"/><path d="M12 4c-2 1.6-2 3.4 0 5s2 3.4 0 5 2 3.4 0 5"/><path d="M16 4c-2 1.6-2 3.4 0 5s2 3.4 0 5 2 3.4 0 5"/></svg>'
          /* 通风=三叶风扇（对齐官方）。单片叶子用 rotate(0/120/240) 复制，保证三叶均匀 */
          : '<svg viewBox="0 0 24 24"><defs><path id="lxblade" d="M12 12 C12 8.5 13 6 15.2 6 C17.6 6 19 7.8 19 9.8 C19 11.6 17.4 12.6 15 12.6 C13.8 12.6 12.8 12.4 12 12 Z"/></defs>'
            + '<circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>'
            + '<use href="#lxblade" fill="currentColor" stroke="none"/>'
            + '<use href="#lxblade" transform="rotate(120 12 12)" fill="currentColor" stroke="none"/>'
            + '<use href="#lxblade" transform="rotate(240 12 12)" fill="currentColor" stroke="none"/></svg>';
        // ★ 2026-10-21 实测：座椅实体是 **fan 域**（fan.li_xiang_l6_主驾座椅加热 等 9 个），
        //   bind 里 seat_* 的 domain 也是 "fan" ⇒ 用 set_percentage 控制档位。
        //   （我一度误判为 sensor 只读 —— 实际 sensor 与 fan 同名并存，
        //     bind 取的是 fan，故可直接控制。）
        /* ★ 2026-10-22（车主："交互方式是循环。风速扇叶颜色数量会变化，热风也一样"）
           三档循环：关 → 1档 → 2档 → 3档 → 关
           实体实测 capabilities.preset_modes = ["low","medium","high"]
           → 用 fan.set_preset_mode 控制（turn_off 关闭）。 */
        b.addEventListener("click", async () => {
          const tgt = this._eid(d.field);
          if (!tgt || tgt.indexOf("fan.") !== 0) return;
          const cur = this._seatLevel(tgt);
          try {
            if (cur >= 3) {
              await this._hass.callService("fan", "turn_off", { entity_id: tgt });
            } else {
              /* ★ 2026-10-22 修正：fan 域**没有** set_preset_mode 服务
                 （可用只有 set_percentage / turn_on / turn_off / toggle）。
                 档位通过 percentage 表达：1档33 / 2档66 / 3档100；
                 集成侧 fan.py 会把 percentage 映射回 log/medium/high。 */
              const pct = cur === 0 ? 33 : (cur === 1 ? 66 : 100);
              await this._hass.callService("fan", "set_percentage",
                { entity_id: tgt, percentage: pct });
            }
          } catch (e) {
            this._toast("操作失败：" + ((e && e.message) || "未知"), "err");
          }
        });
        host.appendChild(b);
      });
      host.__built = true;
    }
    // 状态同步
    host.querySelectorAll(".sbtn").forEach(b => {
      const eid = b.dataset.eid || this._eid(b.dataset.field);
      const lv = eid ? this._seatLevel(eid) : 0;
      // 档位 0~3 写到 data-level，CSS 据此着色；图标由 _seatIcon 重绘数量
      b.dataset.level = String(lv);
      b.classList.toggle("on", lv > 0);
      this._paintSeatIcon(b, b.dataset.kind, lv);
    });
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);
    this._renderSeats();

    q("#v-room").textContent = (t => t == null ? "—" : t.toFixed(0) + "°C")(this._num(this._eid("room_temp")));

    // 空气质量（数值越小越好；App 显示"2 优"）
    const aqi = this._num(this._eid("aqi"));
    const aqiEl = q("#v-aqi");
    if (aqi == null) { aqiEl.textContent = "—"; aqiEl.className = "v"; q("#l-aqi").textContent = "空气质量"; }
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
