// SPDX-License-Identifier: Apache-2.0
// Which app the browser tests open. By default app/ with its own instance/. With
// GATHERLANE_INSTANCE=<dir> (for example examples/instance), a copy of app/ with that instance.
const fs = require('fs'), os = require('os'), path = require('path');

function appUrl() {
  const app = path.resolve(__dirname, '../app');
  const inst = process.env.GATHERLANE_INSTANCE;
  if (!inst) return 'file://' + path.join(app, 'index.html');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gatherlane-app-'));
  fs.cpSync(app, dir, { recursive: true });
  fs.rmSync(path.join(dir, 'instance'), { recursive: true, force: true });
  fs.cpSync(path.resolve(inst), path.join(dir, 'instance'), { recursive: true });
  return 'file://' + path.join(dir, 'index.html');
}

// The parts of the instance the tests steer by, read from the page itself.
const readInstance = page => page.evaluate(() => {
  const levels = Building.LEVELS.filter(L => L.key).sort((a, b) => a.key - b.key);
  const sample = Object.fromEntries(SAMPLE.rows.map(r => [r.agent, r.status]));
  const cast = L => L.agents.filter(a => !a.decor && !a.human);
  const first = levels[0], second = levels[1] || levels[0];
  const agent = (cast(first).find(a => sample[a.id] === 'waiting') || cast(first)[0]).id;
  const other = cast(first).find(a => a.id !== agent);
  const repos = [...new Set(Object.values(GATHERLANE_CONFIG.operations).flatMap(o => o.repos || []))];
  const owners = [...new Set([GATHERLANE_CONFIG.statusRepo, ...repos].map(r => r.split('/')[0]))];
  return {
    first: { key: String(first.key), id: first.id, room: `${first.id}:${first.rooms[0].id}` },
    second: { key: String(second.key), id: second.id },
    agent, other: other ? other.id : agent, statusRepo: GATHERLANE_CONFIG.statusRepo, repos, owners,
    ops: Object.fromEntries(Object.entries(GATHERLANE_CONFIG.operations).map(([k, o]) => [k, o.agentPrefixes || []])),
    fallback: GATHERLANE_CONFIG.fallbackOperation || 'shared',
  };
});

// Same rule as tools/gatherlane.py and app.js.
function pathOf(id, inst) {
  const head = id.split('/')[0], map = {};
  for (const [k, ps] of Object.entries(inst.ops)) for (const p of ps) map[p] = k;
  const op = map[head] || map[head.split('-')[0]] || (id.includes('/') ? head : inst.fallback);
  const parts = id.split('/');
  return `status/${op}/${parts.length === 2 && parts[0] === op ? parts[1] : id.replace('/', '-')}.json`;
}

module.exports = { appUrl, readInstance, pathOf };
