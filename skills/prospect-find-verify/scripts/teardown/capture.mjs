// Passive page capture over Chrome DevTools Protocol. Loads pages, scrolls, waits.
// Never clicks, types or submits. MOUSE=1 adds mouse-move and wheel-scroll events only (no clicks), to wake scripts deferred until interaction. Writes a HAR (request URL, method, headers, postData, status),
// rendered DOM, a screenshot per page, and a frames list.
// Usage: node capture.mjs <outprefix> <url1> [url2 ...]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const [out, ...urls] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random()*500);
const prof = fs.mkdtempSync('/tmp/cdpprof-');
const chrome = spawn('google-chrome', ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  '--no-first-run', '--no-default-browser-check', '--window-size=1366,900', '--disable-features=PrivacySandboxSettings4', 'about:blank'], {stdio: 'ignore'});
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ver; for (let i=0;i<50;i++){ try { ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); break; } catch { await sleep(200);} }
const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map(); const reqs = new Map(); const frames = []; const pages = [];
let curPage = '';
function send(method, params = {}, sessionId) { const i = ++id; ws.send(JSON.stringify({id:i, method, params, sessionId})); return new Promise((res, rej) => pend.set(i, {res, rej})); }
async function setup(sessionId) {
  await send('Network.enable', {maxPostDataSize: 65536}, sessionId).catch(()=>{});
  await send('Page.enable', {}, sessionId).catch(()=>{});
  await send('Target.setAutoAttach', {autoAttach: true, waitForDebuggerOnStart: true, flatten: true}, sessionId).catch(()=>{});
  await send('Runtime.runIfWaitingForDebugger', {}, sessionId).catch(()=>{});
}
ws.onmessage = async ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pend.has(m.id)) { const p = pend.get(m.id); pend.delete(m.id); m.error ? p.rej(m.error) : p.res(m.result); return; }
  const P = m.params || {};
  if (m.method === 'Target.attachedToTarget') { frames.push({page: curPage, type: P.targetInfo.type, url: P.targetInfo.url}); setup(P.sessionId); }
  if (m.method === 'Network.requestWillBeSent') {
    const k = (m.sessionId||'') + P.requestId;
    const prev = reqs.get(k);
    const r = {page: curPage, startedDateTime: new Date(P.wallTime*1000).toISOString(), request: {method: P.request.method, url: P.request.url,
      headers: Object.entries(P.request.headers||{}).map(([name,value])=>({name,value})), postData: P.request.postData ? {mimeType: (P.request.headers||{})['Content-Type']||'', text: P.request.postData} : undefined},
      response: {status: 0}, initiator: P.initiator?.type, sessionId: m.sessionId, rid: P.requestId, type: P.type};
    if (prev) reqs.set(k + '#' + Math.random(), prev);
    reqs.set(k, r);
    if (P.request.hasPostData && !P.request.postData) send('Network.getRequestPostData', {requestId: P.requestId}, m.sessionId).then(x => { r.request.postData = {mimeType:'', text: x.postData}; }).catch(()=>{});
  }
  if (m.method === 'Network.responseReceived') { const r = reqs.get((m.sessionId||'') + P.requestId); if (r) { r.response = {status: P.response.status, mimeType: P.response.mimeType}; } }
  if (m.method === 'Page.frameNavigated' && P.frame.parentId) frames.push({page: curPage, type: 'frame', url: P.frame.url});
};
const tgt = await send('Target.createTarget', {url: 'about:blank'});
const att = await send('Target.attachToTarget', {targetId: tgt.targetId, flatten: true});
const S = att.sessionId; await setup(S);
await send('Network.setUserAgentOverride', {userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36'}, S);
for (const [n, url] of urls.entries()) {
  curPage = url;
  await Promise.race([send('Page.navigate', {url}, S).catch(e => console.error('nav', url, e)), sleep(20000)]);
  await sleep(9000);
  for (let y = 0; y < 6; y++) { if (process.env.MOUSE) { await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: 300 + y*40, y: 300 + y*20}, S).catch(()=>{}); await send('Input.dispatchMouseEvent', {type: 'mouseWheel', x: 683, y: 450, deltaX: 0, deltaY: 600}, S).catch(()=>{}); } else { await send('Runtime.evaluate', {expression: `window.scrollBy(0, 900)`}, S).catch(()=>{}); } await sleep(700); }
  await sleep(4000);
  const dom = await Promise.race([sleep(10000).then(()=>({result:{value:''}})), send('Runtime.evaluate', {expression: 'document.documentElement.outerHTML', returnByValue: true}, S).catch(()=>({result:{value:''}}))]);
  const finalUrl = await send('Runtime.evaluate', {expression: 'location.href', returnByValue: true}, S).catch(()=>({result:{value:''}}));
  fs.writeFileSync(`${out}.p${n}.dom.html`, dom.result.value || '');
  await send('Runtime.evaluate', {expression: 'window.scrollTo(0,0)'}, S).catch(()=>{}); await sleep(800);
  const shot = await send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false}, S).catch(()=>null);
  if (shot) fs.writeFileSync(`${out}.p${n}.png`, Buffer.from(shot.data, 'base64'));
  pages.push({n, url, finalUrl: finalUrl.result.value});
}
await sleep(1500);
const entries = [...reqs.values()].map(r => ({pageref: r.page, startedDateTime: r.startedDateTime, request: r.request, response: r.response, _type: r.type, _initiator: r.initiator, _inIframeSession: !!r.sessionId && r.sessionId !== S}));
fs.writeFileSync(`${out}.har`, JSON.stringify({log: {version: '1.2', creator: {name: 'capture.mjs passive CDP'}, pages, entries}}));
fs.writeFileSync(`${out}.frames.json`, JSON.stringify(frames, null, 1));
console.log(out, 'entries', entries.length, 'pages', JSON.stringify(pages));
ws.close(); chrome.kill(); await sleep(1500); try { fs.rmSync(prof, {recursive: true, force: true}); } catch {} process.exit(0);
