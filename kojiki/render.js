// Deterministic frame renderer: drives page.html in headless Chromium, one frame per call.
// usage:
//   node render.js --stills 3.0,9.8,20      -> out/stills/t_XX.jpg
//   node render.js --frames 0 2016 [--out out/frames]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'timeline.json'), 'utf8'));
const arg = (k, d) => { const i = process.argv.indexOf(k); return i < 0 ? d : process.argv[i + 1]; };

(async () => {
  const src = {};
  const sh = f => fs.readFileSync(path.join(ROOT, 'shaders', f + '.glsl'), 'utf8');
  src.common = sh('common');
  for (const s of TL.scenes) src[s.id] = sh(s.id).replace(/^#version.*$/m, '');
  for (const k of ['post_down', 'post_up', 'post_comp']) src[k] = sh(k);

  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('console', m => console.log('[page]', m.text()));
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  await page.goto('file://' + path.join(ROOT, 'page.html'));
  const info = await page.evaluate(([s, t]) => window.init(s, t), [src, TL]);
  console.log('renderer:', info);

  const shot = async (t, file) => {
    const t0 = Date.now();
    const sc = await page.evaluate(t => window.renderAt(t), t);
    await page.screenshot({ path: file, type: 'jpeg', quality: 95 });
    return [sc, Date.now() - t0];
  };

  if (arg('--stills')) {
    const dir = path.join(ROOT, 'out', 'stills'); fs.mkdirSync(dir, { recursive: true });
    for (const s of arg('--stills').split(',')) {
      const t = parseFloat(s);
      const [sc, ms] = await shot(t, path.join(dir, `t_${t.toFixed(2)}.jpg`));
      console.log(`t=${t} ${sc} ${ms}ms`);
    }
  } else {
    const a = parseInt(arg('--frames', '0')), b = parseInt(process.argv[process.argv.indexOf('--frames') + 2] || String(Math.round(TL.duration * TL.fps)));
    const dir = path.join(ROOT, arg('--out', 'out/frames')); fs.mkdirSync(dir, { recursive: true });
    const T0 = Date.now();
    for (let f = a; f < b; f++) {
      const file = path.join(dir, `f_${String(f).padStart(5, '0')}.jpg`);
      if (fs.existsSync(file)) continue; // resumable
      const [sc, ms] = await shot(f / TL.fps, file + '.tmp.jpg');
      fs.renameSync(file + '.tmp.jpg', file);
      if (f % 24 === 0) console.log(`frame ${f}/${b} ${sc} ${ms}ms elapsed ${((Date.now() - T0) / 60000).toFixed(1)}min`);
    }
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
