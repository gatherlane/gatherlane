// SPDX-License-Identifier: Apache-2.0
// Exercises the live code path against a mocked api.github.com: node tests/live-mock.js <outdir>
// One invalid status file and one 404 repo are injected on purpose; the checks below expect them.
const { chromium } = require('playwright');
const { appUrl, readInstance, pathOf } = require('./app-under-test');
const b64 = o => Buffer.from(JSON.stringify(o)).toString('base64');
const now = new Date().toISOString();
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
    'control/pause.json': { schema: 'gatherlane.control/v1', paused: { [inst.other]: { since: now, by: 'maintainer' } } },
  };
  const ctx = await b.newContext({ viewport: { width: 1600, height: 950 } });
  const tokens = Object.fromEntries(inst.owners.map((o, i) => [o, 't' + i]));
  await ctx.addInitScript(t => localStorage.setItem('gl.tokens', JSON.stringify(t)), tokens);
  const seen = []; let noAuth = 0;
  await ctx.route('https://api.github.com/**', route => {
    const u = new URL(route.request().url()); seen.push(u.pathname + u.search);
    if (!route.request().headers()['authorization']) noAuth++;
    const j = (o, s = 200) => route.fulfill({ status: s, contentType: 'application/json', headers: { 'access-control-allow-origin': '*', 'x-ratelimit-remaining': '4990', etag: '"x"' }, body: JSON.stringify(o) });
    if (u.pathname === `/repos/${inst.statusRepo}/git/trees/status`) return j({ tree: Object.keys(files).map((p, i) => ({ path: p, type: 'blob', sha: 'sha' + i })), truncated: false });
    const bm = /\/git\/blobs\/sha(\d+)/.exec(u.pathname); if (bm) return j({ content: b64(files[Object.keys(files)[+bm[1]]]) });
    if (missingRepo && u.pathname.startsWith(`/repos/${missingRepo}/`)) return j({ message: 'Not Found' }, 404);
    if (u.pathname === `/repos/${prRepo}/pulls` && u.search.includes('open')) return j([{ number: 93, title: 'mock PR', html_url: `https://github.com/${prRepo}/pull/93`, labels: [{ name: 'review:needs-maintainer' }], user: { login: 'g' } }]);
    if (u.pathname === `/repos/${okRepo}/pulls` && u.search.includes('open')) return j([{ number: 41, title: 'mock approved PR', html_url: `https://github.com/${okRepo}/pull/41`, labels: [{ name: 'review:approved' }], user: { login: 'g' } }]);
    if (u.pathname === `/repos/${okRepo}/actions/runs`) return j({ workflow_runs: [{ workflow_id: 1, name: 'ci', head_branch: 'main', status: 'completed', conclusion: 'failure', event: 'push', html_url: 'https://github.com/x/run/1', updated_at: now }] });
    if (u.pathname.endsWith('/actions/runs')) return j({ workflow_runs: [] });
    if (u.pathname.endsWith('/issues')) return j([{ number: 5, title: 'mock issue', html_url: 'https://github.com/x/issues/5', milestone: { title: 'R1: mock' } }]);
    if (u.pathname.endsWith('/pulls')) return j([]);
    return j({ message: 'unmocked ' + u.pathname }, 404);
  });
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
  const want = { mode: 'live', rows: 2, invalid: 1, prs: prRepo === okRepo ? 1 : 2, runs: 1, prErr: missingRepo ? [missingRepo] : [] };
  const fails = Object.keys(want).filter(k => JSON.stringify(st[k]) !== JSON.stringify(want[k])).map(k => `${k}: got ${JSON.stringify(st[k])}, want ${JSON.stringify(want[k])}`);
  if (errs.length) fails.push('page errors: ' + errs.join(' | '));
  if (noAuth) fails.push(`${noAuth} GitHub calls without a token`);
  console.log(JSON.stringify({ st, calls: seen.length, fails }, null, 1));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
