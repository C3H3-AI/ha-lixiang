
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
 * lixiang-task-page —— 车控任务（对齐 App「任务大师」，但落地为 HA 自动化）
 *
 * 背景：
 *   App 的「任务大师」是【云端规则引擎】—— 规则存理想服务器，
 *   集成没有对应 API，无法读写。
 *
 * 但 App 的模型 = IFTTT = HA automation：
 *   任务名称  → alias
 *   如果      → trigger
 *   就执行    → action
 *
 * 本卡片用【同样的交互】创建 **HA 自动化**，效果等价甚至更强：
 *   · 本地执行（不依赖网络，更快）
 *   · 可联动其他品牌设备
 *   · 可发通知 / 调脚本
 *
 * 写入 API：POST /api/config/automation/config/{id}
 */

/* ★ 条件/动作分类的中文名（服务端只给英文 classification） */
const _DICT_CLS_LABEL = {
  ConditionTimes:"时间", ConditionEnvironments:"环境", ConditionLocations:"位置",
  ConditionNavigations:"导航", ConditionPassengers:"乘员", ConditionSittingPositions:"坐姿",
  ConditionDrivings:"驾驶", ConditionPowerStatus:"充电供电", ConditionDoorsAndWindows:"门窗",
  ConditionBelts:"安全带", ConditionLights:"灯光", ConditionVolumes:"音量",
  ConditionApplications:"应用", ConditionModes:"模式", ConditionAccessories:"配件",
  ActionDelays:"延时", ActionAirs:"空调", ActionSeatAirs:"座椅通风", ActionSeatHeats:"座椅加热",
  ActionSeatMassages:"座椅按摩", ActionSittingPositions:"座椅位置", ActionDrivings:"驾驶",
  ActionDoorsAndWindows:"门窗", ActionLights:"灯光", ActionScreenShows:"屏幕",
  ActionVolumes:"音量", ActionNavigations:"导航", ActionBluetooths:"蓝牙",
  ActionApplications:"应用", ActionModes:"模式", ActionLiStudents:"学习",
  ActionAccessories:"配件",
};
/* ★ 常用条目的中文名（未列出的直接显示英文 type，不猜） */
const _DICT_ITEM_LABEL = {
  Gear:"挡位", Speed:"车速", Lock:"车锁", BatteryRemaining:"剩余电量",
  InsideTemperature:"车内温度", OutsideTemperature:"车外温度", TimeRange:"时间段",
  Sunrise:"日出", Sunset:"日落", Time:"定时", InRange:"在位置范围内", OutRange:"在位置范围外",
  LeftFDoor:"主驾车门", RightFDoor:"副驾车门", TailDoor:"尾门",
  LeftFWindow:"主驾车窗", RightFWindow:"副驾车窗", LeftRWindow:"左后车窗", RightRWindow:"右后车窗",
  DriverBelt:"主驾安全带", CopilotBelt:"副驾安全带",
  ChargingStatus:"充电状态", ChargingGunStatus:"充电枪",
  MusicPlaying:"音乐播放", MediaVolume:"媒体音量",
  Driver:"主驾", Copilot:"副驾", SecondLeft:"二排左", SecondRight:"二排右", SecondMid:"二排中",
  GetOnCar:"上车", GetOffCar:"下车",
  ACSwitch:"空调开关", Defog:"除雾", AirPurification:"空气净化",
  DriverHeating:"主驾加热", SecondLHeating:"二排左加热",
  DriverAir:"主驾通风", SeatHeating_:"座椅加热",
  Headlights:"大灯", AllDoorsLock:"全车落锁", AutoUnlock:"自动解锁",
  Delay:"延时", OpenApp:"打开应用", BackHome:"回家",
};

const CARD_TAG = "lixiang-task-page";
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

/* ── 车控常用模板（对应 App 社区的常见任务）──
 * entity_id: null 的占位符在卡片运行时用自动发现结果填充 */
