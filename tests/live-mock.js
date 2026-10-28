// SPDX-License-Identifier: Apache-2.0
// Exercises the live code path against a mocked api.github.com: node tests/live-mock.js <outdir>
// One invalid status file, two agents missing from config.js (one with markup for an id) and one 404 repo
// are injected on purpose; the checks below expect them. Then: a status branch that is not found, Save
// with a read in flight (new tokens, and sample data), and a scratch config with a problem.
const { chromium } = require('playwright');
const { appUrl, scratchApp, readInstance, pathOf } = require('./app-under-test');
const b64 = o => Buffer.from(JSON.stringify(o)).toString('base64');
const now = new Date().toISOString();
const EVIL = '<img src=x onerror="window.__evil=1">';
(async () => {
  const out = process.argv[2] || '/tmp/gl-live';
  require('fs').mkdirSync(out, { recursive: true });
  const url = appUrl();
  const b = await chromium.launch();
  const probe = await b.newPage(); await probe.goto(url);
  const inst = await readInstance(probe); await probe.close();
  const [prRepo, okRepo] = [inst.repos[0], inst.repos[1] || inst.repos[0]];
  const missingRepo = inst.repos.length > 2 ? inst.repos[inst.repos.length - 1] : null;
  const files = {
    [pathOf(inst.agent, inst)]: { schema: 'gatherlane.agent-status/v1', agent: inst.agent, status: 'waiting', current_task: { title: 'mock escalation', url: null }, needs_human: true, needs_human_kind: 'escalation', needs_human_reason: 'mock: refund outside policy', links: { issue: `https://github.com/${prRepo}/issues/1` }, updated_at: now, reported_by: 'mock' },
    [pathOf(inst.other, inst)]: { schema: 'gatherlane.agent-status/v1', agent: inst.other, status: 'running', needs_human: false, updated_at: '2026-01-01T00:00:00Z', schedule: { cron: '*/30 * * * *' } },
    'status/mock/bad.json': { agent: 'x', status: 'dancing' },
    'status/mock/stray.json': { schema: 'gatherlane.agent-status/v1', agent: 'mock/stray', status: 'idle', needs_human: false, updated_at: now },
    'status/mock/evil.json': { schema: 'gatherlane.agent-status/v1', agent: EVIL, status: 'idle', needs_human: false, updated_at: now },
    'control/pause.json': { schema: 'gatherlane.control/v1', paused: { [inst.other]: { since: now, by: 'maintainer' } } },
  };
  const ctx = await b.newContext({ viewport: { width: 1600, height: 950 } });
  const tokens = Object.fromEntries(inst.owners.map((o, i) => [o, 't' + i]));
  await ctx.addInitScript(t => localStorage.setItem('gl.tokens', JSON.stringify(t)), tokens);
  const seen = []; let noAuth = 0, newAuth = 0, stall = false, noBranch = false, hold = null, held = [];
  const authOf = route => route.request().headers()['authorization'] || '';
  // Answers the requests held so far that match `pick`, keeps the rest held
  const release = (pick = () => true) => { const go = held.filter(pick); held = held.filter(r => !pick(r)); go.forEach(answer); };
  await ctx.route('https://api.github.com/**', route => {
    if (stall) return; // left unanswered: a read still in flight
    if (hold && hold(route)) { held.push(route); return; } // answered later by release()
    answer(route);
  });
  function answer(route) {
    const u = new URL(route.request().url()); seen.push(u.pathname + u.search);
    if (!authOf(route)) noAuth++;
    if (authOf(route).includes('NEW')) newAuth++; // tokens typed into Settings: their status tree is a 404
    const j = (o, s = 200) => route.fulfill({ status: s, contentType: 'application/json', headers: { 'access-control-allow-origin': '*', 'x-ratelimit-remaining': '4990', etag: '"x"' }, body: JSON.stringify(o) });
    if (u.pathname === `/repos/${inst.statusRepo}/git/trees/status`) return noBranch || authOf(route).includes('NEW') ? j({ message: 'Not Found' }, 404) : j({ tree: Object.keys(files).map((p, i) => ({ path: p, type: 'blob', sha: 'sha' + i })), truncated: false });
    const bm = /\/git\/blobs\/sha(\d+)/.exec(u.pathname); if (bm) return j({ content: b64(files[Object.keys(files)[+bm[1]]]) });
    if (missingRepo && u.pathname.startsWith(`/repos/${missingRepo}/`)) return j({ message: 'Not Found' }, 404);
    if (u.pathname === `/repos/${prRepo}/pulls` && u.search.includes('open')) return j([{ number: 93, title: 'mock PR', html_url: `https://github.com/${prRepo}/pull/93`, labels: [{ name: 'review:needs-maintainer' }], user: { login: 'g' } }]);
    if (u.pathname === `/repos/${okRepo}/pulls` && u.search.includes('open')) return j([{ number: 41, title: 'mock approved PR', html_url: `https://github.com/${okRepo}/pull/41`, labels: [{ name: 'review:approved' }], user: { login: 'g' } }]);
    if (u.pathname === `/repos/${okRepo}/actions/runs`) return j({ workflow_runs: [{ workflow_id: 1, name: 'ci', head_branch: 'main', status: 'completed', conclusion: 'failure', event: 'push', html_url: 'https://github.com/x/run/1', updated_at: now }] });
    if (u.pathname.endsWith('/actions/runs')) return j({ workflow_runs: [] });
    if (u.pathname.endsWith('/issues')) return j([{ number: 5, title: 'mock issue', html_url: 'https://github.com/x/issues/5', milestone: { title: 'R1: mock' } }]);
    if (u.pathname.endsWith('/pulls')) return j([]);
    return j({ message: 'unmocked ' + u.pathname }, 404);
  }
  const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto(url); await p.waitForTimeout(1200);
  await p.screenshot({ path: out + '/live-building.png' });
  await p.keyboard.press(inst.first.key); await p.waitForTimeout(300);
  const bx = await p.locator(`[data-agent="${inst.agent}"] .bob`).boundingBox();
  await p.mouse.click(bx.x + bx.width / 2, bx.y + bx.height / 2); await p.waitForTimeout(300);
  await p.screenshot({ path: out + '/live-card.png' });
  const rb = await p.locator(`[data-room="${inst.first.room}"]`).first().boundingBox();
  await p.mouse.click(rb.x + rb.width * .3, rb.y + rb.height * .6); await p.waitForTimeout(600);
  await p.screenshot({ path: out + '/live-room.png' });
  await p.click('#settingsBtn'); await p.waitForTimeout(200);
  await p.screenshot({ path: out + '/live-settings.png' });
  const st = await p.evaluate(() => ({ mode: __gl.D.mode, rows: __gl.D.rows.length, invalid: __gl.D.invalid.length, prs: __gl.D.prs.length, runs: __gl.D.runs.length, prErr: Object.keys(__gl.D.prErr || {}) }));
  const conn = await p.evaluate(() => [...document.querySelectorAll('#conn .conn div')].map(d => [d.children[0].textContent, d.children[1].textContent]));
  const silent = await p.evaluate(a => Building.LEVELS.flatMap(L => L.agents.filter(x => !x.human && !x.decor && !x.walker).map(x => x.id)).filter(id => !a.includes(id)).sort().join(', '), [inst.agent, inst.other]);
  const row = start => (conn.find(([k]) => k.startsWith(start)) || [])[1];
  st.unplaced = row('Reporting, but on no floor'); st.silent = row('On a floor, but no status file') || '';
  st.hint = (conn.find(([k]) => k.startsWith('Reporting, but on no floor')) || [])[0];
  st.markup = await p.evaluate(() => ({ imgs: document.querySelectorAll('#conn img').length, ran: !!window.__evil }));
  const generated = await p.evaluate(() => !!Building.generated);
  const lists = pg => pg.evaluate(() => [...document.querySelectorAll('#conn .conn div span')].filter(s => /^(Reporting|On a floor)/.test(s.textContent)).length);
  const readDone = pg => pg.waitForFunction(() => __gl.D.updated, null, { timeout: 8000 }).then(() => true, () => false);
  // A status branch that cannot be read lists no agent as silent or unplaced, only the error
  noBranch = true;
  const nb = await ctx.newPage(); await nb.goto(url);
  st.noBranch = { done: await readDone(nb) };
  await nb.click('#settingsBtn'); await nb.waitForTimeout(200);
  Object.assign(st.noBranch, { err: await nb.evaluate(() => !!__gl.D.statusErr), lists: await lists(nb) });
  await nb.close(); noBranch = false;
  // Settings opened before the first status read finishes must not list anyone as silent
  stall = true;
  const early = await ctx.newPage(); await early.goto(url); await early.waitForTimeout(400);
  await early.click('#settingsBtn'); await early.waitForTimeout(200);
  st.earlyLists = await lists(early);
  // Save starts a new read; until it finishes, the previous tokens' read is not listed
  await p.click('#setSave'); await p.waitForTimeout(200);
  await p.click('#settingsBtn'); await p.waitForTimeout(200);
  st.afterSave = { updated: await p.evaluate(() => __gl.D.updated), lists: await lists(p) };
  stall = false;
  // Save with "Show SAMPLE data" ticked while a read is in flight: when the read returns, no agent
  // lists and no live rows under the SAMPLE pill
  hold = () => true;
  const sm = await ctx.newPage(); sm.on('pageerror', e => errs.push(e.message));
  await sm.goto(url); await sm.waitForTimeout(400);
  await sm.click('#settingsBtn'); await sm.waitForTimeout(100);
  await sm.check('#useSample'); await sm.click('#setSave'); await sm.waitForTimeout(200);
  hold = null; release(); await sm.waitForTimeout(1000);
  await sm.click('#settingsBtn'); await sm.waitForTimeout(200);
  st.toSample = { mode: await sm.evaluate(() => __gl.D.mode), liveRows: await sm.evaluate(() => __gl.D.rows.filter(r => r.source === 'live').length), lists: await lists(sm) };
  await sm.evaluate(() => localStorage.removeItem('gl.prefs')); await sm.close();
  // Save new tokens while a read is in flight: the old read is dropped when it returns, and a new
  // read with the new tokens follows it
  hold = () => true;
  const sv = await ctx.newPage(); sv.on('pageerror', e => errs.push(e.message));
  await sv.goto(url); await sv.waitForTimeout(400);
  await sv.click('#settingsBtn'); await sv.waitForTimeout(100);
  await sv.$$eval('#tokRows input', els => els.forEach(e => { e.value = 'NEW'; }));
  await sv.click('#setSave'); await sv.waitForTimeout(200);
  hold = r => authOf(r).includes('NEW'); release(r => !authOf(r).includes('NEW')); await sv.waitForTimeout(1000);
  await sv.click('#settingsBtn'); await sv.waitForTimeout(200);
  st.saveMidRead = { oldDone: { updated: await sv.evaluate(() => __gl.D.updated), lists: await lists(sv) } };
  await sv.click('#setClose');
  hold = null; release();
  st.saveMidRead.newRead = await readDone(sv);
  await sv.click('#settingsBtn'); await sv.waitForTimeout(200);
  Object.assign(st.saveMidRead, { newReqs: newAuth > 0, err: await sv.evaluate(() => !!__gl.D.statusErr), lists: await lists(sv) });
  await sv.close();
  // A config.js with a problem: toast and console warning at start, a config.js row in Settings
  const cp = await (await b.newContext({ viewport: { width: 1600, height: 950 } })).newPage(); const warns = [];
  cp.on('console', m => { if (m.type() === 'warning') warns.push(m.text()); });
  cp.on('pageerror', e => errs.push(e.message));
  await cp.goto(scratchApp('examples/instance', "GATHERLANE_CONFIG.agents['supervisor/digest'] = {};")); await cp.waitForTimeout(400);
  const toastText = await cp.evaluate(() => { const t = document.getElementById('toast'); return t.hidden ? null : t.textContent; });
  await cp.click('#settingsBtn'); await cp.waitForTimeout(200);
  const cfgRows = await cp.evaluate(() => [...document.querySelectorAll('#conn .conn div')].filter(d => d.children[0].textContent === 'config.js').map(d => d.children[1].textContent));
  st.badConfig = { toast: toastText, warns: warns.filter(w => w.startsWith('config.js:') && w.includes('supervisor/digest')).length, rows: cfgRows.filter(r => r.includes('supervisor/digest')).length, lists: await lists(cp) };
  const want = {
    mode: 'live', rows: 4, unplaced: `${EVIL}, mock/stray`, silent, markup: { imgs: 0, ran: false },
    hint: `Reporting, but on no floor (add to ${generated ? 'config.js' : 'building.js'})`,
    noBranch: { done: true, err: true, lists: 0 }, afterSave: { updated: null, lists: 0 },
    toSample: { mode: 'sample', liveRows: 0, lists: 0 },
    saveMidRead: { oldDone: { updated: null, lists: 0 }, newRead: true, newReqs: true, err: true, lists: 0 },
    badConfig: { toast: 'config.js has 1 problem; see Settings', warns: 1, rows: 1, lists: 0 },
    earlyLists: 0, invalid: 1, prs: prRepo === okRepo ? 1 : 2, runs: 1, prErr: missingRepo ? [missingRepo] : [] };
  const fails = Object.keys(want).filter(k => JSON.stringify(st[k]) !== JSON.stringify(want[k])).map(k => `${k}: got ${JSON.stringify(st[k])}, want ${JSON.stringify(want[k])}`);
  if (errs.length) fails.push('page errors: ' + errs.join(' | '));
  if (noAuth) fails.push(`${noAuth} GitHub calls without a token`);
  console.log(JSON.stringify({ st, calls: seen.length, fails }, null, 1));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
