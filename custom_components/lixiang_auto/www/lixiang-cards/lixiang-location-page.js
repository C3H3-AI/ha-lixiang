/**
 * lixiang-location-page —— 车辆位置（二级页，对齐 App）
 *
 * App 实测结构（截图 1260×2844 @3x）：
 *   地图占 64%，车辆图标居中，左下「闪灯/鸣笛」浮动按钮
 *   地址卡：完整地址 + 距您 xx m + 导航按钮
 *   驻车照片：3 路（俯视/前/后）+ 时间 + 重新拍照
 *
 * 实体：
 *   device_tracker.车辆位置（lat/lon）
 *   button.闪灯 / 鸣笛 / 远程拍照
 *   sensor.360 拍照状态 / 拍照信息
 *
 * 能力边界：
 *   ✅ 驻车照片可显示（2026-10-03 打通）：
 *      VSS 拍照时间 → 构造 5 路 OSS key → lixiang_auto.get_svm_photo
 *      换签名 URL → <img>。链路逆向自 5 月抓包。
 *   ✅ 闪灯/鸣笛 可触发
 *   ⚠️ 触发拍照（button.远程拍照）实测 2009 —— 与充电同因，需 JOB 通道
 */

const CARD_TAG = "lixiang-location-page";
const DEFAULT_ICON_BASE = "/local/lixiang-icons";
const DEFAULT_FONT_BASE = "/local/lixiang-fonts";
let __iconBase = DEFAULT_ICON_BASE;   // setConfig 可覆盖
let __fontBase = DEFAULT_FONT_BASE;

