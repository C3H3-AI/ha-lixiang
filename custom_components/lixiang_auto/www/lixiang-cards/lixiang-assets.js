/*!
 * lixiang-assets.js —— 车型资源解析（适用所有车型的资源层）
 *
 * ★ 设计目标：卡片**不按车型分支**，只问「这辆车该用哪张图」，拿不到就逐级回退，永不空屏。
 *
 * 三级回退链（顺序即优先级）：
 *   ① 用户本地专属图   <config>/www/lixiang_auto/cars/<modelId>.{png,webp,jpg,svg}  （经 /local/ 访问）
 *   ② 内置车系剪影     L 系（L6/L7/L8/L9  SUV）/ W 系（MEGA、i8  MPV）/ M 系（理想ONE）
 *   ③ 通用占位剪影     任何车型都至少有这个兜底
 *
 * ★ 为什么内置剪影而不是官方图：
 *   · 官方车型图只编译在 App 本体里（res/assets 均无法直接取得，也没有 CDN 地址）
 *   · 随集成分发官方素材有版权风险
 *   · 自制剪影体积小、可版本控制、对 unknown/新车型天然可用
 *
 * ★ 持久化：
 *   · 内置剪影：随集成版本分发（`www/lixiang-cards/`，HACS 更新即刷新）
 *   · 用户专属图：放 `<config>/www/lixiang_auto/cars/`，用户自己维护，集成升级不会丢
 *
 * ★ 缓存：资源 URL 会带上版本号（`window.__LX_ASSET_V__`），
 *   由集成侧 `/lixiang_auto/asset-version.js` 注入 —— 版本变了浏览器就会重新拉取。
 */
