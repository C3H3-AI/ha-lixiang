
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
 *   · 入口：车辆健康 | 任务大师 / 车辆信息 | 情景模式 / 车辆设置
 *   （★ 2026-10-12 按车主指示移除「服务专家」与「理想AD学习平台」）
 *   · 图标用 _lisa 粗线版
 */

const CARD_TAG = "lixiang-app-home";
const BUILTIN_ICON_BASE = "/lixiang_auto/lixiang-icons";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";   // 用户自定义优先
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
const __iconFallback = BUILTIN_ICON_BASE;

// ★ 2026-10-14 统一导航助手：**先问外壳**（lx-navigate 事件），被接管就不改 URL。
//   背景：外壳（lixiang-app）只能靠猴补丁拦 history.pushState；一旦 HA 路由
//   抢在它前面处理，子卡片内的"返回/入口"会真的切 HA 视图 → 车主反馈
//   「点击都回到首页」。改为显式事件：外壳在则内部切换，不在则回退 HA 路由。
// ═══ ★ 卡片拖拽排序（2026-10-20）══════════════════════════════════
//   目标：允许用户在【卡片内部】拖动 .row2 里的卡片（空调 / 位置 / 里程 /
//        电量 / 哨兵）自由换位，顺序持久化到 localStorage。
//   设计要点：
//     · 只用原生 HTML5 drag & drop，不引第三方库（卡片要尽量轻）。
//     · 【长按 350ms 才进入拖拽】—— 否则会与卡片自身的点击冲突
//       （点空调卡要跳空调页，点位置卡要跳地图页）。
//     · 拖动时给占位提示；松手按新顺序写回 DOM 并保存。
//     · 提供 lxClearOrder()，用户拖乱后可恢复默认。
const LX_DRAG_STORE = "lx_apphome_order";
const LX_DRAG_HOLD_MS = 350;

/** 取当前实例的 localStorage（shadow DOM / 多实例下不依赖全局）。 */
function lxStore(row) {
  try {
    const win = (row && row.ownerDocument && row.ownerDocument.defaultView) || window;
    return win.localStorage || null;
  } catch (e) { return null; }
}

function lxLoadOrder(row) {
  try {
    const st = lxStore(row);
    if (!st) return null;
    const raw = st.getItem(LX_DRAG_STORE);
    if (!raw) return null;
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr) || !arr.length) return null;
    // 兼容旧格式（纯 id 字符串数组）：补 host="" 让重放按"就近"处理
    return arr.map((x) => (typeof x === "string" ? { id: x, host: "" } : x));
  } catch (e) { return null; }
}

function lxSaveOrder(ids, row) {
  try {
    const st = lxStore(row);
    if (!st) return;
    const scope = (row && row.closest(".root")) || row.parentElement;
    const pairs = [];
    const seen = new Set();
    // 当前 row 的卡
    (ids || []).forEach((id) => {
      if (!id || seen.has(id)) return;
      seen.add(id);
      pairs.push({ id, host: row.id || "" });
    });
    // 其它 row2 的卡（跨组拖动的结果要靠这个才能还原）
    if (scope && scope.querySelectorAll) {
      scope.querySelectorAll(".row2").forEach((r) => {
        if (r === row) return;
        r.querySelectorAll(":scope > .card").forEach((c) => {
          if (!c.id || seen.has(c.id)) return;
          seen.add(c.id);
          pairs.push({ id: c.id, host: r.id || "" });
        });
      });
    }
    st.setItem(LX_DRAG_STORE, JSON.stringify(pairs));
  } catch (e) {}
}

function lxClearOrder(row) {
  try {
    const st = lxStore(row);
    if (st) st.removeItem(LX_DRAG_STORE);
  } catch (e) {}
}

/** 按已保存顺序重排某个 .row2 里的卡片；无保存则保持原样。 */
function lxApplyOrder(row) {
  const order = lxLoadOrder(row);
  if (!order || !row) return false;
  const cards = Array.from(row.querySelectorAll(":scope > .card"));
  if (!cards.length) return false;
  const byId = new Map(cards.map((c) => [c.id, c]));
  let touched = false;
  for (const it of order) {
    const el = byId.get(it.id);
    // 必须仍在 DOM 里（车型可能不支持该卡），否则跳过
    if (el) { row.appendChild(el); touched = true; }
  }
  return touched;
}

/**
 * ★ 重放【全局】顺序：把每张卡按保存的顺序分配回它上次所在的 .row2。
 *   需要每张卡记住自己的宿主 row（拖动时写入 data-lx-host）。
 */
function lxApplyGlobalOrder(root) {
  const order = lxLoadOrder(root);
  if (!order || !root) return false;
  const rows = Array.from(root.querySelectorAll(".row2"));
  if (!rows.length) return false;
  const byId = new Map();
  rows.forEach((r) => r.querySelectorAll(":scope > .card")
    .forEach((c) => byId.set(c.id, c)));
  let touched = false;
  for (const it of order) {
    const el = byId.get(it.id);
    if (!el) continue;
    // 有明确宿主就回宿主；没有（旧数据）就留在当前 row
    const host = it.host ? rows.find((r) => r.id === it.host) : null;
    if (host) { host.appendChild(el); touched = true; }
    else if (el.parentElement) { touched = true; }
  }
  return touched;
}