const STYLE = `
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_regular.ttf"); font-weight:400; font-display:swap; }
  @font-face { font-family:"Licium"; src:url("${__fontBase}/licium_medium.ttf");  font-weight:500; font-display:swap; }
  @font-face { font-family:"LxNum";  src:url("${__fontBase}/roboto_medium_numbers.ttf"); font-display:swap; }
  :host { display:block;
    --lx-blue:#0A58F6; --lx-t1:#1A1A1A; --lx-t2:#666; --lx-t3:#9A9A9A;
    --lx-green:#34C759; --lx-orange:#FF9500;
    --lx-card:#F7F7F9; --lx-bg:#FFF; --lx-line:#F0F0F2; }
  @media (prefers-color-scheme: dark) {
    :host { --lx-t1:#F2F2F7; --lx-t2:#AEAEB2; --lx-t3:#8E8E93;
            --lx-card:#1C1C1E; --lx-bg:#000; --lx-line:#2C2C2E; --lx-blue:#4C9AFF; }
  }
  .root { background:var(--lx-bg); color:var(--lx-t1); padding-bottom:20px;
    font-family:"Licium",-apple-system,"PingFang SC",sans-serif; }

  /* ── 地图区 ── */
  .mapwrap { position:relative; height:340px; background:#E8EEF4; overflow:hidden; }
  /* ── 自建地图（高德瓦片，免 key/免登录）── */
  .tiles { position:absolute; inset:0; cursor:grab; touch-action:none; }
  .tiles.grabbing { cursor:grabbing; }
  .tiles img { position:absolute; width:256px; height:256px; user-select:none;
               pointer-events:none; -webkit-user-drag:none; }
  /* ★ 2026-10-03：车标改为【小车图形】（对齐 App）——
     原来是个 36px 大圆点，太大且不像车，无法表达"车辆位置"。
     小车用已有的 icon_car_loc.webp，尺寸收小到 22px。 */
  .puck { position:absolute; width:22px; height:22px; margin:-11px 0 0 -11px;
          display:flex; align-items:center; justify-content:center;
          pointer-events:none; z-index:4; }
  .puck img { width:22px; height:22px;
              filter:drop-shadow(0 1px 3px rgba(0,0,0,.45)); }
  .mapctl { position:absolute; right:12px; bottom:12px; display:flex;
            flex-direction:column; gap:6px; z-index:5; }
  .mapctl span { width:32px; height:32px; border-radius:8px;
                 background:rgba(255,255,255,.96); display:flex;
                 align-items:center; justify-content:center; font-size:17px;
                 color:#333; cursor:pointer; box-shadow:0 1px 4px rgba(0,0,0,.16);
                 user-select:none; }
  .mapctl span:active { transform:scale(.93); }
  .mapwrap iframe { width:100%; height:100%; border:0; }
  .mapwrap .ph { position:absolute; inset:0; display:flex; flex-direction:column;
                 align-items:center; justify-content:center; gap:10px;
                 font-size:12.5px; color:var(--lx-t3); text-align:center; padding:0 30px; }
  .mapwrap .ph .car { width:44px; height:62px; }
  .back { position:absolute; left:14px; top:14px; width:38px; height:38px;
          border-radius:50%; background:rgba(255,255,255,.95); display:flex;
          align-items:center; justify-content:center; cursor:pointer; z-index:3;
          box-shadow:0 1px 5px rgba(0,0,0,.12); }
  .back img { width:19px; height:19px; opacity:.75; }
  /* 浮动按钮 */
  .floats { position:absolute; left:14px; bottom:14px; display:flex; gap:9px; z-index:3; }
  .fbtn { display:inline-flex; align-items:center; gap:6px; font-size:13px;
          padding:9px 15px; border-radius:22px; background:rgba(255,255,255,.97);
          box-shadow:0 2px 8px rgba(0,0,0,.13); cursor:pointer;
          transition:transform .13s; white-space:nowrap; }
  .fbtn:active { transform:scale(.94); }
  .fbtn img { width:17px; height:17px; }
  .fbtn.busy { opacity:.55; }

  /* ── 地址卡 ── */
  .addr { padding:16px 20px 14px; display:flex; align-items:flex-start; gap:12px; }
  .addr .tx { flex:1; min-width:0; }
  .addr .a { font-size:16px; font-weight:500; line-height:1.4; }
  .addr .d { font-size:13px; color:var(--lx-t3); margin-top:6px; }
  .nav { width:46px; height:46px; border-radius:50%; background:var(--lx-card);
         display:flex; align-items:center; justify-content:center; cursor:pointer;
         flex:0 0 auto; transition:transform .13s; }
  .nav:active { transform:scale(.92); }
  .nav img { width:22px; height:22px; }

  /* ── 驻车照片 ── */
  .sec { padding:12px 0 0; border-top:8px solid var(--lx-card); }
  .sechd { display:flex; align-items:center; gap:10px; padding:14px 20px 10px; }
  .sechd .t { font-size:16px; font-weight:500; }
  .sechd .ts { font-size:12.5px; color:var(--lx-t3); margin-top:3px; }
  .sechd .ra { margin-left:auto; display:inline-flex; align-items:center; gap:6px;
               font-size:13px; padding:8px 14px; border-radius:20px;
               background:var(--lx-card); cursor:pointer; }
  .sechd .ra img { width:16px; height:16px; }
  .photos { display:flex; gap:10px; padding:0 20px 6px; overflow-x:auto;
            scrollbar-width:none; }
  .photos::-webkit-scrollbar { display:none; }
  .ph { flex:0 0 auto; width:150px; height:100px; border-radius:12px;
        background:#2A2A2E; position:relative; overflow:hidden;
        display:flex; align-items:flex-end; }
  .ph img { width:100%; height:100%; object-fit:cover; }
  .ph .lbl { position:absolute; left:8px; top:8px; font-size:11px; color:#fff;
             background:rgba(0,0,0,.45); padding:2px 7px; border-radius:6px; }
  .ph { cursor:pointer; }
  .ph:active { transform:scale(.97); }
  .ph .zoom { position:absolute; right:6px; bottom:6px; width:20px; height:20px;
              border-radius:50%; background:rgba(0,0,0,.5); color:#fff;
              display:flex; align-items:center; justify-content:center;
              font-size:12px; line-height:1; }
  /* ── 照片大图查看（点缩略图打开）── */
  .lightbox { position:fixed; inset:0; background:rgba(0,0,0,.92); z-index:9999;
              display:none; flex-direction:column; }
  .lightbox.on { display:flex; }
  .lightbox .lbhd { display:flex; align-items:center; gap:10px;
                    padding:14px 18px; color:#fff; font-size:15px; }
  .lightbox .lbx { margin-left:auto; font-size:22px; cursor:pointer;
                   width:32px; height:32px; display:flex; align-items:center;
                   justify-content:center; border-radius:50%;
                   background:rgba(255,255,255,.14); }
  .lightbox .lbbody { flex:1; display:flex; align-items:center;
                      justify-content:center; padding:0 14px 22px; }
  .lightbox img { max-width:100%; max-height:100%; object-fit:contain;
                  border-radius:10px; }
  .lightbox .lbnav { display:flex; gap:8px; justify-content:center;
                     padding:0 0 18px; }
  .lightbox .lbnav span { padding:7px 15px; border-radius:18px;
                          background:rgba(255,255,255,.14); color:#fff;
                          font-size:13px; cursor:pointer; }
  .lightbox .lbnav span.on { background:var(--lx-blue); }
  .ph .none { position:absolute; inset:0; display:flex; align-items:center;
              justify-content:center; font-size:11px; color:rgba(255,255,255,.5);
              text-align:center; padding:0 10px; line-height:1.5; }
  .tip { padding:10px 20px 0; font-size:11.5px; color:var(--lx-t3); line-height:1.6; }
  .toast { position:fixed; left:50%; bottom:90px; transform:translate(-50%,14px);
           background:rgba(0,0,0,.84); color:#fff; font-size:13px; padding:10px 18px;
           border-radius:11px; opacity:0; pointer-events:none; transition:.22s; z-index:9; }
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
`;