function buildPresets(card) {
  const eid = (f) => card._eid(f);
  return PRESET_DEFS.map((p) => {
    const t = Object.assign({}, p.trigger);
    if (!t.entity_id) {
      t.entity_id = eid(t._field
        || (t.platform === "numeric_state" && t.below != null ? "battery"
            : (t.above != null ? "room_temp" : "status")));
    }
    delete t._field;
    const action = p.action.map((a) => {
      const b = JSON.parse(JSON.stringify(a));
      if (b.target && b.target.entity_id === null) b.target.entity_id = eid(p.actionField || "ac");
      return b;
    }).filter((a) => !(a.target && !a.target.entity_id));
    return Object.assign({}, p, { trigger: t, action });
  }).filter((p) => p.trigger.entity_id && p.action.length);
}
const PRESET_DEFS = [
  { name: "无人关闭通风", icon: "ic_home_fan_on.webp", color: "#34C759", actionField: "ac",
    desc: "离车后自动关闭空调通风",
    trigger: { platform: "state", entity_id: null, to: "已驻车（P 档）", for: "00:05:00" },
    action: [{ service: "climate.turn_off", target: { entity_id: null } }] },
  { name: "有人自动通风", icon: "ic_home_fan_on.webp", color: "#34C759", actionField: "ac",
    desc: "车内温度过高时开启空调",
    trigger: { platform: "numeric_state", entity_id: null, above: 30 },
    action: [{ service: "climate.turn_on", target: { entity_id: null } }] },
  { name: "离车关遮阳帘防晒", icon: "ic_home_control.webp", color: "#0A58F6", actionField: "sunshade",
    desc: "锁车后关闭遮阳帘",
    trigger: { platform: "state", entity_id: null, to: "locked", _field: "lock" },
    action: [{ service: "cover.close_cover", target: { entity_id: null } }] },
  { name: "低电量提醒", icon: "ic_home_battery.webp", color: "#FF9500", actionField: "sentry",
    desc: "电量低于 20% 时发通知",
    trigger: { platform: "numeric_state", entity_id: null, below: 20 },
    action: [{ service: "persistent_notification.create",
               data: { title: "理想 L6 电量偏低", message: "建议尽快充电" } }] },
  { name: "哨兵模式自动开启", icon: "ic_home_sentry.png", color: "#FF3B30", actionField: "ac",
    desc: "驻车 10 分钟后开启哨兵",
    trigger: { platform: "state", entity_id: null, to: "已驻车（P 档）", for: "00:10:00", _field: "status" },
    action: [{ service: "switch.turn_on", target: { entity_id: null } }] },
  { name: "长途驾驶疲劳缓解", icon: "ic_home_control.webp", color: "#FF9500", actionField: "ac",
    desc: "连续驾驶 2 小时后提醒休息",
    trigger: { platform: "state", entity_id: null, to: "行驶中", for: "02:00:00", _field: "status" },
    action: [{ service: "persistent_notification.create",
               data: { title: "该休息了", message: "已连续驾驶 2 小时" } }] },
];

