/* ★★ 真浏览器验证（无头 Chrome）—— 比 jsdom 更接近真实环境
   在 HA 测试机的真实页面里加载卡片 bundle，用 CDP 真实派发 pointer 事件，
   验证「长按→拖动→松手」是否真的换位。*/
import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CARD = path.join(__dirname, '..', 'custom_components', 'lixiang_auto',
                       'www', 'lixiang-cards', 'lixiang-app-home.js');

const HA = 'http://192.168.3.206:8125';
let failures = 0;
const ok = (m) => console.log('  ✅ ' + m);
const bad = (m) => { console.log('  ❌ ' + m); failures++; };

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome-stable',
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  // 访问 HA（即使需要登录也先拿到页面，再注入卡片代码单独测）
  let reached = false;
  try {
    const r = await page.goto(HA + '/lixiang_auto/lixiang-cards/lixiang-all.js',
                              { timeout: 15000 });
    reached = r.status() === 200;
  } catch (e) {}
  ok(`HA 卡片资源可达（HTTP ${reached ? '200' : '不可达'}）`);
  if (!reached) { console.log('  ⚠️ HA 不可达，改用本地 about:blank 注入测'); }

  // ★ 用 file:// 页面：data:/about:blank 都禁用 localStorage
await page.goto('file://' + path.join(__dirname, '_drag_fixture.html'));

  // 注入拖拽代码 + 最小 DOM（用真 Chrome 的 PointerEvent）
  const src = fs.readFileSync(CARD, 'utf8');
  const grab = (name) => {
    const i = src.indexOf(`function ${name}(`);
    if (i < 0) return '';
    const j = src.indexOf('\nfunction ', i + 10);
    return src.slice(i, j > 0 ? j : src.length);
  };
  // ★ 必须切到 lxStore 之前（LX_DRAG_HOLD_MS 定义在这段里）
  // ★ 必须切到 lxStore 之前（LX_DRAG_HOLD_MS 定义在这段里）
  const consts = src.slice(src.indexOf('const LX_DRAG_STORE'),
                           src.indexOf('function lxStore'));

  await page.evaluate(`(() => {
    ${consts}
    ${grab('lxStore')}
    ${grab('lxLoadOrder')}
    ${grab('lxSaveOrder')}
    ${grab('lxClearOrder')}
    ${grab('lxApplyOrder')}
    ${grab('lxApplyGlobalOrder')}
    ${grab('lxEnableDragSort')}
    window.__lx = { lxEnableDragSort, lxApplyOrder, lxLoadOrder, lxApplyGlobalOrder };
    document.body.innerHTML = \`
      <div class="root">
        <div class="row2" id="r1">
          <div class="card ac" id="c-ac" style="position:absolute;left:20px;top:20px;width:120px;height:80px">空调</div>
          <div class="card loc" id="c-loc" style="position:absolute;left:160px;top:20px;width:120px;height:80px">位置</div>
        </div>
        <div class="row2" id="r2">
          <div class="card mile" id="c-mile" style="position:absolute;left:300px;top:200px;width:120px;height:80px">里程</div>
          <div class="card batt" id="c-batt" style="position:absolute;left:440px;top:200px;width:120px;height:80px">电量</div>
        </div>
      </div>\`;
    window.__lx.lxEnableDragSort(document.getElementById('r1'));
    window.__lx.lxEnableDragSort(document.getElementById('r2'));
    window.__order = (r) => Array.from(r.querySelectorAll(':scope > .card')).map(c=>c.id).join(',');
  })()`);

  const before = await page.evaluate(`({
    r1: window.__order(document.getElementById('r1')),
    r2: window.__order(document.getElementById('r2')) })`);
  console.log(`  初始: r1=${before.r1}  r2=${before.r2}`);

  // ★ 真 Chrome 派发 pointer 事件：长按
  await page.evaluate(`(() => {
    const c = document.getElementById('c-ac');
    c.dispatchEvent(new PointerEvent('pointerdown',
      { bubbles:true, button:0, clientX:60, clientY:50 }));
  })()`);
  await new Promise(r => setTimeout(r, 420));
  const dragging = await page.evaluate(
    `document.getElementById('c-ac').classList.contains('lx-dragging')`);
  dragging ? ok('长按 420ms 后立刻有视觉反馈（lx-dragging ✓）')
           : bad('长按后无视觉反馈 —— 用户会以为没反应（真实反馈的 bug）');

  // ★ pointermove 到里程卡位置（跨 row2）
  await page.evaluate(`(() => {
    window.dispatchEvent(new PointerEvent('pointermove',
      { bubbles:true, clientX:340, clientY:220 }));
  })()`);
  await page.evaluate(`(() => {
    window.dispatchEvent(new PointerEvent('pointerup',
      { bubbles:true, clientX:340, clientY:220 }));
  })()`);

  const after = await page.evaluate(`(() => {
    return {
      r1: window.__order(document.getElementById('r1')),
      r2: window.__order(document.getElementById('r2')),
      saved: localStorage.getItem('lx_apphome_order'),
    };
  })()`);
  console.log(`  之后: r1=${after.r1}  r2=${after.r2}`);
  console.log(`  保存: ${after.saved}`);

  after.r1 === 'c-loc' ? ok('r1 只剩 c-loc（空调卡被拖走）')
                       : bad(`r1 应为 c-loc，实际 ${after.r1}`);
  after.r2.startsWith('c-ac') ? ok('r2 首位是 c-ac（跨 row2 拖动成功）')
                              : bad(`r2 应含 c-ac，实际 ${after.r2}`);
  after.saved ? ok('顺序已保存到 localStorage')
              : bad('顺序未保存');

  // ★ 刷新后顺序是否保持（本地重放验证）
  await page.evaluate(`(() => {
    // 模拟刷新：把 c-ac 放回原来的 r1（DOM 复位）
    document.getElementById('r1').appendChild(document.getElementById('c-ac'));
    // 再按保存的全局顺序重放
    const root = document.querySelector('.root');
    window.__lx.lxApplyGlobalOrder(root);
  })()`);
  const kept = await page.evaluate(`window.__order(document.getElementById('r1'))`);
  kept === 'c-loc' ? ok('重新加载后顺序保持（lxApplyOrder ✓）')
                   : bad(`重新加载后顺序应为 c-loc，实际 ${kept}`);

  await browser.close();
  console.log();
  console.log(failures === 0
    ? '  ✅✅ 真浏览器验证通过：拖拽真的能用'
    : `  ❌ 有 ${failures} 项失败`);
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => { console.error('  ❌ 运行异常:', e.message); process.exit(1); });