(function () {
  const CANDIDATE_EXTS = ['png', 'webp', 'jpg', 'svg'];

  // 用户自定义车型图目录（HA 的 www 目录 → /local/）
  const USER_CAR_DIR = '/local/lixiang-cars';   // 与 /local/lixiang-icons 同一约定

  function assetV() {
    try {
      return (typeof window !== 'undefined' && window.__LX_ASSET_V__) || '0';
    } catch (_) {
      return '0';
    }
  }

  /** 给资源 URL 加版本号查询串（cache-buster） */
  function vurl(url) {
    const v = assetV();
    if (!url || v === '0') return url;
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'v=' + encodeURIComponent(v);
  }

  /**
   * 派生车系（L / W / M / generic）。
   * 三个线索任一即可：unityModel（最准）→ 车型名（"理想L6" / "MEGA" / "理想ONE"）→ 都没有则 generic。
   * 这样即使拿不到能力表（modelId/unityModel 缺失），卡片也不会白屏。
   */
  function seriesOf(unityModel, modelName) {
    const u = String(unityModel || '').toUpperCase();
    if (u.startsWith('M')) return 'M';       // M01A / M01B —— 理想ONE
    if (u.startsWith('W')) return 'W';       // W01/W02/W04… —— MEGA / i8
    if (u.startsWith('L')) return 'L';       // L6 / L7 / L8 / L9
    const n = String(modelName || '');
    if (/理想\s*ONE|ONE/i.test(n)) return 'M';
    if (/MEGA|i8/i.test(n)) return 'W';
    if (/L\s*[6-9]/i.test(n)) return 'L';
    return 'generic';
  }

  /* ---- 内置车系剪影（内联 SVG data URI，离线可用、无外部依赖） ---- */
  // 说明：这是**示意剪影**（侧面轮廓），不是官方车型图。
  function svgDataUri(body) {
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 100" width="240" height="100">' +
      '<g fill="currentColor">' + body + '</g></svg>';
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  const SILHOUETTE = {
    // L 系：SUV（较高车身、短前悬）
    L: svgDataUri(
      '<path d="M18 74 q10-30 34-33 q16-2 26-12 q10-10 30-11 q26-1 40 8 l30 12 q16 6 26 16 l8 20 z"/>' +
      '<circle cx="62" cy="76" r="13"/><circle cx="176" cy="76" r="13"/>'
    ),
    // W 系：MPV（长车身、平直车顶）
    W: svgDataUri(
      '<path d="M12 72 q6-26 26-28 l120-4 q30 0 44 12 l14 18 v22 z"/>' +
      '<circle cx="58" cy="76" r="12"/><circle cx="182" cy="76" r="12"/>'
    ),
    // M 系：理想ONE（更方正的早期 SUV 轮廓）
    M: svgDataUri(
      '<path d="M16 74 q8-28 30-30 q18-2 28-10 q10-8 28-9 q24-1 38 9 l26 12 q14 6 22 14 l6 14 z"/>' +
      '<circle cx="60" cy="76" r="13"/><circle cx="170" cy="76" r="13"/>'
    ),
    // 通用占位：最简车身 + 两个轮子
    generic: svgDataUri(
      '<path d="M20 72 q8-24 28-26 q16-2 26-9 q10-7 26-8 q22-1 34 8 l22 11 q12 5 18 12 l4 12 z"/>' +
      '<circle cx="58" cy="76" r="12"/><circle cx="168" cy="76" r="12"/>'
    ),
  };

  /**
   * 车图候选列表（有序，越靠前越优先）。
   * @param {string} modelId     车型 modelId（服务端下发）
   * @param {string} unityModel  能力表里的 unityModel（L6 / W02 / M01B…），可为空
   * @returns {string[]} 候选 URL 列表
   */
  function carImageCandidates(info) {
    info = info || {};
    const modelId = info.modelId || '';
    const unityModel = info.unityModel || '';
    const modelName = info.modelName || '';
    const series = seriesOf(unityModel, modelName);

    // 用户本地图的查找键：modelId 优先，其次 unityModel，最后车系名 —— 与内置剪影之间还要插一次「车系图」以便用户只放一张就能覆盖整个车系
    const keys = [];
    for (const k of [modelId, unityModel, series === 'generic' ? '' : series]) {
      if (k && keys.indexOf(k) < 0) keys.push(k);
    }

    const out = [];
    for (const k of keys) {
      for (const ext of CANDIDATE_EXTS) {
        out.push(vurl(USER_CAR_DIR + '/' + k + '.' + ext));
      }
    }
    out.push(SILHOUETTE[series] || SILHOUETTE.generic);
    out.push(SILHOUETTE.generic);
    return out.filter((u, i) => out.indexOf(u) === i);
  }

  /**
   * 生成「逐级回退」的 <img>：加载失败自动换下一个候选，全失败则隐藏（不留破图图标）。
   * @param {string} modelId
   * @param {string} unityModel
   * @param {object} [opts] {cls, alt, style}
   */
  function carImageHtml(info, opts) {
    opts = opts || {};
    const list = carImageCandidates(info);
    const cls = opts.cls ? ' class="' + opts.cls + '"' : '';
    const style = opts.style ? ' style="' + opts.style + '"' : '';
    const alt = opts.alt != null ? opts.alt : '';
    // onerror 里推进到下一个候选；用尽则隐藏
    return (
      '<img' + cls + style + ' src="' + list[0] + '" alt="' + alt + '" ' +
      'data-lx-candidates="' + encodeURIComponent(JSON.stringify(list)) + '" ' +
      'onerror="window.__lxCarFallback&&window.__lxCarFallback(this)">'
    );
  }

  /** onerror 处理器：换下一个候选；用尽则隐藏元素 */
  function carFallback(img) {
    try {
      let idx = Number(img.dataset.lxIdx || 0) + 1;
      const list = JSON.parse(decodeURIComponent(img.dataset.lxCandidates || '[]'));
      if (idx < list.length) {
        img.dataset.lxIdx = String(idx);
        img.src = list[idx];
        return;
      }
      img.style.visibility = 'hidden';
    } catch (_) {
      img.style.visibility = 'hidden';
    }
  }

  const api = {
    assetV: assetV,
    vurl: vurl,
    seriesOf: seriesOf,
    SILHOUETTE: SILHOUETTE,
    carImageCandidates: carImageCandidates,
    carImageHtml: carImageHtml,
    carFallback: carFallback,
  };

  if (typeof window !== 'undefined') {
    window.LxAssets = api;
    window.__lxCarFallback = carFallback;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