/** 给一个 .row2 容器挂上拖拽能力。 */
function lxEnableDragSort(row) {
  if (!row || row.__lxDrag) return;
  row.__lxDrag = true;
  let holdTimer = null;
  let drag = null;          // { card, x0, y0, dx, dy, placeholder, moved }

  const clearHold = () => {
    if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
  };

  // 拖动中：记录位移（★ 只在已进入拖动模式后才更新，不取消计时）
  const onMove = (ev) => {
    if (!drag) return;
    const dx = ev.clientX - drag.x0;
    const dy = ev.clientY - drag.y0;
    if (!drag.moved) {
      // 超过 6px 才认定为"拖动"（避免轻微抖动误判）
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
      drag.moved = true;
      row.classList.add("lx-drop-active");
    }
    drag.dx = dx;
    drag.dy = dy;
    drag.card.style.transform = `translate(${dx}px, ${dy}px) scale(1.02)`;

    // ★ 找当前悬停的卡（允许跨 .row2 —— 两张卡区间可互换）
    //   ★ 用 row.ownerDocument 而非裸 document：shadow DOM / 多实例下更稳
    const doc = row.ownerDocument || document;
    const over = doc.elementFromPoint(ev.clientX, ev.clientY);
    const card = over && over.closest && over.closest(".card");
    if (!card || card === drag.card) return;
    const host = card.closest(".row2");
    if (!host) return;
    const box = card.getBoundingClientRect();
    const after = (ev.clientX - box.left) > box.width / 2;
    host.insertBefore(drag.card, after ? card.nextSibling : card);
    drag.host = host;
  };

  const onUp = () => {
    clearHold();
    if (!drag) return;
    const card = drag.card;
    const moved = drag.moved;
    // ★★ 拖动过就必须吞掉【随后补发的 click】——
    //   卡片整块可点（点空调卡跳空调页），pointerup 后浏览器会补一个 click，
    //   若不拦就会"松手即跳二级界面"，而且用户以为没拖动成功。
    if (moved) {
      card.__lxSwallowClick = true;
      setTimeout(() => { card.__lxSwallowClick = false; }, 350);
    }
    // 复位视觉
    card.style.transform = "";
    card.classList.remove("lx-dragging");
    row.classList.remove("lx-drop-active");
    card.removeAttribute("draggable");
    drag = null;

    if (moved) {
      const ids = Array.from(row.querySelectorAll(":scope > .card"))
        .map((c) => c.id).filter(Boolean);
      lxSaveOrder(ids, row);
      const scope = row.closest(".root") || row.parentElement;
      if (scope && scope.querySelectorAll) {
        scope.querySelectorAll(".row2").forEach((r) => { if (r !== row) lxApplyOrder(r); });
      }
      try { navigator.vibrate && navigator.vibrate(8); } catch (e) {}
    }
  };

  // ★ click 拦在【捕获阶段】：卡片的跳转逻辑多在冒泡阶段，
  //   捕获阶段先拦掉，比事后 preventDefault 可靠。
  row.addEventListener("click", (ev) => {
    const card = ev.target.closest && ev.target.closest(".card");
    if (card && card.__lxSwallowClick) {
      ev.preventDefault();
      ev.stopPropagation();
    }
  }, true);

  row.addEventListener("pointerdown", (ev) => {
    if (ev.button != null && ev.button !== 0) return;
    const card = ev.target.closest(".card");
    if (!card || !row.contains(card)) return;
    clearHold();
    holdTimer = setTimeout(() => {
      holdTimer = null;
      drag = { card, host: row, x0: ev.clientX, y0: ev.clientY, dx: 0, dy: 0, moved: false };
      card.setAttribute("draggable", "false");   // ★ 禁掉原生拖拽，交给我们自己
      card.style.willChange = "transform";
      // ★ 长按成功【立刻】给视觉反馈 —— 之前只在移动超 6px 后才加类，
      //   用户长按后看不到任何变化，会以为"没反应"（真实用户反馈）。
      card.classList.add("lx-dragging");
      try { navigator.vibrate && navigator.vibrate(12); } catch (e) {}
    }, LX_DRAG_HOLD_MS);
  });

  // ★★ 关键修正：pointermove/up 绑在【window】上
  //    · 拖动时手指可能移出卡片区 → 只有 window 能持续收到事件
  //    · pointermove 不再 clearHold（那会导致永远拖不起来）
  window.addEventListener("pointermove", onMove, { passive: true });
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointercancel", onUp);
}

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

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_bold.ttf");    font-weight:600; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("/lixiang_auto/lixiang-fonts/roboto_medium_numbers.ttf"); font-display:swap; }

  lixiang-app-home { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500; --lx-red:#FF3B30;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2;
    /* ★ 与深色块同名成对 —— 弹窗/toast 跟随主题 */
    --lx-surface:#FFF; --lx-on-surface:#111418;
    --lx-invert-bg:#1b1f27; --lx-invert-fg:#FFF;
    --lx-toast-bg:rgba(0,0,0,.84); --lx-toast-fg:#fff; }
  @media (prefers-color-scheme: dark) {
    lixiang-app-home { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF;
            /* ★ 2026-10-20：补「反转面」变量 —— 弹窗/toast 用。
               硬编码 #fff 在深色下会是刺眼白块（车主可感知）。 */
            --lx-surface:#1C1C1E;      /* 弹窗底（深色下与卡片一致）*/
            --lx-on-surface:#F2F2F7;   /* 弹窗字 */
            --lx-invert-bg:#F2F2F7;    /* 主按钮底（深色下用亮色）*/
            --lx-invert-fg:#1C1C1E;    /* 主按钮字 */
            --lx-toast-bg:rgba(242,242,247,.92);
            --lx-toast-fg:#1C1C1E; }
  }
  /* 2026-10-12：兜底 —— 长内容不得撑破视口（车主："手机上右边溢出"）。
     真正修复是把 grid 列改成 minmax(0,1fr)；这里再加一道保险。
     ★★ 必须 clip，不能 hidden（2026-10-13 实测）：overflow-x:hidden 会把
        overflow-y 计算成 auto → lixiang-app-home/.root 成为滚动容器 → 里面的
        .head{position:sticky} 被困住，「抬头固定」直接失效（滚动后抬头消失）。
        clip 同样裁剪但【不创建滚动容器】。别再改回 hidden。 */
  lixiang-app-home { display:block; max-width:100%; overflow-x:clip; }
  .wrap > *, .row2 > *, .entries > *, .quick > * { min-width:0; }
  .root { container-type:inline-size; background:var(--lx-bg); color:var(--lx-t1); padding-bottom:14px; overflow-x:clip;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif;
    -webkit-tap-highlight-color:transparent; }
  .root[data-theme="light"] { --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; --lx-blue:#0A58F6; }
  .root[data-theme="dark"] { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
    --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }

  /* ★ 2026-10-09（用户要求）：抬头固定 —— 滚动时头部（车型/续航/状态）不再消失。
     · .head 粘顶；粘顶后收紧成单行 + 隐藏缩略 3D，避免固定头部占掉半屏
     · ★★ 避让 HA 顶栏：HA 的顶栏是 position:fixed 覆盖在内容之上的
       （窄屏尤其明显，内容会滑到顶栏下面）。若只写 top:0，我们的抬头会
       **被 HA 顶栏盖住**（用户反馈："抬头还是会被遮挡"）。
       所以粘顶位置取 --lx-head-top，由 JS 按实测布局算出：
         · 滚动容器顶边在视口顶端（=顶栏覆盖式布局）→ 需要避让 --header-height
         · 顶栏被 HA 自动隐藏时（窄屏下滚）→ 归零，否则会留一条空白
         · 滚动容器顶边已在顶栏之下（桌面布局）→ 归零，不需要避让 */
  .head { position:sticky; top:var(--lx-head-top, 0px); z-index:30; background:var(--lx-bg);
          padding:8px 20px 0;
          transition:top .18s ease, box-shadow .2s, padding .2s, background .2s; }
  .root.stuck .head { padding-bottom:8px; border-bottom:1px solid var(--lx-line);
          box-shadow:0 6px 16px rgba(0,0,0,.06); }
  .root.stuck .head .hrow { align-items:center; }
    /* ★ 2026-10-13：这里原为 baseline —— 与右侧 96px 高的小车图同排时，
       基线对齐会把标题压到小车图底边（左上留一大块空白，看着像被遮挡）。
       标题/续航之间的基线对齐由 .hleft 自己负责，这一层用 center。 */
  .root.stuck .head .hleft { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
  .root.stuck .head .title { font-size:18px; line-height:1.25; }
  .root.stuck .head .ranges { margin-top:0; gap:10px; }
  .root.stuck .head .parked { margin-top:0; font-size:12px; }
  /* 插枪徽标（插电时显示） */
  /* ★ 头部徽标：告警（琥珀）/ 哨兵（蓝） */
  .badge { display:inline-flex; align-items:center; gap:3px; margin-left:6px;
           vertical-align:middle; font-size:11px; padding:2px 7px; border-radius:8px; }
  .badge img { width:12px; height:12px; }
  .badge.warn { color:#8A5300; background:rgba(232,163,60,.16); }
  .badge-sentry { color:#0A58F6; background:rgba(10,88,246,.10); }
  /* ★ 地图卡拍照按钮（官方 HomeControlMapPhoto） */
  .loc .map .shot { position:absolute; right:8px; top:50%; transform:translateY(-50%);
                    width:34px; height:34px; border-radius:50%; background:#fff; border:0;
                    display:flex; align-items:center; justify-content:center; cursor:pointer;
                    box-shadow:0 2px 8px rgba(16,20,28,.2); padding:0; }
  .loc .map .shot img { width:18px; height:18px; }
  /* ★ 空调卡座椅插图（官方布局：右下角、不抢文字） */
  .ac .seatart { position:absolute; right:-6px; bottom:-10px; width:104px; height:110px;
                      opacity:.9; pointer-events:none; }
  .plug { display:inline-flex; align-items:center; gap:3px; margin-left:8px;
          vertical-align:middle; font-size:11px; padding:2px 7px; border-radius:8px;
          color:#0A7B3E; background:rgba(10,123,62,.10); }
  .plug img { width:12px; height:12px; display:block; }
  .plug b { font-weight:500; }
  [data-theme="dark"] .plug { color:#30D158; background:rgba(48,209,88,.14); }
  /* ★★ 2026-10-12 删除 '.root.stuck .head .mini { display:none }'：
     它与「上滑收起成大图旁边的小图」的设计**直接冲突**，而且优先级更高
     （3 个类 vs '.root.collapsed3d .mini' 只有 2 个类）——
     结果是**一滚动小图就消失**，车主反馈「标题抬头固定做的不是很好」。
     现在粘顶时保留小图（这才是 App 的行为）。 */
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
  .root.expanded3d .big3d { height:270px; opacity:1; }
  .root.expanded3d { --lx-3d-h: 260px; }
  .big3d iframe { width:100%; height:100%; border:0; display:block; }
  .big3d, .big3d iframe { touch-action:none; }
  /* ★ 2026-10-14：车图缩到 84% 宽、居中 → 两侧各有约 8% 留白，
     胎压标签放进留白里（车主："胎压还在车子上"）。 */
  /* 必须 display:block —— 否则 img 是行内元素，margin:auto 不居中（实测左侧 0 留白） */
  .big3d img { display:block; width:84%; margin:0 auto; height:100%; object-fit:contain; object-position:50% 62%; }

  /* minmax(0,1fr)：裸 1fr 的默认 min-width:auto 会让长内容撑破容器 → 手机右侧溢出 */
  .quick { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:6px;
           padding:18px 12px 0; }
  /* ★ 车型无快捷功能时的空态（2026-10-11） */
  .qempty { grid-column:1/-1; padding:22px 10px; text-align:center;
            color:var(--lx-t3,#9A9A9A); font-size:13px; }
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
  /* ★ 2026-10-14 官方同款：激活 = 实心深色圆（配官方白色 *_on_* 图标）；
     未激活 = 空心圆（配深色线稿图标）。原来是"蓝圈+浅蓝底"，与官方不一致。 */
  .q.on .c { border-color:#1b1f27; background:#1b1f27; box-shadow:0 2px 10px rgba(16,20,28,.22); }
  .q.on .n { color:#111418; font-weight:600; }
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
  /* ★ 2026-10-16 车主（两次澄清后定稿）：
       「小箭头不是收齐车模的功能，是展开和收齐快捷键的功能。
         比如有车可能有 8 个快捷，那么小箭头就可以展开更多。
         车模是上滑收起，下拉展开。」
     → 默认只显示**第一行 4 个**快捷键；按小箭头展开「更多」（全部可用项），
       再按收起。车模完全不归它管 —— 车模只由滚动（上滑收起/下拉展开）驱动；
       右上角小车图是车模自己的开关。
     → 可用项 ≤4 时箭头无意义，_renderQuick 里会把它藏起来。 */
  .root:not(.quick-open) .quick > .q:nth-child(n+5) { display:none; }
  .root.quick-open .chev img { transform:rotate(180deg); }

  .wrap { padding:12px 20px 0; display:grid; gap:12px; }
  .row2 { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
  .card { background:var(--lx-card); border-radius:18px; padding:16px;
          cursor:pointer; transition:transform .13s, box-shadow .18s; position:relative; }
  .card:hover { box-shadow:0 3px 14px rgba(0,0,0,.07); }
  .card:active { transform:scale(.985); }
  .card:focus-visible { outline:2px solid var(--lx-blue); outline-offset:2px; }
  .card .lbl { font-size:13px; color:var(--lx-t3); }
  /* ★ 2026-10-12：卡片高度对齐 App。
     从车主截图量得：温度卡/位置卡约 180x183（**近正方形**）、里程卡约 180x213。
     此前写死 150px → 卡片偏扁（比 App 矮约 20%）。改用 clamp 随视口缩放，
     窄屏不过高、宽屏不过矮。 */
  .ac { min-height:clamp(168px, 46vw, 200px); display:flex; flex-direction:column;
        justify-content:space-between; 
             position:relative; overflow:hidden; }
  .ac .temp { font-family:"LxNum"; font-size:30px; font-weight:600; line-height:1.1; }
  .ac .temp sup { font-size:15px; font-weight:500; }
  .ac .target { font-size:11.5px; color:var(--lx-t3); margin-top:3px; }
  /* 风扇：右上角标（不占布局空间）*/
  .ac .fan { position:absolute; right:14px; top:14px; width:34px; height:34px;
             border-radius:50%; background:var(--lx-bg); display:flex;
             align-items:center; justify-content:center;
             box-shadow:0 1px 4px rgba(0,0,0,.06); }
  .ac .fan img { width:18px; height:18px; }
  /* ★ 2026-10-14 官方同款：空调开启时风扇 **蓝底 + 白图标 + 转动**。
     官方资源本就是配套的：ic_home_fan_off = 深灰(浅底)、ic_home_fan_on = 纯白(蓝底)。 */
  .ac .fan.on { background:var(--lx-blue); box-shadow:0 2px 10px rgba(10,88,246,.35); }
  .ac .fan.on img { animation:spin 1.6s linear infinite; }
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
  .loc { min-height:clamp(168px, 46vw, 200px); display:flex; flex-direction:column;
         overflow:hidden; }
  .loc .map { flex:1; border-radius:12px; background:#E8EEF4; overflow:hidden;
              position:relative; min-height:clamp(96px, 26vw, 120px); }
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
  /* 里程卡比上排略高（App 约 213px）—— 右列是「电量 + 哨兵」两张堆叠 */
  .mile { min-height:clamp(196px, 54vw, 232px); }
  .mile .big { font-family:"LxNum","Licium"; font-size:30px; font-weight:600; line-height:1.1; }
  .mile .big small { font-size:14px; font-weight:500; color:var(--lx-t2); margin-left:3px; }
  .mile .cap { font-size:13px; color:var(--lx-t3); margin-top:4px; }
  .mile .chart { margin-top:10px; height:46px; position:relative; }
  .mile .chart::after { content:""; position:absolute; left:0; right:0; bottom:0;
                        height:1px; background:var(--lx-line); }
  .mile .chart svg { width:100%; height:100%; display:block; }
  /* ★ 柱状图（对齐 App）：每个数据点一根等宽柱子 */
  #sparkbars rect { fill:#9A9AA0; }
  #sparkbars rect[data-zero] { fill:transparent; }     /* 0 值不画柱子（不留脏点） */
  #sparkgrid line { stroke:var(--lx-line); stroke-width:0.4; }
  .mile .axis { display:flex; justify-content:space-between; font-size:10px;
                color:var(--lx-t3); margin-top:3px; }
  .batt .row { display:flex; align-items:center; gap:9px; }
  /* 充电中的剩余时间（App 同款：小字 + 闪电） */
  .batt .batt-remain { display:flex; align-items:center; gap:4px; margin-top:6px;
                       font-size:12px; color:var(--lx-t2); }
  .batt .batt-remain .ic { font-size:11px; }
  .batt .row img { width:26px; height:26px; }
  .batt .big { font-family:"LxNum","Licium"; font-size:28px; font-weight:600; line-height:1.05; }
  .batt .big small { font-size:15px; font-weight:500; color:var(--lx-t2); }
  .sentry { display:flex; align-items:center; gap:12px; min-height:76px; }
  .sentry img { width:26px; height:26px; }
  .sentry .t { font-size:15px; }
  .sentry .s { font-size:12px; color:var(--lx-t3); margin-top:3px; }
  .sentry.on .t { color:var(--lx-blue); }

  .entries { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
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
  .divider { height:1px; background:var(--lx-line); margin:16px 0; }

  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:var(--lx-toast-bg); color:var(--lx-toast-fg); font-size:13px; padding:10px 18px;
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
  /* ★ 2026-10-14：胎压叠在车图四个轮子旁（车主要求）。
     位置由 JS 按"车图实际渲染区域"计算（见 _layoutTires），不用百分比硬套盒子，
     因为车图是 object-fit:contain + object-position:50% 62%，并不铺满盒子。 */
  .big3d .tires { position:absolute; inset:0; pointer-events:none; }
  .big3d .tp { position:absolute; transform:translate(-50%,-50%); padding:1px 5px;
               border-radius:8px; background:#0d1828cc; border:1px solid #ffffff1f;
               font-size:11px; font-weight:600; color:#eaf1fb; white-space:nowrap; }
  /* ★ 官方同款二次确认弹框 */
  .cfm { position:fixed; inset:0; z-index:99; background:rgba(16,20,28,.45);
         display:flex; align-items:center; justify-content:center; padding:24px; }
  .cfm-box { width:100%; max-width:340px; background:var(--lx-surface); border-radius:20px;
             padding:24px 20px 16px; box-shadow:0 18px 50px rgba(10,14,22,.28); }
  .cfm-text { font-size:16px; line-height:1.55; color:var(--lx-on-surface); text-align:center; font-weight:500; }
  .cfm-row { display:flex; gap:12px; margin-top:22px; }
  .cfm-row button { flex:1; height:46px; border-radius:23px; font-size:16px; font-weight:600;
                    border:1px solid var(--lx-line); background:var(--lx-surface); color:var(--lx-on-surface); cursor:pointer; }
  .cfm-row .cfm-yes { background:var(--lx-invert-bg); border-color:var(--lx-invert-bg); color:var(--lx-invert-fg); }
  .cfm-rem { display:flex; align-items:center; justify-content:center; gap:6px;
             margin-top:14px; font-size:13px; color:#6b7480; }
  .big3d .tp small { font-size:9px; font-weight:400; opacity:.75; margin-left:1px; }
  .big3d .tp.low { background:#4a3410cc; border-color:#e8b96b55; color:#f2c98a; }
  .big3d .ph .spin2 { width:22px; height:22px; border-radius:50%;
               border:2.5px solid rgba(10,88,246,.18); border-top-color:var(--lx-blue);
               animation:spin .8s linear infinite; }

    /* ── 手机断点（≤480px，容器查询）──────────────────────────────
       ★ 2026-10-14：v1.5.7 的提交说明声称加过这段，但 diff 里只改了 11 张
         页面卡，app-home **从未真正加上** —— 断点一直不存在。
         同时 container-type 必须挂在 .root（真实元素）上：
         light DOM 里写在 lixiang-app-home 上的 container-type 不生效，容器查询不会触发。 */
    @container (max-width: 480px) {
      /* ★ 2026-10-14 车主："为什么下面是一列了？"
         官方在手机宽度：下方两张卡**并排**、入口瓦片**一行两个**、
         快捷按钮**一行 4 个**。原来这里把 .row2/.entries 收成一列是我定错了。
         全部移除，只在极窄（≤330px）才收。 */
      .head { padding-left:14px; padding-right:14px; }
      .wrap { padding-left:14px; padding-right:14px; }
      /* ★ 2026-10-16 车主（截图）：「车模都右上角了，中间车模地方空着了，没收起来」
         原来是 ".big3d, .root.expanded3d .big3d { height:188px }" —— 裸 .big3d
         把收起态的 height:0 盖掉了，于是收起后仍占 188px 空白。
         收起态就该完全塌陷，所以这里只留展开态选择器。 */
      .root.expanded3d .big3d { height: 188px; }
      .mini { width:118px; height:78px; }
    }

    /* ★ 2026-10-14：快捷键只在**很窄**时才收成 2 列。
       原来写在 ≤480px 里 —— 容器查询修好后（v1.5.10）它在 460~490px 的
       desktop 栏里也命中，车主反馈"一行只有 2 个"。App 本体在 420pt 仍是 4 列，
       所以阈值下调到 400px（约等于手机竖屏可用宽度以下）。 */
      /* ★ 2026-10-20：330px → 340px（按官方截图对齐，18px 余量）
         维护者反馈「其他用户是一列，我们是两列」。
         最强证据 = 官方 App 手机宽度实测（容器 ≈358px）：
         快捷 4 个 / 两卡并排 / 瓦片 2 个 —— 全部保持多列。
         而旧阈值 330px【本该低于 358px】却仍让 358 落在阈值之下，
         于是 .quick 收 2 列、.row2 收 1 列 ⇒ 看起来「一列」。
         ⇒ 340px 保证 358px 宽度不命中，与官方一致。 */
    /* ── ★ 卡片拖拽排序（2026-10-20）────────────────────────────
       长按 350ms 抓起某张卡 → 拖到目标位置松手 → 顺序保存。
       · .lx-dragging  被拖起的卡：半透明 + 抬起阴影（跟手）
       · .lx-dragover  悬停位置：插入线提示（比方块更轻，不遮挡内容） */
    .card.lx-dragging {
      opacity:.72; transform:scale(.985);
      filter:drop-shadow(0 6px 16px rgba(0,0,0,.22));
      cursor:grabbing;
    }
    .card.lx-dragging * { pointer-events:none; }
    /* 拖拽中的插入提示线 */
    .row2.lx-drop-active { position:relative; }
    .row2.lx-drop-active::after {
      content:""; position:absolute; inset:0; pointer-events:none;
      outline:2px dashed rgba(0,114,255,.35); outline-offset:2px;
      border-radius:12px;
    }
    /* 触屏上禁止长按选中/放大镜，否则会跟拖拽打架 */
    .row2 > .card { -webkit-user-select:none; user-select:none;
                    -webkit-touch-callout:none; }

    @container (max-width: 340px) {
      .quick { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .row2 { grid-template-columns: minmax(0,1fr); }
      .entries { grid-template-columns: minmax(0,1fr); }
    }
`;

// ★ 2026-10-11 车型适配：QUICK 是数据表，但**不再无条件全部渲染** ——
//   渲染前先问 _supports(it)：该功能对应的实体在这台车上不存在 → 整块不显示。
//   理由：之前不支持的车也会出现入口，点了只提示"该功能尚未接入"（体验差，
//   而且用户会以为集成坏了）。实体存在性由**服务端能力门控**决定，不是前端猜车型。
const QUICK = [
  // ★ 2026-10-14 车主（两次澄清）：
  //   1) "所有的按键变化都是这样的" → 2) "我说的是空心圆和实心圆的变化"。
  //   即状态用**圆圈**表达：未激活 = 空心圆 + 深色线稿图标；
  //   激活 = **实心深色圆** + 白色图标（官方图资本来就是配套的：
  //   *_off_* 是深色线稿、*_on_* 是纯白，正好配实心圆）。
  //   标签默认保持动作名；仅官方截图已证实的「授权驾驶 → 已授权」带 onName。
  { key:"lock",   name:"车锁",   off:"ic_home_lock_off_lisa.png",      on:"ic_home_lock_open_lisa.png" },
  { key:"window", name:"车窗",   off:"ic_home_window_off_lisa.png",    on:"ic_home_window_on_lisa.png" },
  { key:"trunk",  name:"尾门",   off:"ic_home_tail_w_off_2025.png",    on:"ic_home_tail_w_on_2025.png" },
  // ★ 2026-10-09：授权驾驶是【动作】（button，cmdKey=remoteVehAuth），
  //   可执行实体与状态显示实体分开：auth=动作，stateField=授权状态。
  // ★ 2026-10-14 对照官方 App「车控」页截图修正：
  //   官方在这里的按钮是 8 个（4×2），第 4 个在**已授权**时标签变成「已授权」+ 实心黑圆。
  //   也就是说：状态**要**显示，但**标签必须跟着变** —— 只高亮而不改标签，
  //   用户看到的就是"授权驾驶一直开着"（车主的疑问）。
  // 官方 I18N（VehicleHomeControl）：authorization=授权驾驶 / alreadyAuthorization=已授权 /
  // alreadyStart=已启动 / dismiss=不再提醒 → 授权按钮有**两态**且动作前要**二次确认**。
  // ★ 2026-10-17 车主：「已授权怎么一直显示？app 上显示是授权驾驶」
  //   根因：我们用 `Vehicle.Provision.Authorize.State`（binary_sensor.车辆授权）
  //   当"是否已授权"的依据 —— 那个是**这台车与账号的绑定关系，长期为 on**，
  //   于是标签永远变「已授权」。
  //   官方包证据：它用的是 **LXVehicleBLEConnectState**（'bleConnected'/
  //   'bleConnectionStatus'，共 55/78 处引用）—— **蓝牙连接状态**，一次性的，
  //   下车/断连就失效；我们集成**没有** BLE 信号，无法复现。
  //   → 拿不到真实依据就不假装有：去掉 onName，始终显示官方动作名「授权驾驶」。
  //   （点击下发不受影响 —— 它本来就是动作按钮 remoteVehAuth。）
  //   同样去掉 stateField（原本指向 binary_sensor.车辆授权）：没有真实 BLE 依据时
  //   **连圆点也不该常亮**（官方只有 bleConnected 为真才高亮）。
  { key:"auth",   name:"授权驾驶", startedName:"已启动",
    confirm:"请在 2 分钟内上车并踩下刹车踏板，下车后请远程上锁。",
    remember:true,
    off:"ic_home_authorization_off_lisa.png",  on:"ic_home_authorization_on_lisa.png" },
  { key:"summon", name:"直线召唤", unsupported:true, note:"命令走 JOB 通道，HTTP 不可达",
    off:"ic_home_parkingout_off_lisa.png",     on:"ic_home_parkingout_on_lisa.png" },
  { key:"find",   name:"寻车",       off:"ic_summon_lisa.png",                  on:"ic_summon_lisa.png" },
  // optimMs：充电盖开合需数秒、状态回读慢 → 乐观值多留一会儿
  { key:"port",   name:"充电口盖", optimMs:12000,
    off:"ic_home_chrgporlid_off_lisa.png",     on:"ic_home_chrgporlid_on_lisa.png" },
  // optimMs：后视镜加热是 App 侧 660s 长命令，VSS 回读更慢
  { key:"mirror", name:"后视镜加热", optimMs:60000,
    off:"ic_home_rearmirroheat_off_lisa.png",  on:"ic_home_rearmirroheat_on_lisa.png" },
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
   * 该快捷功能在这台车上是否可用（车型适配的第一道门）。
   * ★ 判据 = **实体是否真实存在**（服务端已按车型能力门控），
   *   前端不猜车型、不维护车型→功能的映射表。
   * @param {boolean} warmup 首帧可能还没拿到全部实体 → 放宽，避免闪烁
   */
  _supports(def, warmup) {
    // 明确标注"集成暂未支持"的（如直线召唤走 JOB 通道）→ 不显示，
    // 避免给用户一个必然失败的入口。
    if (def.unsupported) return false;
    const eid = this._eidIn("quick", def.key);
    if (!eid) return false;
    if (this._st(eid)) return true;
    // 首帧/刷新瞬间实体表可能未就绪：只要配置里**声明过**就先渲染，等回读再隐藏
    if (warmup) {
      const cfgMap = (this._config || {}).quick || {};
      return typeof cfgMap[def.key] === "string" || !!(cfgMap[def.key] || {}).entity;
    }
    return false;
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
    if (this._scrollCleanups) {
      for (const fn of this._scrollCleanups) { try { fn(); } catch (e) {} }
      this._scrollCleanups = null;
    }
    if (this._cleanupScroll) { this._cleanupScroll(); this._cleanupScroll = null; }
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
  }

  /** 当前滚动量。
   *  ★ 2026-10-09：HA 里滚动常常发生在【外层容器】而不是文档
   *  （此时 window.scrollY 恒为 0）——所以优先读 scroll 事件目标的 scrollTop。
   *  scroll 不冒泡，但带 capture 的监听能收到子容器的 scroll 事件。 */
  _scrollTopOf(ev) {
    const t = ev && ev.target;
    if (t && t.nodeType === 1 && typeof t.scrollTop === "number") return t.scrollTop;
    return window.scrollY || document.documentElement.scrollTop || 0;
  }

  /** 真正的滚动祖先（没有则返回文档滚动元素）。 */
  _scrollRoot() {
    let n = this.parentElement || (this.getRootNode && this.getRootNode().host) || null;
    while (n && n.nodeType === 1) {
      const cs = getComputedStyle(n);
      if (/(auto|scroll|overlay)/.test(cs.overflowY) && n.scrollHeight > n.clientHeight + 2) return n;
      n = n.parentElement || (n.getRootNode && n.getRootNode().host) || null;
    }
    return document.scrollingElement || document.documentElement;
  }

  /** 抬头粘顶位置（px）—— 避开 HA 固定顶栏。
   *
   *  HA 的顶栏（`app-header`）是 position:fixed 覆盖在内容之上，高度由
   *  `--header-height` 给出（实测 56px）。两种布局：
   *    · 覆盖式（窄屏/移动端）：滚动容器顶边 = 视口顶端（0）
   *      → 抬头若只写 top:0 会被顶栏盖住（用户实测："抬头被遮挡"）→ 下移一个顶栏高度
   *    · 预留式（宽屏桌面）：滚动容器顶边已在顶栏之下（≈56）
   *      → 它的 top:0 本来就等于顶栏底边 → 不能下移，否则会露出空白
   *  两种情形用「滚动容器顶边 vs --header-height」自动区分，不用猜屏宽。
   */
  _headTopOffset() {
    try {
      const docEl = document.documentElement;
      const hh = parseFloat(getComputedStyle(docEl).getPropertyValue("--header-height")) || 0;
      if (!hh) return 0;                                     // 非 HA 环境（如卡片预览）不避让
      const sc = this._scrollRoot();
      const isDoc = !sc || sc === docEl || sc === document.body ||
                    sc === document.scrollingElement;
      const scTop = isDoc ? 0 : Math.round(sc.getBoundingClientRect().top);
      return scTop < hh - 2 ? Math.round(hh) : 0;            // 覆盖式才避让
    } catch (e) {
      return 0;
    }
  }

  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
  _num(id) {
    const s = this._st(id);
    if (!s || ["unknown","unavailable"].includes(s.state)) return null;
    const n = parseFloat(s.state); return isNaN(n) ? null : n;
  }
  _txt(id) { const s = this._st(id); return (s && !["unknown","unavailable"].includes(s.state)) ? s.state : null; }
  /**
   * 实体是否处于"开"状态。
   * ★ 2026-10-14 修复（车主："授权驾驶为什么一直显示开着"）：
   *   原实现 `["…","1"].some(x => v.includes(x))` 会把**任何含 1 的状态**判成开 ——
   *   button 实体的状态是时间戳（如 2026-10-14T07:14:35+00:00，含 "1"），
   *   于是「授权驾驶」永远显示为开着。
   *   现在：先排掉明确的"关"、动作型实体（button）与时间戳状态，再做包含判断。
   */
  _on(id) {
    const s = this._st(id);
    if (!s) return false;
    const v = String(s.state == null ? "" : s.state).trim().toLowerCase();
    if (!v) return false;
    // 明确的"关/无效"值
    if (["off","closed","0","false","no","none","unknown","unavailable","idle","standby"].includes(v)) return false;
    // 动作型实体没有开/关语义（状态是"最后一次动作时间"）
    if (String(id).split(".")[0] === "button") return false;
    if (/^\d{4}-\d{2}-\d{2}t/.test(v)) return false;              // 时间戳状态
    if (v === "1") return true;                                      // 精确的 1 才算开
    // climate 域没有 "on" 状态：cool/heat/auto/dry/fan_only 都算"开着"
    if (["cool", "heat", "heat_cool", "auto", "dry", "fan_only"].includes(v)) return true;
    return ["on","open","opening","unlocked","locked","home","playing","true","yes","detected",
            "开启","已开启","已锁定","已连接","已解锁","在线"].some((x) => v.includes(x));
  }
  _online() {
    const s = this._st(this._config.online); if (!s) return true;
    return !["离线","off","unavailable","unknown"].some(v => String(s.state).includes(v));
  }
  /** 二次确认弹框（官方样式：白卡 + 取消/确定 + 不再提醒）。resolve {ok, remember} */
  _confirm(opts) {
    return new Promise((resolve) => {
      const old = this.querySelector(".cfm"); if (old) old.remove();
      const d = document.createElement("div");
      d.className = "cfm";
      d.innerHTML = `<div class="cfm-box" role="dialog" aria-modal="true">
          <div class="cfm-text">${opts.text}</div>
          <div class="cfm-row">
            <button type="button" class="cfm-no">取消</button>
            <button type="button" class="cfm-yes">确定</button>
          </div>
          ${opts.remember ? '<label class="cfm-rem"><input type="checkbox">不再提醒</label>' : ""}
        </div>`;
      this.appendChild(d);
      const box = d.querySelector(".cfm-rem input");
      const done = (ok) => {
        const remember = !!(box && box.checked);
        d.remove();
        resolve({ ok, remember });
      };
      d.querySelector(".cfm-no").addEventListener("click", () => done(false));
      d.querySelector(".cfm-yes").addEventListener("click", () => done(true));
      d.addEventListener("click", (e) => { if (e.target === d) done(false); });
      const y = d.querySelector(".cfm-yes"); if (y && y.focus) y.focus();
    });
  }

  /** 「不再提醒」是否已勾选并记住 */
  _noAsk(key) {
    try { return localStorage.getItem("lx_noask_" + key) === "1"; } catch (e) { return false; }
  }
  _setNoAsk(key, on) {
    try { on ? localStorage.setItem("lx_noask_" + key, "1") : localStorage.removeItem("lx_noask_" + key); } catch (e) { /* 隐私模式禁用存储 */ }
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
              <span class="rg"><img src="${__iconBase}/ic_home_electricity.webp" onerror="__lxIconFallback(this)" alt="">
                <span class="v" id="v-range">—</span><span class="u">km</span>
                <span class="v" id="v-soc" style="margin-left:6px">—</span><span class="u">%</span></span>
              <span class="rg" id="rg-fuel"><img src="${__iconBase}/ic_home_oil.webp" onerror="__lxIconFallback(this)" alt="">
                <span class="v" id="v-fuel">—</span><span class="u">km</span></span>
            </div>
            <div class="parked" id="v-status">—</div>
            <!-- ★ 2026-10-12：插电标识。App 在【插枪时】才显示充电桩
                 （车主两次截图对比确认）；我们用徽标表达同一信息，
                 且放在头部 —— 3D 展开/收起都能看到。 -->
            <span class="plug" id="v-plug" style="display:none" role="status">
              <img src="${__iconBase}/icon_charge_lighting.webp" alt="" onerror="this.style.display='none'">
              <b id="v-plug-t">充电枪已插入</b>
            </span>
            <!-- ★ 2026-10-14 对齐官方顶部徽标（HomeControlHeaderWarning / HeaderSentry） -->
            <span class="badge warn" id="v-badge-warn" style="display:none" role="status">
              <img src="${__iconBase}/src_assets_images_vehicle_header_ic_home_warning.png" alt="" onerror="this.style.display='none'">
              <b id="v-badge-warn-t">告警</b>
            </span>
            <span class="badge badge-sentry" id="v-badge-sentry" style="display:none" role="status">
              <img src="${__iconBase}/src_assets_images_vehicle_header_ic_home_sentry.png" alt="" onerror="this.style.display='none'">
              <b>哨兵</b>
            </span>
          </div>
          <div class="mini" id="mini" role="button" tabindex="0" aria-label="展开车辆 3D"></div>
        </div>
      </div>
      <div class="lowbat" id="lowbat" style="display:none" role="alert" aria-live="polite">
        <img src="${__iconBase}/ic_home_battery.webp" onerror="__lxIconFallback(this)" alt="">
        <span id="lowbat-t"></span>
      </div>
      <div class="big3d" id="big3d">
        <div class="ph" id="b3ph"><div class="spin2"></div><div>车辆 3D 加载中…</div></div>
        <div class="tires" id="tires" style="display:none">
          <div class="tp" data-k="lf"></div><div class="tp" data-k="rf"></div>
          <div class="tp" data-k="lr"></div><div class="tp" data-k="rr"></div>
        </div>
      </div>
      <div class="quick" id="quick" role="group" aria-label="快捷操作"></div>
      <div class="chev" id="chev" role="button" tabindex="0" aria-expanded="false" aria-label="展开更多快捷按键">
        <img src="${__iconBase}/ic_home_pulldown.png" onerror="__lxIconFallback(this)" alt="">
      </div>
      <div class="wrap">
        <div class="row2">
          <div class="card ac" id="c-ac" role="button" tabindex="0">
            <!-- ★ 2026-10-14 对齐官方：空调卡右下角的座椅插图（官方包内无可复用位图，自绘 SVG） -->
            <svg class="seatart" viewBox="0 0 120 128" aria-hidden="true">
              <defs><linearGradient id="lxseat" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#e9edf3"/></linearGradient></defs>
              <path d="M34 12h30c7 0 12 6 12 13l-3 44H37l-3-44c0-7 5-13 12-13z" fill="url(#lxseat)" stroke="#d7dde6" stroke-width="1"/>
              <rect x="30" y="72" width="58" height="14" rx="7" fill="url(#lxseat)" stroke="#d7dde6" stroke-width="1"/>
              <path d="M28 92h62c4 0 7 3 7 7v14c0 4-3 7-7 7H28c-4 0-7-3-7-7v-14c0-4 3-7 7-7z" fill="url(#lxseat)" stroke="#d7dde6" stroke-width="1"/>
              <rect x="40" y="20" width="18" height="4" rx="2" fill="#dde3ea"/>
              <rect x="40" y="30" width="18" height="4" rx="2" fill="#dde3ea"/>
              <rect x="40" y="40" width="18" height="4" rx="2" fill="#dde3ea"/>
            </svg>
            <div class="temp"><span id="v-room">—</span><sup>°C</sup></div>
            <div class="target">目标温度 <span id="v-target">—</span>°C</div>
            <div class="acrow" id="acrow">
              <span class="chip" id="ch-seat"><img src="${__iconBase}/ic_home_seat_heating3.webp" alt="" onerror="this.style.visibility='hidden'"><b id="ch-seat-t">座椅加热</b></span>
              <span class="chip" id="ch-fan"><img src="${__iconBase}/ic_home_fan_on.webp" onerror="__lxIconFallback(this)" alt=""><b id="ch-fan-t">吹风</b></span>
              <span class="chip" id="ch-defrost"><img src="${__iconBase}/ic_home_ice_cool.webp" onerror="__lxIconFallback(this)" alt=""><b id="ch-defrost-t">除雪除霜</b></span>
            </div>
            <div class="fan" id="fan"><img src="${__iconBase}/ic_home_fan_off.webp" onerror="__lxIconFallback(this)" alt=""></div>
          </div>
          <div class="card loc" id="c-loc" role="button" tabindex="0">
            <div class="map" id="map">
              <div class="tiles" id="hm-tiles"></div>
              <div class="puck" id="hm-puck" style="display:none">
                <img src="${__iconBase}/icon_car_loc.webp" onerror="__lxIconFallback(this)" alt="车辆位置"></div>
              <!-- ★ 2026-10-14 对齐官方 HomeControlMapPhoto：地图卡上的拍照按钮 -->
              <button type="button" class="shot" id="hm-shot" aria-label="远程拍照" style="display:none">
                <img src="${__iconBase}/ic_home_photo.png" onerror="__lxIconFallback(this)" alt="">
              </button>
            </div>
            <div class="addr"><img src="${__iconBase}/icon_vehicle_my_location.webp" alt="" onerror="this.style.display='none'">
              <span id="v-addr">定位获取中…</span></div>
          </div>
        </div>
        <div class="row2">
          <div class="card mile" id="c-mile" role="button" tabindex="0">
            <div class="big"><span id="v-mile">—</span><small>km</small></div>
            <div class="cap">本月陪伴里程</div>
            <!-- ★ 2026-10-12：折线 → 柱状图（对齐 App —— 车主截图里是柱状图 + 网格线） -->
            <div class="chart"><svg id="spark" viewBox="0 0 100 40" preserveAspectRatio="none">
              <g class="grid" id="sparkgrid" aria-hidden="true">
                <line x1="0" y1="10" x2="100" y2="10"></line>
                <line x1="0" y1="22" x2="100" y2="22"></line>
                <line x1="0" y1="34" x2="100" y2="34"></line>
              </g>
              <g id="sparkbars"></g></svg></div>
            <div class="axis"><span>01</span><span>08</span><span>15</span><span>22</span><span>29</span></div>
          </div>
          <div style="display:grid; gap:12px; grid-template-rows:1fr auto;">
            <div class="card batt" id="c-batt" role="button" tabindex="0">
              <div class="row"><img src="${__iconBase}/ic_home_battery.webp" onerror="__lxIconFallback(this)" alt="">
                <div><div class="big"><span id="v-batt">—</span><small>%</small></div>
                <div class="lbl" style="margin-top:2px">剩余电量</div></div></div>
              <!-- ★ 2026-10-11：充电中显示剩余时间（对齐 App「剩余2小时25分钟」）。
                   非充电态隐藏。数据源：charge_remain_time（ChargeSurplusTime/min） -->
              <div class="batt-remain" id="batt-remain" style="display:none">
                <span class="ic">⚡</span><span id="v-remain">—</span>
              </div>
            </div>
            <div class="card sentry" id="c-sentry" role="button" tabindex="0">
              <img src="${__iconBase}/ic_home_sentry.png" alt="" onerror="this.style.visibility='hidden'">
              <div><div class="t">哨兵模式</div><div class="s" id="v-sentry">—</div></div>
            </div>
          </div>
        </div>
        <div class="entries">
          <div class="entry" id="e-health" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_health.webp" onerror="__lxIconFallback(this)" alt="">
            <div class="tx"><div class="nm">车辆健康</div></div></div>
          <div class="entry" id="e-task" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_control_off_lisa.png" alt="" onerror="this.src='${__iconBase}/ic_home_control.webp'">
            <div class="tx"><div class="nm">任务大师</div></div></div>
          <div class="entry" id="e-key" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_bluetooth.webp" onerror="__lxIconFallback(this)" alt="">
            <!-- ★ 2026-10-12：原为「钥匙管理 / 未连接」——
                 ① 名称与页面内容（车辆信息）不符，车主据此误判「显示的设置的内容」；
                 ② 「未连接」来自 _eid("key_connected")，但该绑定键根本不存在，
                    所以永远显示假状态。现改为「车辆信息」+ 真实车型副标题。 -->
            <div class="tx"><div class="nm">车辆信息</div><div class="sd" id="v-key">—</div></div></div>
          <!-- ★ 2026-10-20：情景模式入口按【车型能力】隐藏。
               M 系（理想ONE）real-time-state 无场景字段、能力表无 version:scene
               ⇒ 点进去只能看到 unknown。实体不存在就不给入口（同 QUICK 思路）。 -->
          <div class="entry" id="e-scene" role="button" tabindex="0" hidden>
            <img class="ic" src="${__iconBase}/ic_home_scene_mode_lisa.png" alt="" onerror="this.src='${__iconBase}/ic_home_control.webp'">
            <div class="tx"><div class="nm">情景模式</div></div></div>
          <div class="entry" id="e-setting" role="button" tabindex="0">
            <img class="ic" src="${__iconBase}/ic_home_control.webp" onerror="__lxIconFallback(this)" alt="">
            <div class="tx"><div class="nm">车辆设置</div></div></div>
        </div>
      </div>
      <div class="toast" role="status" aria-live="polite"></div>
    `;
    this.appendChild(root);

    // ★ 2026-10-20：卡片拖拽排序初始化（长按 350ms 抓起 → 自由换位 → 记住顺序）
    //   · 先应用已保存的顺序，再给每个 .row2 挂拖拽能力。
    //   · 两处调用：首屏渲染 + 后续重渲染（车型/主题变化会重写 DOM）。
    try {
      // ★ 先按【全局】保存的顺序重放（含跨 row2 的位置）
      if (typeof lxApplyGlobalOrder === "function") lxApplyGlobalOrder(root);
      root.querySelectorAll(".row2").forEach((r) => lxEnableDragSort(r));
      this.__lxDragBound = true;
    } catch (e) { /* 拖拽是增强功能，失败不影响主功能 */ }

    // ★ 2026-10-09（用户要求）：抬头固定。
    //   .head 用 position:sticky 粘顶；这里判断"是否已粘顶"以收紧头部。
    //   ⚠️ 用真实滚动量判断，不用 IntersectionObserver：
    //     HA 的滚动常发生在外层滚动容器里（视口 root 的 IO 会误判为"仍可见"），
    //     而 scroll 事件带 capture 能拿到容器，事件目标就是那个容器的 scrollTop。
    this._scrollCleanups = this._scrollCleanups || [];
    {
      // 浏览器可能恢复上次滚动位置：初始就按当前滚动量定"已粘顶"
      const y0 = this._scrollTopOf(null);
      let stuck = y0 > 4, lastY = y0, lastTop = null;
      const applyHeadTop = () => {
        const top = this._headTopOffset();
        if (top === lastTop) return;
        lastTop = top;
        root.style.setProperty("--lx-head-top", top + "px");
        root.dataset.headTop = String(top);   // 诊断可见：实际避让了多少 px
      };
      const onStuck = (ev) => {
        const y = this._scrollTopOf(ev);
        if (Math.abs(y - lastY) < 2) return;      // 抖动过滤
        lastY = y;
        const next = y > 4;
        if (next !== stuck) { stuck = next; root.classList.toggle("stuck", stuck); }
        applyHeadTop();
      };
      applyHeadTop();                       // 首屏先算一次
      window.addEventListener("scroll", onStuck, { passive: true });
      document.addEventListener("scroll", onStuck, { passive: true, capture: true });
      const onResize = () => applyHeadTop();
      window.addEventListener("resize", onResize, { passive: true });
      this._scrollCleanups.push(() => {
        window.removeEventListener("scroll", onStuck);
        document.removeEventListener("scroll", onStuck, { capture: true });
        window.removeEventListener("resize", onResize);
      });
    }

    const b3 = this.querySelector("#big3d"), mini = this.querySelector("#mini");
    // ★★★ 2026-10-12：车模改为**官方静态图**（放弃自建 3D）。
    //
    // 为什么放弃 3D（实测结论，别再重走）：
    //   1. 官方 AssetBundle 里**没有车门外覆件** —— 92 个网格里只有
    //      Door_*（材质="车门内_金属/内饰底绒_侧面"，即内衬），
    //      没有前/后保险杠、车门外壳。下载的官方包与本地包 md5 完全一致，
    //      所以不是导出错误，是素材本身如此。
    //   2. 成本高：转出来的 GLB 61 MB，手机每次清缓存都要重下。
    //   3. 颜色拿不到：7 个 CarPaint_* 材质共用同一张贴图、_BaseColor 全 [1,1,1]，
    //      车漆色不在模型里。
    //
    // 现在的方案（零人工配置）：
    //   GET /lixiang_auto/car-image.json → {modelId, colorCode, static:"/lixiang_car/…"}
    //   ★ colorCode 与车型配置里的 vertical[].key 是同一套（实测 colorCode=FA9）
    //   ★ 图是 p.ampmake.com 明文直链，后端按需下载并缓存，卡片直接 <img> 引用。
    //
    // 保留项：car_3d / car_iframe 配置项仍识别（显式传 car_3d:true 时走旧 3D 路径），
    //         但默认关闭 —— 以后若模型问题解决，改一个默认值即可恢复。
    const FALLBACK = c.car_image || __iconBase + "/icon_car_loc.webp";
    const still = `<img src="${FALLBACK}" alt="车辆">`;
    const useLegacy3d = c.car_3d === true;      // 默认不再走 3D

    if (useLegacy3d) {
      // ---- 旧 3D 路径（保留，默认不启用）----
      let DEFAULT_3D = "/lixiang_auto/lixiang-3d/index.html"
                     + "?minimal=1&model=/local/lixiang-3d/carmodel.glb";
      if (c.car_iframe) DEFAULT_3D = c.car_iframe;
      const frame = (title, extra) =>
        `<iframe src="${DEFAULT_3D}" title="${title}" loading="lazy" ${extra}
           sandbox="allow-scripts allow-same-origin allow-pointer-lock"></iframe>`;
      const f3 = document.createElement("iframe");
      f3.src = DEFAULT_3D; f3.title = "车辆 3D"; f3.loading = "lazy";
      f3.setAttribute("sandbox", "allow-scripts allow-same-origin allow-pointer-lock");
      b3.appendChild(f3);
      mini.innerHTML = frame("车辆 3D 缩略图", 'scrolling="no"');
    } else {
      // ---- 官方静态车模图（默认）----
      b3.innerHTML = still; mini.innerHTML = still;
      this._loadCarImage(b3, mini, FALLBACK);
    }

  /// 拉取官方车模图（★ 2026-10-12）。
  ///
  /// 后端返回 {model_id, color_code, vertical:{static, cached, key}}，
  /// 车型与车漆色都由服务器给，**用户无需任何配置**。
    // ★ 2026-10-16 车主：「是快捷下面的小三角箭头。这个键应该是快捷按键更多显示，
    //   不是隐藏和展示车模的地方。」
    //   → 拆成两个互不相干的开关：
    //     · #chev  = 快捷按键更多/收起（quick-compact：只留第一行 4 个）
    //     · #mini  = 车模 3D 的收起/展开（右上角小车图，它才是车模自己的开关）
    const toggle3d = () => {
      this._userToggled = true;    // 用户手动操作后，停止自动跟随
      const collapsed = !root.classList.contains("collapsed3d");
      root.classList.toggle("collapsed3d", collapsed);
      root.classList.toggle("expanded3d", !collapsed);
      try { localStorage.setItem("lx_3d_collapsed", collapsed ? "1" : "0"); } catch (e) {}
    };
    const toggleQuick = () => {
      const open = !root.classList.contains("quick-open");
      root.classList.toggle("quick-open", open);
      const chev = this.querySelector("#chev");
      if (chev) {
        chev.setAttribute("aria-label", open ? "收起快捷按键" : "展开更多快捷按键");
        chev.setAttribute("aria-expanded", open ? "true" : "false");
      }
    };
    const bind = (el, fn) => {
      if (!el) return;
      el.addEventListener("click", e => { e.stopPropagation(); fn(); });
      el.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); fn(); }
      });
    };
    bind(this.querySelector("#chev"), toggleQuick);   // 小三角 → 快捷按键更多/收起
    bind(this.querySelector("#mini"), toggle3d);      // 右上小车图 → 车模收起/展开

    // ★ 上拉自动收起 3D（对齐 App 交互）
    //   App 用滚动驱动：页面下滑 → 3D 收起；回到顶部 → 3D 展开
    //   ★ 2026-10-09：改为读【事件目标】的 scrollTop —— HA 的滚动常在外层容器里，
    //     只看 window.scrollY（恒为 0）会导致这里永不触发。
    if (c.car_scroll_collapse !== false) {
      const THRESHOLD = Number(c.car_scroll_threshold || 60);
      let lastY = 0, scheduled = false;
      const apply = (ev) => {
        scheduled = false;
        const y = this._scrollTopOf(ev);
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
      const onScroll = (ev) => apply(ev);   // 直接执行（scroll 本身已节流）
      window.addEventListener("scroll", onScroll, { passive: true });
      document.addEventListener("scroll", onScroll, { passive: true, capture: true });
      this._scrollCleanups = this._scrollCleanups || [];
      this._scrollCleanups.push(() => {
        window.removeEventListener("scroll", onScroll);
        document.removeEventListener("scroll", onScroll, { capture: true });
      });
    }

    const q = this.querySelector("#quick");
    // ★ 车型适配：只渲染这台车**真实支持**的功能
    const warmup = !this._hass || !Object.keys(this._hass.states || {}).length;
    // ★ 2026-10-14：网格渲染抽成独立方法（可重复调用）。
    //   原来这段直接写在 _build() 里，且**一旦 avail 为空就 return** ——
    //   首帧实体未就绪时会把后面「入口卡片接线」整段跳过，且 _build 只跑一次，
    //   导致**入口永远点不动**（车主反馈"下面的都无法操作"）。
    this._renderQuick(warmup);

    this._wireNav();

    // ★ 2026-10-12：车主指示移除「服务专家」与「理想AD学习平台」两个入口

    this._built = true;
  }




  /** 渲染快捷键网格（可重复调用：首帧实体未就绪时先占位，实体到位后自动重建） */
  _renderQuick(warmup) {
    const q = this.querySelector("#quick");
    if (!q) return;
    const avail = QUICK.filter(it => this._supports(it, warmup));
    // 已渲染过同样数量的按钮 → 无需重建（避免丢掉点击态/焦点）
    if (q.querySelector(".q") && q.dataset.shown === String(avail.length)
        && avail.every(it => q.querySelector(`.q[data-key="${it.key}"]`))) return;
    q.dataset.shown = String(avail.length);
    // ★ 2026-10-16：快捷项 ≤4（一行）时没有"更多"可展开 → 藏掉小箭头
    const chevEl = this.querySelector("#chev");
    if (chevEl) chevEl.style.display = avail.length > 4 ? "" : "none";
    q.replaceChildren();
    if (!avail.length) {
      q.innerHTML = '<div class="qempty">该车型暂无可用快捷功能</div>';
      return;
    }
    avail.forEach(it => {
      const d = document.createElement("div");
      d.className = "q"; d.dataset.key = it.key;
      d.setAttribute("role", "button"); d.setAttribute("tabindex", "0");
      d.setAttribute("aria-label", it.name);
      d.innerHTML = `<div class="c"><img src="${this._img(it.off)}" alt="" onerror="__lxIconFallback(this)"></div>
                     <div class="n">${it.name}</div><div class="sp"></div><div class="sub"></div>`;
      d.addEventListener("click", () => this._tap(it.key));
      d.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this._tap(it.key); }
      });
      q.appendChild(d);
    });
  }

  /** 入口卡片接线（幂等：只接一次，元素在 _build 后不再替换） */
  _wireNav() {
    if (this._navWired) return;
    this._navWired = true;
    const c = this._config;
    const nav = c.nav || {};
    const go = p => { if (!p) return; lxNavigate(this, p); };
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
    // ★ 2026-10-20：情景模式入口按车型隐藏
    //   ONE（M 系）的 real-time-state 无场景字段、能力表无 version:scene
    //   ⇒ 实体不会创建 ⇒ 不给入口（避免点进去只有 unknown）
    {
      const _el = this.$("#e-scene");
      if (_el) {
        const _has = !!this._eid("scene_mode")
                   || !!this._eidIn("entries", "scene_mode")
                   || !!this._eidIn("quick", "scene_mode");
        _el.hidden = !_has;
      }
    }
    wire("#e-scene", nav.scene || "/lixiang/scene");
    // 2026-10-12 修复（车主："车辆设置二级页面错误"）：这两行此前没有默认路径。
    // nav.setting / nav.health 未配置时是 undefined → go(undefined) → if (!p) return
    // → 点击完全没反应。与其他入口一致，补上默认路径。
    wire("#e-health", nav.health || "/lixiang/health");
    wire("#e-setting", nav.setting || "/lixiang/setting");
    // ★ 地图卡拍照按钮（官方 HomeControlMapPhoto）
    const shotEl = this.querySelector("#hm-shot");
    if (shotEl) {
      const shoot = async () => {
        const pe = this._eid("btn_photo");
        if (!pe) { this._toast("远程拍照未接入", "err"); return; }
        if (!this._online()) { this._toast("车辆离线，操作不可用", "err"); return; }
        try {
          await this._hass.callService("button", "press", { entity_id: pe });
          this._toast("已发送拍照", "ok");
        } catch (e) { this._toast("拍照失败：" + ((e && e.message) || "未知"), "err"); }
      };
      this._a11y(shotEl, "远程拍照", shoot);
      shotEl.addEventListener("click", shoot);
    }

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
  }

  /** 胎压 → {v, unit}：实体单位是 kPa 时换算成 bar（与「车辆健康」页同一规则） */
  _tireVal(field) {
    const v = this._num(this._eid(field));
    const st = this._st(this._eid(field));
    const u = String(((st && st.attributes) || {}).unit_of_measurement || "").toLowerCase();
    if (v === null) return null;
    if (u.includes("kpa")) return { v: v / 100, unit: "bar" };
    if (u.includes("psi")) return { v: v / 14.5038, unit: "bar" };
    if (u.includes("bar")) return { v, unit: "bar" };
    return { v, unit: u || "" };
  }

  /** 把四个胎压值写到车图上（车头朝左的俯视图：车头在左端，车左侧在下方） */
  _applyTires() {
    const box = this.querySelector("#big3d");
    if (!box) return;
    // ★ 车图加载时会重写 #big3d 的 innerHTML，静态模板里的浮层会被冲掉
    //   → 这里按需创建（幂等），保证浮层始终在。
    let layer = box.querySelector(".tires");
    if (!layer) {
      layer = document.createElement("div");
      layer.className = "tires";
      layer.id = "tires";
      layer.style.display = "none";
      layer.innerHTML = '<div class="tp" data-k="lf"></div><div class="tp" data-k="rf"></div>'
        + '<div class="tp" data-k="lr"></div><div class="tp" data-k="rr"></div>';
      box.appendChild(layer);
    }
    const MAP = { lf: "tire_lf", rf: "tire_rf", lr: "tire_lr", rr: "tire_rr" };
    let any = false;
    for (const [k, field] of Object.entries(MAP)) {
      const el = layer.querySelector(`.tp[data-k="${k}"]`);
      if (!el) continue;
      const p = this._tireVal(field);
      if (p === null) { el.style.display = "none"; continue; }
      const bad = p.v > 0 && (p.v < 2.0 || p.v > 2.9);
      el.style.display = "";
      const num = bad && p.v < 2.0 ? p.v.toFixed(2) : p.v.toFixed(1);
      // ★ 带上单位（车主："另外确实单位"）
      el.innerHTML = `<b>${num}</b><small> ${p.unit}</small>`;
      el.classList.toggle("low", !!bad);
      el.title = `${({lf:"左前",rf:"右前",lr:"左后",rr:"右后"})[k]} ${num} ${p.unit}`;
      any = true;
    }
    layer.style.display = any ? "" : "none";
    if (any) this._layoutTires();
  }

  /** 按车图**实际渲染区域**摆放（车图 contain + object-position:50% 62%，不铺满盒子） */
  _layoutTires() {
    const box = this.querySelector("#big3d");
    const layer = box && box.querySelector(".tires");
    if (!box || !layer) return;
    const bw = box.clientWidth, bh = box.clientHeight;
    // 车图（object-fit:contain + object-position:50% 62%）的实际渲染区域
    let ox = 0, oy = 0, cW = bw, cH = bh;
    const img = box.querySelector("img");
    if (img && img.naturalWidth) {
      const r = img.getBoundingClientRect(), br = box.getBoundingClientRect();
      const ar = img.naturalHeight / img.naturalWidth;
      cH = Math.min(r.height, r.width * ar); cW = cH / ar;
      ox = r.left - br.left + (r.width - cW) / 2;
      oy = r.top - br.top + (r.height - cH) * 0.62;
    }
    // ★ 2026-10-14 车主纠正：车是**横放**的，四个轮子在车的**上下两条边**上，
    //   标签要贴在各自车轮的上/下侧 —— 不是放在卡片左右两端（车头/车尾）。
    //   实测轮心：纵向 x≈28.4% / 71.4%（前/后），横向 y≈29% / 71%（车的右侧在上、左侧在下）。
    //   车体轮廓占图高的 8%~92%，所以上排标签放车顶边之上、下排放车底边之下。
    const xF = ox + cW * 0.284;      // 前轮
    const xR = ox + cW * 0.714;      // 后轮
    const yT = oy + cH * 0.08 - 15;  // 车顶边之上（标签半高 + 间隙）
    const yB = oy + cH * 0.92 + 15;  // 车底边之下
    const POS = {
      rf: [xF, yT], rr: [xR, yT],    // 上排 = 车的右侧（右前 / 右后）
      lf: [xF, yB], lr: [xR, yB],    // 下排 = 车的左侧（左前 / 左后）
    };
    for (const [k, [px, py]] of Object.entries(POS)) {
      const el = layer.querySelector(`.tp[data-k="${k}"]`);
      if (!el) continue;
      el.style.left = Math.round(px) + "px";
      el.style.top = Math.round(py) + "px";
      el.style.right = "auto";
    }
  }

  /// 失败时保留占位图（不显示破图）。
  async _loadCarImage(b3, mini, fallback) {
    // ★ 2026-10-16 修「车图时有时无」：
    //   ① 先用**上次成功的 URL**（localStorage）→ 秒出；JSON 拿不到时也不至于退回 20×20 占位图标
    //   ② JSON 失败**重试一次**（1.5s 后），仍失败且无缓存 → 5s 后再试一轮（网络恢复自动出图）
    //   ③ <img> onerror **带 ?v= 重试一次**（破掉浏览器可能缓存的坏响应）
    const CK = "lx_car_img_v1";
    const hit = (() => { try { const o = JSON.parse(localStorage.getItem(CK) || "{}"); return o && o.src ? o : null; } catch (e) { return null; } })();
    const applySrc = (src, key) => {
      const put = (box) => {
        if (!box) return;
        const img = box.querySelector("img");
        if (!img) return;
        if (img.dataset.lxReal === "1" && img.getAttribute("src") === src) return;
        img.dataset.lxReal = "1";
        delete img.dataset.lxRetried;
        img.onload = () => { img.style.opacity = "1"; delete img.dataset.lxRetried; };
        img.onerror = () => {
          if (img.dataset.lxRetried === "1") { img.style.opacity = "0"; return; }   // 两次都失败 → 先藏，下轮再试
          img.dataset.lxRetried = "1";
          const bust = src + (src.indexOf("?") >= 0 ? "&" : "?") + "v=" + Date.now();
          setTimeout(() => { img.src = bust; }, 600);
        };
        img.style.opacity = "1";
        img.src = src;
        img.alt = "车辆 " + (key || "");
        img.style.objectFit = "contain";
      };
      put(b3); put(mini);
      if (b3) {
        const _im = b3.querySelector("img");
        if (_im) _im.addEventListener("load", () => this._layoutTires(), { once: true });
        this._layoutTires();
      }
    };
    if (hit) applySrc(hit.src, hit.key);                 // ① 缓存优先
    let data = null;
    for (let i = 0; i < 2 && !data; i++) {                // ② 拉 JSON（失败重试一次）
      try {
        const resp = await fetch("/lixiang_auto/car-image.json", { cache: "no-store" });
        if (resp.ok) data = await resp.json();
      } catch (err) { /* 静默：占位图已在 DOM 里 */ }
      if (!data && i === 0) await new Promise((r) => setTimeout(r, 1500));
    }
    if (!data || !data.ok || !data.vertical) {
      if (!hit) setTimeout(() => { if (this.isConnected) this._loadCarImage(b3, mini, fallback); }, 5000);
      return;
    }
    // ★ 横版优先（官方竖图逆时针旋转 90° 派生，车头朝左）—— 横容器不再"车小如邮票"
    const src = (data.horizontal && data.horizontal.static) || data.vertical.static || "";
    if (!src) return;                     // 还没缓存好 → 保持占位，下次刷新再来
    if (!hit || hit.src !== src) applySrc(src, data.color_code);   // ③ 只在变化时重设，避免闪
    try { localStorage.setItem(CK, JSON.stringify({ src, key: data.color_code || "", t: Date.now() })); } catch (e) {}
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
    if (!eid) {
      this._toast(`${def.name} ${def.note || "尚未接入"}`, "err");
      return;
    }
    if (!this._online()) { this._toast("车辆离线，操作不可用", "err"); return; }
    // ★ 官方同款：这类动作执行前要二次确认（可勾选"不再提醒"）
    if (def.confirm && !this._noAsk(key)) {
      const r = await this._confirm({ text: def.confirm, remember: def.remember });
      if (!r.ok) return;
      if (r.remember) this._setNoAsk(key, true);
    }
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
      } else if (dom === "cover") {
        // ★ 2026-10-09 修复：cover 域【没有】open/close 服务，
        //   正确服务名是 open_cover / close_cover（此前调用必然失败）。
        const opened = ["open","opening","on","开启","已连接"].some(v => String(s.state).includes(v));
        await this._hass.callService("cover", opened ? "close_cover" : "open_cover", { entity_id: eid });
        this._optim[key] = !opened;
      } else if (dom === "switch") {
        // ★ 2026-10-09 修复：switch 域没有 open/close，只有 turn_on/turn_off。
        const on = ["on","open","开启","true"].some(v => String(s.state).includes(v));
        await this._hass.callService("switch", on ? "turn_off" : "turn_on", { entity_id: eid });
        this._optim[key] = !on;
      } else if (dom === "select") {
        const opts = (s.attributes && s.attributes.options) || [];
        const cur = opts.indexOf(s.state);
        const next = opts[(cur + 1) % opts.length];
        await this._hass.callService("select","select_option",{entity_id:eid, option:next});
        this._toast(`${def.name} → ${next}`, "ok");
      } else if (dom === "button") {
        await this._hass.callService("button","press",{entity_id:eid});
      } else if (dom === "binary_sensor" || dom === "sensor") {
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
      const ttl = (def && def.optimMs) || 3500;
      setTimeout(() => { delete this._optim[key]; this._applyQuick(); }, ttl);
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
      // stateField：动作类按钮（如授权驾驶 = button）用另一个实体显示状态。
      // ★ 配了 stateField 但解析不到（该车没有这个实体）时必须返回 null ——
      //   回退到动作实体本身会让 button 的时间戳状态被当成"开着"（真实踩过的坑）。
      const stateEid = it.stateField ? (this._eid(it.stateField) || null) : eid;
      let active = false; const missing = !eid || !this._st(eid);
      if (stateEid && this._st(stateEid)) {
        if (it.key in this._optim) active = this._optim[it.key];
        else if (it.key === "lock") {
          const v = String((this._st(stateEid) || {}).state || "");
          active = ["unlocked","已解锁"].some(x => v.includes(x));
        } else active = this._on(stateEid);
      }
      el.className = "q" + (active ? " on" : "") + ((missing || offline) ? " dim" : "")
                   + (this._busy[it.key] ? " busy" : "");
      // ★ 2026-10-14 官方逻辑：授权按钮有**两态** ——
      //   车辆已启动（非驻车）→ 已启动；已授权 → 已授权；否则 授权驾驶。
      //   （官方 I18N：alreadyAuthorization='已授权' / alreadyStart='已启动'）
      const nameEl = el.querySelector(".n");
      if (nameEl && it.onName) {
        let want = active ? it.onName : it.name;
        if (it.startedName) {
          const stTxt = String(this._txt(this._eid("status")) || "");
          const started = !!stTxt && !/驻车|P\s*档|park/i.test(stTxt);
          if (started) { want = it.startedName; active = true; }
        }
        if (nameEl.textContent !== want) nameEl.textContent = want;
      }
      el.setAttribute("aria-pressed", active ? "true" : "false");
      // 未接入的按钮：把原因写在下面（例如"集成暂未支持"），避免用户反复点
      const sub = el.querySelector(".sub");
      if (sub && missing && it.note) sub.textContent = it.note;
      const img = el.querySelector("img");
      if (img) {
        // ★ 2026-10-14：只在目标变化时赋值，并清掉回退标记 ——
        //   __lxIconFallback 带 dataset.lxFb 一次性保护；若每次都重新赋 /local 值，
        //   回退救回来的内置图标会被再次写坏且不再回退 → 永久破图。
        const want = this._img(active ? it.on : it.off);
        if (img.getAttribute("src") !== want) {
          delete img.dataset.lxFb;
          img.src = want;
        }
      }
    });
  }

  /** 本月每日里程 —— **柱状图**（对齐 App；此前是折线）。
   *  每根柱子等宽，高度按当月最大值归一；0 值不画柱子。
   */
  _spark() {
    const el = this.querySelector("#sparkbars"); if (!el) return;
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
    if (!vals || !vals.length) { el.innerHTML = ""; return; }
    const max = Math.max.apply(null, vals.concat([1]));
    const n = vals.length;
    const step = 100 / n;                       // 每根柱子占的横向槽位
    const bw = Math.max(step * 0.62, 0.9);      // 柱宽（留间隙）
    el.innerHTML = vals.map((v, i) => {
      const val = Number(v) || 0;
      const h = (val / max) * 34;               // 柱高（底部留 6 给坐标轴）
      const x = i * step + (step - bw) / 2;
      const y = 40 - h - 2;
      const zero = val <= 0 ? ' data-zero="1"' : "";
      return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${bw.toFixed(2)}" `
           + `height="${Math.max(h, 0.6).toFixed(2)}"${zero}></rect>`;
    }).join("");
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
    // ★ 2026-10-14：空调是 climate 域，状态是 cool/heat/auto/fan_only…（**不是 on**），
    //   原来用 _on() 判 → 永远 false → 风扇不转；且图标固定用白色版（浅底上几乎看不见）。
    const acEid = this._eid("ac");
    const acSt = this._st(acEid);
    const acRaw = acSt ? String(acSt.state).toLowerCase() : "";
    const acOn = ["cool", "heat", "heat_cool", "auto", "dry", "fan_only", "on", "开启"]
      .some((x) => acRaw.includes(x));
    const fan = q("#fan");
    if (fan) {
      fan.className = "fan" + (acOn ? " on" : "");
      const fi = fan.querySelector("img");
      const want = this._img(acOn ? "ic_home_fan_on.webp" : "ic_home_fan_off.webp");
      if (fi && fi.getAttribute("src") !== want) { delete fi.dataset.lxFb; fi.src = want; }
    }
    // 功能状态 chip（有实体且开启时点亮；无实体则隐藏）
    const _chip = (sel, eid) => {
      const el = q(sel); if (!el) return;
      if (!eid) { el.style.display = "none"; return; }
      el.style.display = "";
      el.className = "chip" + (this._on(eid) ? " on" : "");
    };
    // ★ 2026-10-14 对齐官方空调页文案（从 index.vehicle.bundle 反汇编提取，共 23 项）：
    //   deicing:'除雪除霜' · rapidCool:'极速制冷' · rapidHeat:'极速制热' · steeringWheelHeat:'方向盘加热'
    //   我们原来写的是 座椅 / 吹风 / 除霜 —— 与官方措辞不一致。
    const seatEid = this._eid("steer_heat");
    _chip("#ch-seat", seatEid || this._eid("ac_fast_hot"));
    const seatT = q("#ch-seat-t");
    if (seatT) seatT.textContent = seatEid ? "方向盘加热" : "极速制热";
    _chip("#ch-fan", this._eid("ac_fast_cold"));
    const fanT = q("#ch-fan-t"); if (fanT) fanT.textContent = "极速制冷";
    _chip("#ch-defrost", this._eid("ac_defrost"));
    const defT = q("#ch-defrost-t"); if (defT) defT.textContent = "除雪除霜";

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

    // ★ 2026-10-11：充电中显示「剩余2小时25分钟」（对齐 App）。
    //   判据：ChargeSurplusTime(剩余充电时间) > 0 —— 无需依赖额外的充电状态实体。
    //   非充电态（无该实体 / 值为 0 / 未知）→ 整行隐藏，不留空位。
    const rmEl = q("#batt-remain");
    if (rmEl) {
      const rmRaw = this._txt(this._eid("remain_time"));
      const rmMin = Number(rmRaw);
      if (rmRaw && Number.isFinite(rmMin) && rmMin > 0) {
        rmEl.style.display = "";
        const _h = Math.floor(rmMin / 60), _m = Math.round(rmMin % 60);
        q("#v-remain").textContent =
          (_h ? _h + "小时" : "") + (_m ? _m + "分钟" : (_h ? "整" : "—"));
      } else {
        rmEl.style.display = "none";
      }
    }

    const sen = this._eid("sentry") ? this._on(this._eid("sentry")) : false;
    const senEl = q("#c-sentry"); if (senEl) senEl.className = "card sentry" + (sen ? " on" : "");
    q("#v-sentry").textContent = this._eid("sentry") ? (sen ? "已激活" : "未激活") : "未接入";

    // ★ 插电标识（对齐 App：插枪时才有充电桩/插枪提示）。
    //   交流枪与直流枪任一插入即显示；都没有则整块隐藏（不留空隙）。
    const plugEl = q("#v-plug");
    if (plugEl) {
      const acGun = this._on(this._eid("ac_gun"));
      const dcGun = this._on(this._eid("dc_gun"));
      if (acGun || dcGun) {
        plugEl.style.display = "";
        const pt = q("#v-plug-t");
        if (pt) pt.textContent = (dcGun ? "直流快充" : "交流慢充") + " · 充电枪已插入";
      } else {
        plugEl.style.display = "none";
      }
    }

    // 副标题显示车型（真实数据）；拿不到就留空，不再显示假状态
    const vk = q("#v-key");
    if (vk) {
      const cfg = this._txt(this._eid("vehicle_cfg"));
      vk.textContent = cfg ? String(cfg).slice(0, 10) : "";
    }

    // ★ 2026-10-14：首帧实体未就绪时网格是空的 —— 实体到位后重建
    if (!this.querySelector("#quick .q")) this._renderQuick(false);
    this._applyQuick(); this._spark();
    this._applyTires();
    // ★ 2026-10-14 对齐官方顶部徽标：告警（胎压告警任一）/ 哨兵（开启时）
    const wEl = this.querySelector("#v-badge-warn");
    if (wEl) {
      const wids = ["warn_lf", "warn_rf", "warn_lr", "warn_rr"]
        .map((k) => this._eid(k)).filter(Boolean);
      const won = wids.filter((id) => this._on(id)).length;
      wEl.style.display = won ? "" : "none";
      const wt = this.querySelector("#v-badge-warn-t");
      if (wt) wt.textContent = won > 1 ? `告警 ${won}` : "胎压告警";
    }
    const sBEl = this.querySelector("#v-badge-sentry");
    if (sBEl) {
      const se = this._eid("sentry");
      sBEl.style.display = (se && this._on(se)) ? "" : "none";
    }
    const shotBEl = this.querySelector("#hm-shot");
    if (shotBEl) shotBEl.style.display = this._eid("btn_photo") ? "" : "none";
    if (!this._tireResize) {
      this._tireResize = () => this._layoutTires();
      window.addEventListener("resize", this._tireResize);
    }
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
window.customCards = window.customCards || [];
// 去重：自动注入 + 手工注册可能同时存在，避免卡片选择器出现重复项
// ★ 2026-10-14：单页卡默认不列进卡片选择器（车主要求选择器里只留两张）。
  //   YAML 里直接写 type: custom:xxx-page 仍然可用 —— 自定义元素照样已定义，
  //   只是不在选择列表里。需要列出时：加载卡片前置 window.__LX_PICKER_ALL = true。
  if (window.__LX_PICKER_ALL === true && !window.customCards.some((c) => c && c.type === CARD_TAG)) window.customCards.push({
  type: CARD_TAG,
  name: "理想车控首页（v3 · 对齐 App）",
  description: "8 圆按钮 · 双态 3D · 空调/位置/里程/电量/哨兵 · 各页入口",
  preview: true,
});
