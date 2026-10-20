/* ★ 真浏览器验证：卡片在浅色/深色下都能正常显示（无隐形文字）。*/
import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CARD = path.join(__dirname, '..', 'custom_components', 'lixiang_auto',
                       'www', 'lixiang-cards', 'lixiang-app-home.js');
const src = fs.readFileSync(CARD, 'utf8');

let fail = 0;
const ok = (m) => console.log('  ✅ ' + m);
const bad = (m) => { console.log('  ❌ ' + m); fail++; };

(async () => {
  const b = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome-stable', headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await b.newPage();
  await page.setViewport({ width: 420, height: 900 });

  for (const scheme of ['light', 'dark']) {
    await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: scheme }]);
    // 取出 STYLE 与一段 DOM（含确认弹窗）
    const style = src.slice(src.indexOf('const STYLE'), src.indexOf('`;', src.indexOf('const STYLE')));
    await page.setContent(`<!DOCTYPE html><html><head><style>${style.slice(style.indexOf('`')+1)}</style></head>
      <body><lixiang-app-home>
        <div class="root">
          <div class="cfm-box"><div class="cfm-text">确认锁车？</div>
            <div class="cfm-row"><button class="cfm-no">取消</button>
            <button class="cfm-yes">确认</button></div></div>
          <div class="toast">已锁车</div>
        </div></lixiang-app-home></body></html>`);

    const r = await page.evaluate(() => {
      const lum = (c) => {
        const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null;
        const [r, g, bb] = m[1].split(',').map(Number);
        return (0.299*r + 0.587*g + 0.114*bb) / 255;
      };
      const box = document.querySelector('.cfm-box');
      const txt = document.querySelector('.cfm-text');
      const yes = document.querySelector('.cfm-yes');
      const toast = document.querySelector('.toast');
      const g = (el) => el ? getComputedStyle(el) : null;
      const bg = g(box) ? g(box).backgroundColor : '';
      const fg = g(txt) ? g(txt).color : '';
      const ybg = g(yes) ? g(yes).backgroundColor : '';
      const yfg = g(yes) ? g(yes).color : '';
      const tbg = g(toast) ? g(toast).backgroundColor : '';
      const tfg = g(toast) ? g(toast).color : '';
      return { bg, fg, ybg, yfg, tbg, tfg,
               lbg: lum(bg), lfg: lum(fg), lybg: lum(ybg), lyfg: lum(yfg),
               ltbg: lum(tbg), ltfg: lum(tfg) };
    });

    console.log(`  ── ${scheme} 模式:`);
    // 弹窗：字与底必须有对比
    const dlg = Math.abs((r.lbg ?? 0) - (r.lfg ?? 0));
    dlg > 0.3 ? ok(`确认弹窗可读（底/字亮度差 ${dlg.toFixed(2)}）`)
              : bad(`确认弹窗对比不足（差 ${dlg.toFixed(2)}）`);
    // 主按钮
    const dbtn = Math.abs((r.lybg ?? 0) - (r.lyfg ?? 0));
    dbtn > 0.3 ? ok(`主按钮可读（差 ${dbtn.toFixed(2)}）`)
               : bad(`主按钮对比不足（差 ${dbtn.toFixed(2)}）`);
    // toast
    const dtoast = Math.abs((r.ltbg ?? 0) - (r.ltfg ?? 0));
    dtoast > 0.3 ? ok(`toast 可读（差 ${dtoast.toFixed(2)}）`)
                : bad(`toast 对比不足（差 ${dtoast.toFixed(2)}）`);
  }
  await b.close();
  console.log();
  console.log(fail === 0 ? '  ✅✅ 深浅色均通过' : `  ❌ ${fail} 项失败`);
  process.exit(fail === 0 ? 0 : 1);
})().catch((e) => { console.error('  ❌', e.message); process.exit(1); });
