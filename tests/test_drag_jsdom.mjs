/* ★ 真实验证：用 jsdom 模拟「长按→拖动→松手」，看卡片是否真的换了位置 */
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CARD = path.join(__dirname, '..', 'custom_components', 'lixiang_auto',
                       'www', 'lixiang-cards', 'lixiang-app-home.js');

const src = fs.readFileSync(CARD,'utf8');
// 只取拖拽相关函数（避免整卡依赖 HA 环境）
const grab = (name) => {
  const i = src.indexOf(`function ${name}(`);
  if (i < 0) return null;
  const j = src.indexOf('\nfunction ', i + 10);
  return src.slice(i, j > 0 ? j : src.length);
};
const consts = src.slice(src.indexOf('const LX_DRAG_STORE'), src.indexOf('function lxLoadOrder'));
const code = [consts, grab('lxLoadOrder'), grab('lxSaveOrder'), grab('lxClearOrder'),
              grab('lxApplyOrder'), grab('lxEnableDragSort')].join('\n');

const dom = new JSDOM(`<!DOCTYPE html><html><body>
<div class="root">
  <div class="row2" id="r1">
    <div class="card ac" id="c-ac">空调</div>
    <div class="card loc" id="c-loc">位置</div>
  </div>
  <div class="row2" id="r2">
    <div class="card mile" id="c-mile">里程</div>
    <div class="card batt" id="c-batt">电量</div>
  </div>
</div></body></html>`, { url: 'http://localhost/' });
const { window } = dom;
window.localStorage.setItem('lx_apphome_order', JSON.stringify([]));
// ★ eval 在 ESM 里不暴露函数 → 追加一句把它们挂到 window
eval(code + `
window.__lx = { lxLoadOrder, lxSaveOrder, lxClearOrder, lxApplyOrder, lxEnableDragSort };
`);
const lxLoadOrder = window.__lx.lxLoadOrder;
const lxSaveOrder = window.__lx.lxSaveOrder;
const lxApplyOrder = window.__lx.lxApplyOrder;
const lxEnableDragSort = window.__lx.lxEnableDragSort;

const r1 = window.document.getElementById('r1');
const r2 = window.document.getElementById('r2');
const cAc = window.document.getElementById('c-ac');
const cMile = window.document.getElementById('c-mile');

const order = (r) => Array.from(r.querySelectorAll(':scope > .card')).map(c=>c.id).join(',');
console.log('  初始 r1:', order(r1));
console.log('  初始 r2:', order(r2));

lxEnableDragSort(r1);
lxEnableDragSort(r2);

// 模拟长按 350ms
cAc.dispatchEvent(new window.PointerEvent('pointerdown', {bubbles:true, button:0, clientX:100, clientY:100}));
await new Promise(r=>setTimeout(r, 400));
console.log('  → 长按 400ms 后，卡片有 lx-dragging?', cAc.classList.contains('lx-dragging') ? '✅' : '❌（拖动未启动）');

// 模拟拖动到里程卡（跨 row2）
const box = cMile.getBoundingClientRect();
box.left = 300; box.width = 100;
cMile.getBoundingClientRect = () => ({left:300, top:200, width:100, height:80, right:400, bottom:280});
window.document.elementFromPoint = () => cMile;
window.dispatchEvent(new window.PointerEvent('pointermove', {bubbles:true, clientX:340, clientY:210}));
window.dispatchEvent(new window.PointerEvent('pointerup', {bubbles:true, clientX:340, clientY:210}));

console.log('  → 松手后 r1:', order(r1));
console.log('  → 松手后 r2:', order(r2));
const saved = JSON.parse(window.localStorage.getItem('lx_apphome_order'));
console.log('  → 保存的顺序:', JSON.stringify(saved));
console.log();
console.log('  ★ 判定：');
const r1ok = order(r1) === 'c-loc';
const r2ok = order(r2).startsWith('c-ac');
console.log(`     r1 只剩 loc  : ${r1ok?'✅':'❌'}`);
console.log(`     r2 首位是 ac : ${r2ok?'✅':'❌'}`);
console.log(`     顺序已保存   : ${saved && saved.length?'✅':'❌'}`);
console.log(`     结论：${r1ok && r2ok ? '✅✅ 拖拽真的能用了' : '❌ 仍有问题'}`);
if (!(r1ok && r2ok && saved && saved.length)) process.exit(1);
