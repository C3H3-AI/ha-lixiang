/**
 * 理想汽车 · 总入口卡片（一张卡片承载全部页面）
 *
 * ★★ 2026-10-11 为什么做这个
 * ------------------------------------------------------------------
 * 原先用户要用上这套 UI 需要：
 *   · 注册 **14 个资源**（13 张卡片 + auto-bind 引擎）
 *   · 建 **13 个 dashboard 视图**（每张卡片一个）
 *   · 加 13 次卡片
 *   = 27 次手工操作 —— 普通用户根本折腾不下来。
 *
 * 现在只需三步：
 *   ① 注册 1 个资源（本文件）
 *   ② 建 1 个视图
 *   ③ 加 1 张卡片：`type: custom:lixiang-app`
 *
 * 工作原理
 * --------
 * · 本卡片在内部**动态 import 全部子卡片**（用 import.meta.url 解析相对路径，
 *   所以无论从 /lixiang_auto/… 还是 /local/lixiang-cards/… 加载都能找到同级文件）
 * · 子卡片仍是标准自定义元素，本卡片按需创建并切换显示
 * · 导航：子卡片派发 `lx-navigate` 事件 → 本卡片拦截并切换内部页面
 *   （子卡片保留了「未被拦截则回退 HA 路由」的旧行为，所以**多视图用法仍然可用**）
 *
 * 配置
 * ----
 * ```yaml
 * type: custom:lixiang-app
 * # 可选：起始页（默认 app）
 * page: app
 * # 可选：多车时指定
 * vin: HLX32XXXXXXXXXXXX
 * # 可选：传给子卡片的原始配置（高级用法）
 * child: { ... }
 * ```
 */

const CARD_TAG = "lixiang-app";

/** 内部页面表：路径片段 → 子卡片自定义元素名 */
const PAGES = {
  app: "lixiang-app-home",
  charge: "lixiang-charge-page",
  energy: "lixiang-energy-page",
  health: "lixiang-health-page",
  setting: "lixiang-setting-page",
  scene: "lixiang-scene-page",
  climate: "lixiang-climate-page",
  seat: "lixiang-seat-page",
  location: "lixiang-location-page",
  vinfo: "lixiang-vehicle-info-page",
  task: "lixiang-task-page",
  ad: "lixiang-ad-page",
  bindings: "lixiang-bindings-card",
};

/** 全部子卡片文件名（用于动态加载） */
const CARD_FILES = Object.values(PAGES);

/** 加载状态：全局一次即可（多个总卡片实例共享） */
let __loading = null;

function _loadCards() {
  if (__loading) return __loading;
  // ★ 用 import.meta.url 解析同级目录 —— 兼容 /lixiang_auto/… 与 /local/… 两种部署
  const base = new URL(".", import.meta.url).href;
  __loading = Promise.all(
    CARD_FILES.map((name) =>
      import(/* @vite-ignore */ `${base}${name}.js`).catch((e) => {
        // 单个卡片加载失败不应拖垮整体：其余页面照常可用
        console.warn(`[lixiang-app] 子卡片加载失败: ${name}`, e);
      })
    )
  ).then(() => {
    // 自动绑定引擎（可选，缺失时子卡片会自行降级）
    return import(/* @vite-ignore */ `${base}lixiang-auto-bind.js`).catch(() => {});
  });
  return __loading;
}

class LixiangApp extends HTMLElement {
  constructor() {
    super();
    this._built = false;
    this._instances = {};   // 元素名 → 已创建的子卡片
    this._current = null;   // 当前页面 key
    this._mount = null;
  }

  setConfig(config) {
    this._config = config || {};
  }

  /** 在多视图用法下，HA 会把 URL 变化转成 hass 更新；这里同步一下内部页 */
  set hass(h) {
    this._hass = h;
    if (!this._built) {
      this._build();
      return;
    }
    this._syncFromUrl();
    this._pushHass();
  }

  get hass() { return this._hass; }

  /** 子卡片读取父级配置里的 vin 等 */
  get config() { return this._config || {}; }