class LixiangLocationPage extends HTMLElement {
  setConfig(c) { this._config = c || {}; this._busy = {}; this._built = false; }
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
  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }
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
      <div class="mapwrap" id="mapwrap">
        <div class="tiles" id="tiles"></div>
        <div class="puck" id="puck" style="display:none">
          <img src="${__iconBase}/icon_car_loc.webp" alt="车辆位置"></div>
        <div class="mapctl">
          <span id="cz-in" role="button" tabindex="0" aria-label="放大">+</span>
          <span id="cz-out" role="button" tabindex="0" aria-label="缩小">−</span>
          <span id="cz-me" role="button" tabindex="0" aria-label="回到车辆">⌖</span>
        </div>
        <div class="ph" id="mapph" style="display:none">
          <img class="car" src="${__iconBase}/icon_car_loc.webp" alt="">
          <div id="coords">定位获取中…</div>
        </div>
        <div class="back" id="back" role="button" tabindex="0" aria-label="返回">
          <img src="${__iconBase}/ic_home_return.webp" alt=""></div>
        <div class="floats">
          <div class="fbtn" id="btn-flash" role="button" tabindex="0" aria-label="闪灯">
            <img src="${__iconBase}/ic_home_lightning.png" alt="" onerror="this.style.visibility='hidden'">闪灯</div>
          <div class="fbtn" id="btn-horn" role="button" tabindex="0" aria-label="鸣笛">
            <img src="${__iconBase}/ic_home_dialogue.png" alt="" onerror="this.style.visibility='hidden'">鸣笛</div>
        </div>
      </div>

      <div class="addr">
        <div class="tx">
          <div class="a" id="v-addr">地址获取中…</div>
          <div class="d" id="v-dist"></div>
        </div>
        <div class="nav" id="btn-nav" role="button" tabindex="0" aria-label="导航到车辆">
          <img src="${__iconBase}/ic_home_navigation.webp" alt=""></div>
      </div>

      <div class="sec">
        <div class="sechd">
          <div><div class="t">驻车照片</div><div class="ts" id="v-photots">—</div></div>
          <div class="ra" id="btn-photo" role="button" tabindex="0" aria-label="重新拍照">
            <img src="${__iconBase}/ic_home_photo.png" alt="" onerror="this.style.visibility='hidden'">重新拍照</div>
        </div>
        <div class="photos" id="photos"></div>
        <div class="lightbox" id="lightbox" role="dialog" aria-modal="true"
             aria-label="驻车照片大图">
          <div class="lbhd"><span id="lb-title">驻车照片</span>
            <div class="lbx" id="lb-close" role="button" tabindex="0"
                 aria-label="关闭">×</div></div>
          <div class="lbbody"><img id="lb-img" alt=""></div>
          <div class="lbnav" id="lb-nav"></div>
        </div>
        <div class="tip">驻车照片由车辆摄像头拍摄。点击「重新拍照」后，
          照片会显示在这里（5 路：前 / 后 / 左 / 右 / 俯视）。
          图片链接约 24 小时有效，过期后需重新获取。</div>
      </div>
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

    const flash = () => this._press("btn_flash", "闪灯");
    const horn = () => this._press("btn_horn", "鸣笛");
    const photo = () => this._press("btn_photo", "远程拍照");
    [["#btn-flash", flash, "闪灯"], ["#btn-horn", horn, "鸣笛"],
     ["#btn-photo", photo, "重新拍照"]].forEach(([sel, fn, label]) => {
      const el = this.querySelector(sel); if (!el) return;
      this._a11y(el, label, fn);
      el.addEventListener("click", fn);
    });

    // 大图查看器的关闭（点遮罩空白处也关）
    const lb = this.querySelector("#lightbox");
    if (lb) {
      this._a11y(this.querySelector("#lb-close"), "关闭大图",
                 () => this._closeLightbox());
      lb.addEventListener("click", (ev) => {
        if (ev.target === lb || ev.target.classList.contains("lbbody")) {
          this._closeLightbox();
        }
      });
    }

    // 导航
    const nav = () => {
      const dt = this._st(this._eid("tracker"));
      const la = dt && dt.attributes.latitude, lo = dt && dt.attributes.longitude;
      if (la == null || lo == null) { this._toast("暂无定位", "err"); return; }
      // 用系统地图 URL scheme（手机端可唤起）
      const url = `https://uri.amap.com/marker?position=${lo},${la}&name=我的车`;
      window.open(url, "_blank");
    };
    this._a11y(this.querySelector("#btn-nav"), "导航到车辆", nav);
    this.querySelector("#btn-nav").addEventListener("click", nav);

    this._built = true;
  }

  _toast(msg, kind) {
    const t = this.querySelector(".toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { t.className = "toast"; }, 2400);
  }

  async _press(field, label) {
    const eid = this._eid(field);
    if (!eid) { this._toast(`${label} 未接入`, "err"); return; }
    if (this._busy[field]) return;
    this._busy[field] = true;
    const el = this.querySelector(field === "btn_flash" ? "#btn-flash"
              : (field === "btn_horn" ? "#btn-horn" : "#btn-photo"));
    if (el) el.classList.add("busy");
    try {
      await this._hass.callService("button", "press", { entity_id: eid });
      this._toast(`${label} 已触发`, "ok");
    } catch (e) {
      this._toast(`${label} 失败：${(e && e.message) || "未知"}`, "err");
    } finally {
      delete this._busy[field];
      if (el) el.classList.remove("busy");
    }
  }

  _update() {
    if (!this._built) return;
    const q = s => this.querySelector(s);

    // 定位
    const dt = this._st(this._eid("tracker"));
    const la = dt && dt.attributes.latitude, lo = dt && dt.attributes.longitude;
    const coords = q("#coords");
    if (la != null && lo != null) {
      coords.textContent = `${Number(la).toFixed(5)}, ${Number(lo).toFixed(5)}`;
      // ★ 2026-10-03：改用【自建地图】——直接拼高德瓦片。
      //   此前用 iframe 嵌 uri.amap.com/marker，但那是网页版，
      //   在 iframe 里会要求登录（截图里是「请按住滑块拖动」验证页）。
      //   高德瓦片本身免 key、免登录：
      //     https://webrd0{s}.is.autonavi.com/appmaptile?...&x=&y=&z=
      //   注意 HA 存 WGS84、高德瓦片是 GCJ-02，需要纠偏（见 _wgs2gcj）。
      this._initMap(la, lo);
    } else {
      coords.textContent = "暂无定位（车辆可能离线）";
    }

    // 地址（HA 无反向地理编码时显示坐标 + 提示）
    const addrState = this._txt(this._eid("address"));
    const addrEl = q("#v-addr");
    if (dt && dt.attributes.address) addrEl.textContent = dt.attributes.address;
    else if (addrState && !/^\d+$/.test(String(addrState))) addrEl.textContent = String(addrState);
    else if (la != null && lo != null) addrEl.textContent = `坐标 ${Number(la).toFixed(4)}, ${Number(lo).toFixed(4)}`;
    else addrEl.textContent = "地址不可用";

    // 距离（本机到车；浏览器定位不可用时隐藏）
    const distEl = q("#v-dist");
    if (this._myPos && la != null && lo != null) {
      const d = this._haversine(this._myPos[0], this._myPos[1], la, lo);
      distEl.textContent = d < 1000 ? `距您 ${Math.round(d)}m` : `距您 ${(d/1000).toFixed(1)}km`;
    } else distEl.textContent = "";

    // 拍照时间
    const info = this._txt(this._eid("photo_info"));
    const stt = this._txt(this._eid("photo_status"));
    q("#v-photots").textContent = info || stt || "暂无记录";

    // ★ 2026-10-03：驻车照片改为【真实图片】
    //   链路（抓包逆向）：VSS 拍照时间 → 构造 5 路 OSS key →
    //   lixiang_auto.get_svm_photo 换签名 URL → <img src>。
    //   URL 有时效，所以缓存 2 分钟（够一次浏览，又不至于显示过期图）。
    this._renderPhotos(q, info);
  }

  /** 渲染 5 路驻车照片（前/后/左/右/俯视）。 */
  async _renderPhotos(q, photoTime) {
    const box = q("#photos");
    if (!box) return;
    const ANGLES = [["Top", "俯视"], ["Front", "前"], ["Rear", "后"],
                    ["Left", "左"], ["Right", "右"]];

    // 首次：占位骨架（避免空白闪烁）
    if (!box.dataset.init) {
      box.dataset.init = "1";
      box.innerHTML = ANGLES.map(([k, lbl]) =>
        `<div class="ph" data-a="${k}"><div class="none">${lbl}视图<br>加载中…</div>
         <div class="lbl">${lbl}</div></div>`).join("");
    }

    const stamp = String(photoTime || "");
    const now = Date.now();
    if (this._phCache && this._phCache.stamp === stamp &&
        now - this._phCache.at < 120000) {
      this._paintPhotos(box, this._phCache.urls, ANGLES);
      return;
    }
    if (this._phBusy) return;
    this._phBusy = true;
    try {
      const res = await this._hass.callService(
        "lixiang_auto", "get_svm_photo",
        photoTime ? { time: photoTime } : {}, undefined, false, true);
      const payload = (res && (res.result || res.response)) || {};
      const first = Object.values(payload)[0] || {};
      const urls = first.urls || {};
      this._phCache = { stamp, urls, at: Date.now() };
      this._paintPhotos(box, urls, ANGLES, first.error);
    } catch (err) {
      this._paintPhotos(box, {}, ANGLES, String(err && err.message || err));
    } finally {
      this._phBusy = false;
    }
  }

  /** 打开大图查看器（可左右切换 5 路）。 */
  _openLightbox(curKey, curLbl, curUrl, urls, angles) {
    const lb = this.querySelector("#lightbox");
    if (!lb) return;
    // 只列出真正有图的方位
    const avail = angles.map(([k, l]) => {
      const hit = Object.entries(urls || {})
        .find(([kk]) => kk && kk.includes(`picIn${k}.jpg`));
      return hit ? [k, l, hit[1]] : null;
    }).filter(Boolean);
    if (!avail.length) return;

    const show = (idx) => {
      const [k, l, u] = avail[idx];
      const img = lb.querySelector("#lb-img");
      img.src = u;
      img.alt = `${l}视图`;
      lb.querySelector("#lb-title").textContent = `驻车照片 · ${l}`;
      lb.querySelectorAll("#lb-nav span").forEach((sp, i) =>
        sp.classList.toggle("on", i === idx));
      lb.dataset.idx = String(idx);
    };
    const nav = lb.querySelector("#lb-nav");
    nav.innerHTML = avail.map(([k, l], i) =>
      `<span data-i="${i}" role="button" tabindex="0">${l}</span>`).join("");
    nav.querySelectorAll("span").forEach((sp) => {
      sp.onclick = () => show(Number(sp.dataset.i));
    });

    const start = Math.max(0, avail.findIndex(([k]) => k === curKey));
    show(start);
    lb.classList.add("on");
    this._lbKeyHandler = (ev) => {
      if (ev.key === "Escape") { this._closeLightbox(); return; }
      const n = avail.length;
      const i = Number(lb.dataset.idx || 0);
      if (ev.key === "ArrowRight") show((i + 1) % n);
      if (ev.key === "ArrowLeft") show((i - 1 + n) % n);
    };
    document.addEventListener("keydown", this._lbKeyHandler);
    lb.querySelector("#lb-close").focus?.();
  }

  _closeLightbox() {
    const lb = this.querySelector("#lightbox");
    if (!lb) return;
    lb.classList.remove("on");
    lb.querySelector("#lb-img").src = "";   // 释放图片
    if (this._lbKeyHandler) {
      document.removeEventListener("keydown", this._lbKeyHandler);
      this._lbKeyHandler = null;
    }
  }

  /** 把 URL 填进对应方位；缺失的显示原因而不是假装有图。 */
  _paintPhotos(box, urls, angles, err) {
    const list = Object.entries(urls || {});
    angles.forEach(([key, lbl]) => {
      const cell = box.querySelector(`.ph[data-a="${key}"]`);
      if (!cell) return;
      const hit = list.find(([k]) => k && k.includes(`picIn${key}.jpg`));
      if (hit) {
        // ★ 图片可能已过期（实测 5 个月前的照片在 OSS 已 404，
        //   而签名 URL 本身仍有效）—— 加载失败要如实说明，不静默空白。
        cell.innerHTML = `<img src="${hit[1]}" alt="${lbl}视图" loading="lazy"
             style="width:100%;height:100%;object-fit:cover;border-radius:8px"
             onerror="this.parentNode.innerHTML='<div class=&quot;none&quot;>${lbl}视图<br>（图片已过期）</div><div class=&quot;lbl&quot;>${lbl}</div>'">
           <div class="lbl">${lbl}</div>
           <div class="zoom" aria-hidden="true">⤢</div>`;
        // 点缩略图 → 大图（URL 只在内存里，不落 DOM 属性）
        cell.onclick = () => this._openLightbox(key, lbl, hit[1], urls, angles);
        cell.setAttribute("role", "button");
        cell.setAttribute("tabindex", "0");
        cell.setAttribute("aria-label", `${lbl}视图，点击查看大图`);
      } else {
        const why = err ? "获取失败" : (list.length ? "该方位无图" : "尚未拍照");
        cell.innerHTML = `<div class="none">${lbl}视图<br>（${why}）</div>
           <div class="lbl">${lbl}</div>`;
      }
    });
  }

  // ── 自建地图：高德瓦片 ────────────────────────────────────────────────
  /** WGS84 → GCJ-02（大陆有 300~600m 偏移，不纠偏车标会跑偏）。 */
  _wgs2gcj(lat, lon) {
    const a = 6378245.0, ee = 0.00669342162296594323;
    const outOfChina = (la, lo) => lo < 72.004 || lo > 137.8347 || la < 0.8293 || la > 55.8271;
    if (outOfChina(lat, lon)) return [lat, lon];
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
    const sqrtMagic = Math.sqrt(magic);
    const dLat = (dLat0 * 180) / ((a * (1 - ee)) / (magic * sqrtMagic) * Math.PI);
    const dLon = (dLon0 * 180) / (a / sqrtMagic * Math.cos(radLat) * Math.PI);
    return [lat + dLat, lon + dLon];
  }

  _lonlatToTile(lat, lon, z) {
    const n = 2 ** z;
    const x = (lon + 180) / 360 * n;
    const y = (1 - Math.log(Math.tan(lat * Math.PI/180) + 1/Math.cos(lat * Math.PI/180)) / Math.PI) / 2 * n;
    return [x, y];
  }

  _initMap(la, lo) {
    const box = this.querySelector("#tiles");
    const wrap = this.querySelector("#mapwrap");
    const puck = this.querySelector("#puck");
    if (!box || !wrap || la == null || lo == null) return;
    // WGS84 → GCJ-02
    const [glat, glon] = this._wgs2gcj(Number(la), Number(lo));
    this._map = this._map || { z: 16 };
    this._map.lat = glat; this._map.lon = glon;
    this.querySelector("#mapph").style.display = "none";

    this._drawMap();
    if (!box.dataset.wired) {
      box.dataset.wired = "1";
      // 拖拽平移
      let sx = 0, sy = 0, ox = 0, oy = 0, drag = false;
      const down = (e) => {
        drag = true; box.classList.add("grabbing");
        const p = e.touches ? e.touches[0] : e;
        sx = p.clientX; sy = p.clientY; ox = this._map.px || 0; oy = this._map.py || 0;
        e.preventDefault();
      };
      const move = (e) => {
        if (!drag) return;
        const p = e.touches ? e.touches[0] : e;
        this._map.px = ox + (sx - p.clientX);
        this._map.py = oy + (sy - p.clientY);
        this._positionTiles();
        e.preventDefault();
      };
      const up = () => { drag = false; box.classList.remove("grabbing"); };
      box.addEventListener("mousedown", down);
      box.addEventListener("touchstart", down, { passive: false });
      window.addEventListener("mousemove", move);
      window.addEventListener("touchmove", move, { passive: false });
      window.addEventListener("mouseup", up);
      window.addEventListener("touchend", up);
      // 双击放大
      box.addEventListener("dblclick", () => this._zoomMap(1));
    }
    // 缩放 / 回到车辆
    const wire = (sel, fn, label) => {
      const el = this.querySelector(sel);
      if (el && !el.dataset.w) { el.dataset.w = "1"; el.onclick = fn;
        this._a11y?.(el, label, fn); el.setAttribute("tabindex","0"); }
    };
    wire("#cz-in", () => this._zoomMap(1), "放大");
    wire("#cz-out", () => this._zoomMap(-1), "缩小");
    wire("#cz-me", () => { this._map.px = 0; this._map.py = 0; this._drawMap(); }, "回到车辆");
    puck.style.display = "";
  }

  _zoomMap(delta) {
    if (!this._map) return;
    const z = Math.max(3, Math.min(18, this._map.z + delta));
    if (z === this._map.z) return;
    // 缩放时保持车辆在视野中心
    this._map.z = z; this._map.px = 0; this._map.py = 0;
    this._drawMap();
  }

  /** 按当前缩放/偏移算出需要的瓦片并放置。 */
  _drawMap() {
    const box = this.querySelector("#tiles");
    const wrap = this.querySelector("#mapwrap");
    if (!box || !wrap || !this._map) return;
    const W = wrap.clientWidth || 400, H = wrap.clientHeight || 340;
    const z = this._map.z;
    // ★ 关键：cx/cy 是【瓦片坐标系里的小数】(如 27394.7)。
    //   车辆中心与该点的像素差 = (cx - cxInt) * 256。
    //   之前写成 cpx - (cx - tx) * 256 —— 把整个 cx（两万多）当像素用了，
    //   结果 left = -1400 万 px，瓦片全跑到屏幕外（这就是"看不到地图"的原因）。
    const [cxExact, cyExact] = this._lonlatToTile(this._map.lat, this._map.lon, z);
    const cxInt = Math.floor(cxExact), cyInt = Math.floor(cyExact);
    const offX = (cxExact - cxInt) * 256;   // 车辆在中心瓦片内的像素偏移
    const offY = (cyExact - cyInt) * 256;
    const px = this._map.px || 0, py = this._map.py || 0;
    const cpx = W / 2 + px, cpy = H / 2 + py;   // 车辆在容器里的像素位置
    // 需要覆盖的瓦片范围（以中心瓦片为基准向外扩）
    const x0 = cxInt - Math.ceil((cpx - offX) / 256);
    const x1 = cxInt + Math.ceil((W - cpx + offX) / 256);
    const y0 = cyInt - Math.ceil((cpy - offY) / 256);
    const y1 = cyInt + Math.ceil((H - cpy + offY) / 256);
    const n = 2 ** z;
    const frag = [];
    for (let tx = x0; tx <= x1; tx++) {
      for (let ty = y0; ty <= y1; ty++) {
        if (tx < 0 || ty < 0 || tx >= n || ty >= n) continue;
        // 该瓦片左上角在容器中的位置
        const left = cpx - offX + (tx - cxInt) * 256;
        const top = cpy - offY + (ty - cyInt) * 256;
        const s = (tx + ty) % 4 + 1;   // 高德 1..4 轮询
        const url = `https://webrd0${s}.is.autonavi.com/appmaptile`
                  + `?lang=zh_cn&size=1&scale=1&style=8&x=${tx}&y=${ty}&z=${z}`;
        frag.push(`<img data-k="${tx}_${ty}" src="${url}"`
                + ` style="left:${Math.round(left)}px;top:${Math.round(top)}px">`);
      }
    }
    // 复用已有瓦片节点（减少闪烁）
    const existing = new Map();
    box.querySelectorAll("img").forEach((im) => existing.set(im.dataset.k, im));
    const added = [];
    for (const f of frag) {
      const k = /data-k="([^"]+)"/.exec(f)[1];
      const im = existing.get(k);
      if (im) {
        const st = /left:(-?\d+)px;top:(-?\d+)px/.exec(f);
        im.style.left = st[1] + "px"; im.style.top = st[2] + "px";
        existing.delete(k);
      } else {
        added.push(f);
      }
    }
    existing.forEach((im) => im.remove());
    if (added.length) box.insertAdjacentHTML("beforeend", added.join(""));
    // 车辆标记固定在中心
    const puck = this.querySelector("#puck");
    if (puck) { puck.style.left = (W/2 + px) + "px"; puck.style.top = (H/2 + py) + "px"; }
  }

  _haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000, toRad = (x) => x * Math.PI / 180;
    const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat/2)**2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, LixiangLocationPage);
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "车辆位置（二级页）",
  description: "地图定位 + 地址 + 距离 + 闪灯/鸣笛 + 驻车照片入口",
  preview: true,
});