const STYLE = `
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("/local/lixiang-fonts/licium_medium.ttf");  font-weight:500; font-display:swap; }
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

  .topbar { display:flex; align-items:center; height:52px; padding:0 16px; position:relative; }
  .back { width:34px; height:34px; border-radius:50%; background:var(--lx-card);
          display:flex; align-items:center; justify-content:center; cursor:pointer; }
  .back img { width:18px; height:18px; opacity:.7; }
  .topbar h1 { position:absolute; left:0; right:0; text-align:center;
               font-size:18px; font-weight:500; margin:0; pointer-events:none; }
  .help { margin-left:auto; font-size:15px; color:var(--lx-t2); cursor:pointer;
          padding:6px 8px; position:relative; z-index:2; }

  /* Tabs */
  .tabs { display:flex; gap:26px; padding:6px 20px 0; border-bottom:1px solid var(--lx-line); }
  .tab { font-size:15.5px; color:var(--lx-t2); padding:10px 0 12px; cursor:pointer;
         position:relative; }
  .tab.on { color:var(--lx-t1); font-weight:500; }
  .tab.on::after { content:""; position:absolute; left:0; right:0; bottom:-1px;
                   height:2.5px; background:var(--lx-blue); border-radius:2px; }

  .sorts { display:flex; gap:20px; padding:16px 20px 6px; }
  .sort { font-size:14.5px; color:var(--lx-t3); cursor:pointer; }
  .sort.on { color:var(--lx-t1); font-weight:500; }

  /* 任务卡列表 */
  .list { padding:6px 16px 0; }
  .item { display:flex; align-items:center; gap:13px; background:var(--lx-card);
          border-radius:16px; padding:15px 16px; margin-bottom:10px; cursor:pointer;
          transition:transform .13s; }
  .item:active { transform:scale(.985); }
  .item .ic { width:38px; height:38px; border-radius:11px; display:flex;
              align-items:center; justify-content:center; flex:0 0 auto; }
  .item .ic img { width:21px; height:21px; }
  .item .tx { flex:1; min-width:0; }
  .item .n { font-size:16px; display:flex; align-items:center; gap:7px; }
  .item .n .new { font-size:10px; background:var(--lx-blue); color:#fff;
                  padding:2px 6px; border-radius:5px; font-weight:500; }
  .item .a { font-size:12.5px; color:var(--lx-t3); margin-top:5px; }
  .item .ar { color:var(--lx-t3); font-size:17px; flex:0 0 auto; }
  .item.on .n { color:var(--lx-blue); }

  /* 创建区 */
  .create { margin:18px 16px 0; }
  .field { background:var(--lx-card); border-radius:18px; padding:16px;
           margin-bottom:14px; }
  .field .lbl { font-size:15px; font-weight:500; margin-bottom:4px; }
  .field .hint { font-size:12.5px; color:var(--lx-t3); line-height:1.55;
                 margin-bottom:12px; }
  .nameinput { width:100%; border:none; background:transparent; font-size:16px;
               color:var(--lx-t1); outline:none; font-family:inherit;
               padding:10px 0; }
  .nameinput::placeholder { color:#C7C7CC; }
  .addbox { border:1.5px dashed var(--lx-line); border-radius:14px; padding:22px;
            display:flex; flex-direction:column; align-items:center; gap:6px;
            cursor:pointer; color:var(--lx-t2); }
  .addbox .p { font-size:26px; line-height:1; font-weight:300; }
  .addbox .t { font-size:14.5px; }
  .chips { display:flex; flex-direction:column; gap:8px; }
  .chip { background:var(--lx-bg); border-radius:12px; padding:12px 14px;
          font-size:13.5px; display:flex; align-items:center; gap:9px; }
  .chip .x { margin-left:auto; color:var(--lx-t3); cursor:pointer; padding:0 4px;
             font-size:16px; }
  .confirm { text-align:center; border-radius:26px; padding:15px; font-size:16px;
             background:#1A1A1A; color:#fff; cursor:pointer; transition:opacity .2s; }
  .confirm.dis { background:#E5E5EA; color:#AEAEB2; cursor:not-allowed; }
  .confirm:not(.dis):active { transform:scale(.985); }

  /* 底部固定 */
  .bottom { display:flex; align-items:center; gap:12px; margin:18px 16px 0; }
  .share { font-size:14.5px; color:var(--lx-t2); cursor:pointer; }
  .mk { flex:1; text-align:center; background:#1A1A1A; color:#fff;
        border-radius:24px; padding:14px; font-size:15px; cursor:pointer; }

  .empty { text-align:center; color:var(--lx-t3); font-size:13px; padding:30px 0; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9;
           max-width:82%; text-align:center; line-height:1.5; }
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

class LixiangTaskPage extends HTMLElement {
  setConfig(c) {
    this._config = c || {};
    if (this._config.icon_base) __iconBase = this._config.icon_base;
    if (this._config.font_base) __fontBase = this._config.font_base; this._tab = "discover"; this._sort = "rec";
    this._mine = []; this._draft = null; this._built = false;
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
  // ★ 2026-10-11 新增：读实体状态（其他页面都有；此前本页缺它，
  //   新加的触发条件过滤调用后会抛 TypeError → 被 test_frontend_bindings 抓到）
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }


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
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <h1>任务大师</h1>
        <div class="help" id="help" role="button" tabindex="0" aria-label="帮助">帮助</div>
      </div>

      <div class="tabs">
        <div class="tab on" data-tab="discover" role="button" tabindex="0">发现</div>
        <div class="tab" data-tab="mine" role="button" tabindex="0">我的任务</div>
        <div class="tab" data-tab="create" role="button" tabindex="0">创建任务</div>
      </div>

      <div id="body"></div>
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

    const help = () => this._toast(
      "App 的「任务大师」规则存在理想云端，集成无法读写。本页创建的是 HA 自动化" +
      "（本地执行，可联动其他设备），效果等价。", null, 5200);
    this._a11y(this.querySelector("#help"), "帮助", help);
    this.querySelector("#help").addEventListener("click", help);

    this.querySelectorAll(".tab").forEach(t => {
      const act = () => { this._tab = t.dataset.tab; this._render(); };
      this._a11y(t, t.textContent, act);
      t.addEventListener("click", act);
    });

    this._built = true;
  }

  /** 模板（延迟构造：实体由自动发现提供） */
  _presets() {
    if (!this._presetCache) this._presetCache = buildPresets(this);
    return this._presetCache;
  }

  _toast(msg, kind, ms) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, ms || 2600);
  }

  /** 我的任务：枚举 automation 实体（由本卡片创建的） */
  _myTasks() {
    const out = [];
    const h = this._hass; if (!h) return out;
    for (const id of Object.keys(h.states)) {
      if (!id.startsWith("automation.")) continue;
      const s = h.states[id];
      const a = s.attributes || {};
      const isMine = (a.id && String(a.id).startsWith("lx_"))
        || /理想|车辆|车控|哨兵|充电|座椅|空调/.test(a.friendly_name || "");
      if (isMine) out.push({ id, eid: id, alias: a.friendly_name || id,
                             on: s.state === "on", last: a.last_triggered });
    }
    return out;
  }

  _render() {
    const box = this.querySelector("#body");
    this.querySelectorAll(".tab").forEach(t =>
      t.className = "tab" + (t.dataset.tab === this._tab ? " on" : ""));

    if (this._tab === "discover") { box.innerHTML = this._discoverHtml(); this._bindDiscover(); }
    else if (this._tab === "mine") { box.innerHTML = this._mineHtml(); this._bindMine(); }
    else { box.innerHTML = this._createHtml(); this._bindCreate(); }
  }

  /* ── 发现（模板库）── */
  _discoverHtml() {
    return `
      <div class="sorts">
        <span class="sort on" data-s="rec">推荐</span>
        <span class="sort" data-s="hot">最热</span>
        <span class="sort" data-s="new">飙升</span>
      </div>
      <div class="list">
        ${this._presets().map((p, i) => `
          <div class="item" data-i="${i}">
            <div class="ic" style="background:${p.color}22">
              <img src="${__iconBase}/${p.icon}" alt="" onerror="this.style.visibility='hidden'"></div>
            <div class="tx">
              <div class="n">${p.name}<span class="new">NEW</span></div>
              <div class="a">${p.desc}</div>
            </div>
            <div class="ar">›</div>
          </div>`).join("")}
      </div>
      <div class="bottom">
        <span class="share" id="share" role="button" tabindex="0">分享码添加</span>
        <div class="mk" id="mk" role="button" tabindex="0">创建任务</div>
      </div>`;
  }

  _bindDiscover() {
    this.querySelectorAll(".sort").forEach(s => {
      const act = () => {
        this._sort = s.dataset.s;
        this.querySelectorAll(".sort").forEach(x =>
          x.className = "sort" + (x.dataset.s === this._sort ? " on" : ""));
      };
      this._a11y(s, s.textContent, act);
      s.addEventListener("click", act);
    });
    this.querySelectorAll(".item").forEach(it => {
      const p = this._presets()[Number(it.dataset.i)];
      const act = () => this._applyPreset(p);
      this._a11y(it, p.name, act);
      it.addEventListener("click", act);
    });
    const mk = this.querySelector("#mk");
    if (mk) { const a = () => { this._tab = "create"; this._render(); };
      this._a11y(mk, "创建任务", a); mk.addEventListener("click", a); }
    const sh = this.querySelector("#share");
    if (sh) { const a = () => this._toast("分享码需在理想 App 内使用（云端功能）");
      this._a11y(sh, "分享码添加", a); sh.addEventListener("click", a); }
  }

  /* ── 我的任务 ── */
  _mineHtml() {
    const list = this._myTasks();
    if (!list.length) {
      return `<div class="empty">还没有任务<br>
        <span style="font-size:12px">到「发现」里选一个模板，或自己创建</span></div>
        <div class="bottom"><div class="mk" id="mk2" role="button" tabindex="0">创建任务</div></div>`;
    }
    return `<div class="list">${list.map(t => `
      <div class="item${t.on ? " on" : ""}" data-eid="${t.eid}">
        <div class="ic" style="background:${t.on ? "#0A58F622" : "#8E8E9322"}">
          <img src="${__iconBase}/ic_home_control.webp" onerror="__lxIconFallback(this)" alt=""></div>
        <div class="tx">
          <div class="n">${t.alias}</div>
          <div class="a">${t.on ? "已启用" : "已停用"}${t.last ? " · 上次 " + String(t.last).slice(0, 16) : ""}</div>
        </div>
        <div class="ar">›</div>
      </div>`).join("")}</div>
      <div class="bottom"><div class="mk" id="mk3" role="button" tabindex="0">创建任务</div></div>`;
  }

  _bindMine() {
    this.querySelectorAll(".item").forEach(it => {
      const eid = it.dataset.eid;
      const act = async () => {
        try {
          await this._hass.callService("automation", this._hass.states[eid].state === "on" ? "turn_off" : "turn_on",
            { entity_id: eid });
          this._toast("已切换", "ok"); this._render();
        } catch (e) { this._toast("操作失败", "err"); }
      };
      this._a11y(it, it.querySelector(".n").textContent, act);
      it.addEventListener("click", act);
    });
    const mk = this.querySelector("#mk2") || this.querySelector("#mk3");
    if (mk) { const a = () => { this._tab = "create"; this._render(); };
      this._a11y(mk, "创建任务", a); mk.addEventListener("click", a); }
  }

  /* ── 创建 ── */
  _createHtml() {
    const d = this._draft;
    const trg = d && d.trigger ? `<div class="chips"><div class="chip">
        <span>${this._describeTrigger(d.trigger)}</span>
        <span class="x" data-del="t">×</span></div></div>` : "";
    const act = d && d.action && d.action.length ? `<div class="chips">
        ${d.action.map((a, i) => `<div class="chip">
          <span>${this._describeAction(a)}</span>
          <span class="x" data-del="a" data-i="${i}">×</span></div>`).join("")}</div>` : "";
    const canConfirm = !!(d && d.name && d.action && d.action.length);
    return `
      <div class="create">
        <div class="field">
          <input class="nameinput" id="tname" placeholder="任务名称"
            value="${d && d.name ? d.name : ""}" aria-label="任务名称">
        </div>
        <div class="field">
          <div class="lbl">如果</div>
          <div class="hint">发生以下情况时，任务将自动运行。不添加时，任务将手动运行</div>
          ${trg || `<div class="addbox" id="addtrg" role="button" tabindex="0">
            <div class="p">＋</div><div class="t">添加</div></div>`}
        </div>
        <div class="field">
          <div class="lbl">就执行</div>
          <div class="hint">执行哪些操作？</div>
          ${act || `<div class="addbox" id="addact" role="button" tabindex="0">
            <div class="p">＋</div><div class="t">添加</div></div>`}
        </div>
        <div class="confirm${canConfirm ? "" : " dis"}" id="confirm"
          role="button" tabindex="0">确定</div>
      </div>`;
  }

  _bindCreate() {
    if (!this._draft) this._draft = { name: "", trigger: null, action: [] };
    const nm = this.querySelector("#tname");
    if (nm) nm.addEventListener("input", (e) => { this._draft.name = e.target.value; });

    const at = this.querySelector("#addtrg");
    if (at) { const a = () => this._pickTrigger();
      this._a11y(at, "添加触发条件", a); at.addEventListener("click", a); }
    const aa = this.querySelector("#addact");
    if (aa) { const a = () => this._pickAction();
      this._a11y(aa, "添加操作", a); aa.addEventListener("click", a); }

    this.querySelectorAll("[data-del]").forEach(x => {
      const a = () => {
        if (x.dataset.del === "t") this._draft.trigger = null;
        else this._draft.action.splice(Number(x.dataset.i), 1);
        this._render();
      };
      this._a11y(x, "删除", a); x.addEventListener("click", a);
    });

    const cf = this.querySelector("#confirm");
    if (cf) {
      const a = () => {
        if (cf.className.includes("dis")) {
          this._toast("请填写任务名称并至少添加一个操作", "err"); return;
        }
        this._save();
      };
      this._a11y(cf, "确定", a); cf.addEventListener("click", a);
    }
  }

  _describeTrigger(t) {
    if (t.platform === "state") {
      const s = this._hass && this._hass.states[t.entity_id];
      const nm = s ? (s.attributes.friendly_name || t.entity_id) : t.entity_id;
      return `${nm} 变为「${t.to}」${t.for ? " 持续 " + this._forText(t.for) : ""}`;
    }
    if (t.platform === "numeric_state") {
      const s = this._hass && this._hass.states[t.entity_id];
      const nm = s ? (s.attributes.friendly_name || t.entity_id) : t.entity_id;
      const cmp = t.above != null ? `高于 ${t.above}` : `低于 ${t.below}`;
      return `${nm} ${cmp}`;
    }
    if (t.platform === "time") return `每天 ${t.at}`;
    return JSON.stringify(t).slice(0, 40);
  }
  _forText(f) {
    const m = String(f).match(/(\d+):(\d+):(\d+)/);
    if (!m) return f;
    const h = +m[1], mi = +m[2];
    return h ? `${h} 小时` : `${mi} 分钟`;
  }
  _describeAction(a) {
    const svc = a.service || "";
    const tgt = (a.target && a.target.entity_id) || (a.data && a.data.entity_id) || "";
    const s = this._hass && this._hass.states[tgt];
    const nm = s ? (s.attributes.friendly_name || tgt) : tgt;
    const MAP = { "climate.turn_on": "开启空调", "climate.turn_off": "关闭空调",
      "switch.turn_on": "开启", "switch.turn_off": "关闭",
      "cover.close_cover": "关闭", "cover.open_cover": "打开",
      "lock.lock": "上锁", "lock.unlock": "解锁",
      "persistent_notification.create": "发送通知" };
    return `${svc} ${MAP[svc] ? "（" + MAP[svc] + "）" : ""} ${nm}`.trim();
  }

  /** 触发条件选择（简化为常用几项） */
  async _pickTrigger() {
    // ★ 优先用服务端字典（86 条件 + 参数模板）；取不到则回退下面的简表
    if (await this._ensureDict()) {
      const r = await this._pickFromDict("选择触发条件", "conditions");
      if (r) { this._draft.trigger = { platform: "state", entity_id: this._eid("status"), to: r.type, params: r.payload }; }
      return;
    }
    const OPTS = [
      { label: "驻车后", t: { platform: "state", entity_id: this._eid("status"), to: "已驻车（P 档）", for: "00:05:00" } },
      { label: "开始行驶", t: { platform: "state", entity_id: this._eid("status"), to: "行驶中" } },
      { label: "车辆上锁", t: { platform: "state", entity_id: this._eid("lock"), to: "locked" } },
      { label: "电量低于 20%", t: { platform: "numeric_state", entity_id: this._eid("battery"), below: 20 } },
      { label: "车内温度高于 30°C", t: { platform: "numeric_state", entity_id: this._eid("room_temp"), above: 30 } },
      // ★ 2026-10-11 与动作列表一致地过滤：实体不存在就别给这个选项，
      //   否则用户选了 → 任务创建失败（服务端找不到该 entity_id）
    ].filter(o => o.t && o.t.entity_id && this._st(o.t.entity_id));
    if (!OPTS.length) { this._toast("这台车暂无可用触发条件（缺少状态实体）", "err"); return; }
    const pick = await this._choose("选择触发条件", OPTS.map(o => o.label));
    if (pick == null) return;
    this._draft.trigger = OPTS[pick].t;
    this._render();
  }

  async _pickAction() {
    if (await this._ensureDict()) {
      const r = await this._pickFromDict("选择操作", "actions");
      if (r) this._draft.action.push(r.payload);
      return;
    }
    const act = this._eid("ac"), lock = this._eid("lock"), sentry = this._eid("sentry");
    const OPTS = [
      { label: "开启空调", a: act ? { service: "climate.turn_on", target: { entity_id: act } } : null },
      { label: "关闭空调", a: act ? { service: "climate.turn_off", target: { entity_id: act } } : null },
      { label: "开启哨兵模式", a: sentry ? { service: "switch.turn_on", target: { entity_id: sentry } } : null },
      { label: "关闭哨兵模式", a: sentry ? { service: "switch.turn_off", target: { entity_id: sentry } } : null },
      { label: "车辆上锁", a: lock ? { service: "lock.lock", target: { entity_id: lock } } : null },
      { label: "发送通知", a: { service: "persistent_notification.create",
          data: { title: "理想 L6", message: "任务已触发" } } },
    ].filter(o => o.a);
    const pick = await this._choose("选择操作", OPTS.map(o => o.label));
    if (pick == null) return;
    this._draft.action.push(OPTS[pick].a);
    this._render();
  }

  /** 轻量选择器（替代 window.prompt —— 后者在 HA 里体验差） */
  /**
   * 拉取字典（一次即可，缓存在实例上）。
   * ★ 取不到时静默返回 false —— 调用方回退到旧的硬编码简表，
   *   **不让用户看到一个空的"添加条件"表单**（那会像坏了）。
   */
  async _ensureDict() {
    if (this._dictCache) return true;
    if (this._dictTried) return false;          // 本次会话已试过，不重复打
    this._dictTried = true;
    try {
      const res = await fetch("/lixiang_auto/task-dict.json");
      const j = await res.json();
      if (j && j.ok && Array.isArray(j.conditions) && j.conditions.length) {
        this._dictCache = j;
        return true;
      }
    } catch (e) {
      // 忽略：回退旧简表
    }
    return false;
  }

  /**
   * ★ 2026-10-11 字典驱动：从服务端下发的 condition-and-action 字典构建条件/动作列表。
   *   取不到时返回 null（调用方回退到旧的硬编码简表，不让用户看到空表单）。
   *   字典结构（见 task_dict.py）：classification → items[{type,source,params[]}]
   */
  _dict(kind) {
    // ★ 卡片拿不到 coordinator → 字典经 REST 视图暴露（/lixiang_auto/task-dict.json）
    const d = this._dictCache || null;
    if (!d) return null;
    const groups = d[kind] || [];
    if (!groups.length) return null;
    return groups.map(g => ({
      cls: g.classification,
      label: _DICT_CLS_LABEL[g.classification] || g.classification,
      items: (g.items || []).map(it => ({
        type: it.type,
        label: _DICT_ITEM_LABEL[it.type] || it.type,
        source: it.source,
        params: it.params || [],
      })),
    })).filter(g => g.items.length);
  }

  /** 该条目是否需要参数表单（没有 params 就是选完即用）。 */
  static _needsForm(item) { return Array.isArray(item.params) && item.params.length > 0; }

  /**
   * 两级选择：先选分类，再选条目；带参数的在第二步后追加参数表单。
   * @returns {Promise<null | {type:string, t:object, a:object}>}
   */
  _pickFromDict(title, kind, typeKey) {
    const groups = this._dict(kind);
    if (!groups) return Promise.resolve(null);
    return (async () => {
      // ① 选分类
      const gi = await this._choose(title, groups.map(g => g.label));
      if (gi == null) return null;
      const g = groups[gi];
      // ② 选条目
      const ii = await this._choose(g.label, g.items.map(i => i.label));
      if (ii == null) return null;
      const item = g.items[ii];
      // ③ 需要参数 → 生成表单
      let vals = {};
      if (item.params.length) {
        vals = await this._fillParams(item);
        if (vals === null) return null;          // 用户取消
      }
      const body = {};
      for (const [k, v] of Object.entries(vals)) body[k] = v;
      return { type: item.type, payload: body, source: item.source,
               text: `${g.label} · ${item.label}` };
    })();
  }

  /**
   * 按参数模板生成表单。
   * ★ 支持的控件类型（来自实测字典）：
   *   singleChoiceList / multiChoiceList → 单选/多选按钮组
   *   singleColumnSelector            → 数值选择（滚轮/滑杆）
   *   默认（无 value）→ 文本输入
   * 未知类型不猜：退回文本输入并保留原始 key（服务端仍可能接受）。
   */
  _fillParams(item) {
    return new Promise((resolve) => {
      const ov = document.createElement("div");
      ov.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:21;
        display:flex;align-items:flex-end;justify-content:center;`;
      const sheet = document.createElement("div");
      sheet.style.cssText = `background:var(--lx-bg);color:var(--lx-t1);width:100%;
        max-width:460px;border-radius:20px 20px 0 0;padding:16px 0 24px;
        font-family:inherit;max-height:78vh;overflow:auto;`;
      const vals = {};
      const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
      const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ESC_MAP[c]);

      const rows = item.params.map((p, i) => {
        const key = p.key;
        const label = p.label || key;
        const type = p.type || "";
        const opts = Array.isArray(p.value) ? p.value : null;
        if (type.includes("ChoiceList") && opts) {
          // 单选按钮组（多选暂按单选，取第一个匹配 —— ★ 不猜多选语义）
          const multi = type.includes("multi");
          vals[key] = p.defaultValue != null ? p.defaultValue
                    : (multi && Array.isArray(p.defaultValue) ? p.defaultValue[0] : opts[0]);
          return `<div style="padding:10px 20px">
            <div style="font-size:12.5px;color:var(--lx-t3);margin-bottom:7px">${esc(label)}</div>
            <div data-p="${i}" data-key="${esc(key)}" data-multi="${multi}"
                 style="display:flex;flex-wrap:wrap;gap:7px">
              ${opts.map(o => `<span data-v="${esc(o)}" style="padding:6px 12px;border-radius:9px;
                 font-size:13px;border:1px solid var(--lx-line);cursor:pointer">${esc(o)}</span>`).join("")}
            </div></div>`;
        }
        if (type === "singleColumnSelector" && opts) {
          // 数值：默认取 defaultValue（找不到则取中间值）
          let init = p.defaultValue;
          const hit = opts.some((n) => String(n) === String(init));
          if (init == null || !hit) init = opts[Math.floor(opts.length / 2)];
          vals[key] = init;
          return `<div style="padding:10px 20px">
            <div style="font-size:12.5px;color:var(--lx-t3);margin-bottom:7px">${esc(label)}</div>
            <input data-p="${i}" data-key="${esc(key)}" data-kind="num"
              value="${esc(init)}" inputmode="decimal"
              style="width:100%;padding:11px 12px;border-radius:10px;font-size:15px;
                     border:1px solid var(--lx-line);background:var(--lx-card);color:var(--lx-t1)">
            <div style="font-size:11px;color:var(--lx-t3);margin-top:5px">可选：${esc(opts[0])} ~ ${esc(opts[opts.length-1])}</div>
          </div>`;
        }
        // 兜底：文本输入（不猜语义，保留原始 key）
        vals[key] = p.defaultValue != null ? p.defaultValue : "";
        return `<div style="padding:10px 20px">
          <div style="font-size:12.5px;color:var(--lx-t3);margin-bottom:7px">${esc(label)}</div>
          <input data-p="${i}" data-key="${esc(key)}" data-kind="txt" value="${esc(vals[key])}"
            style="width:100%;padding:11px 12px;border-radius:10px;font-size:15px;
                   border:1px solid var(--lx-line);background:var(--lx-card);color:var(--lx-t1)">
        </div>`;
      }).join("");

      sheet.innerHTML = `<div style="font-size:16px;font-weight:500;padding:0 20px 6px">${esc(item.label)}</div>
        ${rows}
        <div style="display:flex;gap:10px;padding:14px 20px 0">
          <div id="ok" style="flex:1;text-align:center;padding:13px 0;border-radius:12px;
               background:var(--lx-blue);color:#fff;font-size:15px;cursor:pointer">确定</div>
          <div id="cx" style="flex:1;text-align:center;padding:13px 0;border-radius:12px;
               font-size:15px;color:var(--lx-t3);border:1px solid var(--lx-line);cursor:pointer">取消</div>
        </div>`;
      ov.appendChild(sheet);
      document.body.appendChild(ov);

      // 选项高亮 + 单选
      sheet.querySelectorAll("[data-p]").forEach((box) => {
        const key = box.dataset.key;
        const multi = box.dataset.multi === "true";
        if (box.tagName === "INPUT") {
          box.addEventListener("input", () => { vals[key] = box.value; });
          return;
        }
        const paint = () => box.querySelectorAll("[data-v]").forEach(el => {
          const on = String(el.dataset.v) === String(vals[key]);
          el.style.background = on ? "var(--lx-blue)" : "transparent";
          el.style.color = on ? "#fff" : "";
        });
        box.querySelectorAll("[data-v]").forEach(el => {
          const v = el.dataset.v;
          const a = () => {
            if (!multi) vals[key] = v;                 // ★ 不猜多选语义
            else {
              const cur = Array.isArray(vals[key]) ? vals[key] : [vals[key]];
              const i = cur.indexOf(v);
              if (i >= 0) cur.splice(i, 1); else cur.push(v);
              vals[key] = cur;
            }
            paint();
          };
          this._a11y(el, String(v), a);
          el.addEventListener("click", a);
        });
        paint();
      });

      const close = (r) => { ov.remove(); resolve(r); };
      const ok = () => {
        sheet.querySelectorAll("input[data-kind]").forEach((inp) => {
          const key = inp.dataset.key;
          vals[key] = inp.dataset.kind === "num" ? Number(inp.value) : inp.value;
        });
        close(vals);
      };
      sheet.querySelector("#ok").addEventListener("click", ok);
      sheet.querySelector("#cx").addEventListener("click", () => close(null));
      this._a11y(sheet.querySelector("#ok"), "确定", ok);
    });
  }

  _choose(title, labels) {
    return new Promise((resolve) => {
      const ov = document.createElement("div");
      ov.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:20;
        display:flex;align-items:flex-end;justify-content:center;`;
      const sheet = document.createElement("div");
      sheet.style.cssText = `background:var(--lx-bg);color:var(--lx-t1);width:100%;
        max-width:460px;border-radius:20px 20px 0 0;padding:18px 0 26px;
        font-family:inherit;max-height:70vh;overflow:auto;`;
      sheet.innerHTML = `<div style="font-size:16px;font-weight:500;padding:0 20px 14px">${title}</div>`
        + labels.map((l, i) => `<div data-i="${i}" style="padding:15px 20px;
            font-size:15px;border-top:1px solid var(--lx-line);cursor:pointer">${l}</div>`).join("")
        + `<div id="cx" style="padding:15px 20px;font-size:15px;color:var(--lx-t3);
            border-top:8px solid var(--lx-card);cursor:pointer;text-align:center">取消</div>`;
      const close = (v) => { ov.remove(); resolve(v); };
      sheet.querySelectorAll("[data-i]").forEach(el => {
        const i = Number(el.dataset.i);
        const a = () => close(i);
        this._a11y(el, labels[i], a);
        el.addEventListener("click", a);
      });
      const cx = sheet.querySelector("#cx");
      const ca = () => close(null);
      this._a11y(cx, "取消", ca);
      cx.addEventListener("click", ca);
      ov.appendChild(sheet);
      ov.addEventListener("click", (e) => { if (e.target === ov) close(null); });
      this.appendChild(ov);
    });
  }

  async _applyPreset(p) {
    const id = "lx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const cfg = {
      alias: p.name, description: p.desc,
      trigger: [p.trigger], action: p.action, mode: "single",
    };
    try {
      await this._saveCfg(id, cfg);
      this._toast(`已创建「${p.name}」`, "ok", 3200);
      this._tab = "mine"; this._render();
    } catch (e) {
      this._toast("创建失败：" + ((e && e.message) || "未知"), "err", 4000);
    }
  }

  async _save() {
    const d = this._draft;
    const id = "lx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const cfg = { alias: d.name, trigger: d.trigger ? [d.trigger] : [], action: d.action, mode: "single" };
    try {
      await this._saveCfg(id, cfg);
      this._toast(`已创建「${d.name}」`, "ok", 3200);
      this._draft = null;
      this._tab = "mine"; this._render();
    } catch (e) {
      this._toast("创建失败：" + ((e && e.message) || "未知"), "err", 4000);
    }
  }

  async _saveCfg(id, cfg) {
    const h = this._hass;
    const tok = h.auth && h.auth.data ? h.auth.data.access_token : null;
    const res = await fetch(`/api/config/automation/config/${id}`, {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" },
        tok ? { Authorization: "Bearer " + tok } : {}),
      body: JSON.stringify(cfg),
    });
    if (!res.ok) {
      const t = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${t.slice(0,80)}`);
    }
    return res.json().catch(() => ({}));
  }

  _update() {
    if (!this._built) return;
    // 首屏与切换 tab 时重绘（保持输入内容：create 页由 _draft 承载）
    this._render();
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangTaskPage);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "任务大师（HA 版）",
  description: "用 App 的交互创建 HA 自动化：模板库 + 如果/就执行 + 我的任务",
  preview: true,
});