  async _build() {
    if (this._built) return;
    this._built = true;

    // 事件：子卡片请求导航（cancelable → preventDefault 表示"父级已处理"）
    this.addEventListener("lx-navigate", (e) => {
      const key = this._keyOf(e.detail && e.detail.path);
      if (!key) return;           // 不认识 → 不拦截，让子卡片回退 HA 路由
      e.preventDefault();
      this.show(key);
    });

    // ★ 导航拦截：子卡片一律用 `history.pushState(null,"",p)` + `location-changed`
    //   跳转（12 个文件写法完全一致）。与其改 12 个文件，不如在这里把
    //   **能映射到内部页面的 URL** 拦下来做内部切换 —— 子卡片零改动。
    //   非本卡片的 URL（HA 自己的导航）原样放行，且断开时恢复原函数。
    this._installNavHook();

    // 容器
    this._mount = document.createElement("div");
    this._mount.style.cssText = "display:block;";
    this.appendChild(this._mount);

    // 先显示加载态，避免白屏
    this._mount.innerHTML =
      '<div style="padding:24px;text-align:center;color:var(--lx-t3,#999);'
      + 'font-size:13px">正在加载理想汽车卡片…</div>';

    await _loadCards();

    const start = this._config && this._config.page;
    this.show(PAGES[start] ? start : this._initialKey());
  }

  _installNavHook() {
    const self = this;
    if (!window.__lxNavHook) {
      const orig = history.pushState.bind(history);
      window.__lxNavOrigPush = orig;
      window.__lxNavRefs = 0;
      window.__lxNavTargets = new Set();
      window.__lxNavHook = function (state, title, url) {
        const path = String(url == null ? "" : url);
        for (const t of window.__lxNavTargets) {
          const k = t._keyOf(path);
          if (k) {
            // 内部处理：不改 URL（避免 HA 去切换不存在的视图）
            t.show(k);
            return undefined;
          }
        }
        return orig(state, title, url);
      };
      history.pushState = window.__lxNavHook;
    }
    window.__lxNavRefs += 1;
    window.__lxNavTargets.add(this);
  }

  _removeNavHook() {
    if (!window.__lxNavHook) return;
    window.__lxNavTargets.delete(this);
    window.__lxNavRefs -= 1;
    if (window.__lxNavRefs <= 0 && window.__lxNavOrigPush) {
      history.pushState = window.__lxNavOrigPush;
      window.__lxNavHook = null;
      window.__lxNavTargets = new Set();
    }
  }

  disconnectedCallback() {
    this._removeNavHook();
  }

  /** 从 URL 推断初始页（URL 是 /lixiang/charge 或卡片所在视图的 path） */
  _initialKey() {
    const k = this._keyOf(window.location.pathname);
    return k || "app";
  }

  /** 把路径片段映射到页面 key（兼容 "/lixiang/charge" 与 "charge"） */
  _keyOf(path) {
    if (!path || typeof path !== "string") return null;
    const seg = path.split("/").filter(Boolean).pop();
    if (seg && PAGES[seg]) return seg;
    const last = path.split("/").filter(Boolean);
    for (let i = last.length - 1; i >= 0; i--) {
      if (PAGES[last[i]]) return last[i];
    }
    return null;
  }

  /** 切到某个页面（key 必须是 PAGES 的键） */
  show(key) {
    if (!PAGES[key] || !this._mount) return;
    if (this._current === key) return;
    this._current = key;

    // 只创建一次，之后复用（保留子卡片的内部状态，如滚动位置/已展开月份）
    const tag = PAGES[key];
    let el = this._instances[tag];
    if (!el) {
      el = document.createElement(tag);
      try {
        el.setConfig(this._childConfig());
      } catch (e) {
        console.warn(`[lixiang-app] ${tag} setConfig 失败`, e);
      }
      this._instances[tag] = el;
    }
    this._mount.replaceChildren(el);

    // 同步 hass（子卡片依赖它渲染）
    this._pushHass();
  }

  _childConfig() {
    const c = this._config || {};
    const base = Object.assign({}, c.child || {});
    if (c.vin) base.vin = c.vin;
    return base;
  }

  _pushHass() {
    if (!this._hass) return;
    Object.values(this._instances).forEach((el) => {
      try {
        el.hass = this._hass;
      } catch (e) {
        // 单个子卡片异常不影响其他
        console.warn("[lixiang-app] 传递 hass 失败", e);
      }
    });
  }

  /** 多视图用法：URL 变了就同步内部页（本卡片仍在同一视图内时也生效） */
  _syncFromUrl() {
    const k = this._keyOf(window.location.pathname);
    if (k && k !== this._current) this.show(k);
  }

  getCardSize() { return 12; }

  static getStubConfig() { return {}; }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangApp);

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "理想汽车 · 全部页面",
  description: "一张卡片承载理想 App 风格的全部页面（首页/充电/能耗/空调/座椅/位置/设置/情景/任务等）",
  preview: false,
});