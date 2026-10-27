// SPDX-License-Identifier: Apache-2.0
// Checks the generated building (app/js/layout.js): node tests/layout.test.js
// Runs on the example config, this repository's instance config, and small edge cases.
const assert = require('assert'), path = require('path'), fs = require('fs');
const load = f => { delete globalThis.GATHERLANE_CONFIG; delete globalThis.Building; require(path.resolve(f)); return globalThis.GATHERLANE_CONFIG; };
delete require.cache[require.resolve('../app/js/layout.js')];
require('../app/js/layout.js');
const { fromConfig, opOfId } = globalThis.Layout;

function check(name, cfg) {
  const { LEVELS } = fromConfig(cfg);
  const placed = LEVELS.flatMap(L => L.agents.filter(a => !a.human).map(a => ({ ...a, L })));
  const ids = Object.keys(cfg.agents);
  assert.deepStrictEqual(placed.map(a => a.id).sort(), [...ids].sort(), `${name}: every agent placed exactly once`);
  for (const a of placed) {
    assert.strictEqual(a.room, cfg.agents[a.id].room || 'team', `${name}: ${a.id} in the room config.js gives it`);
    const r = a.L.rooms.find(r => r.id === a.room);
    assert.ok(r && a.x > r.x && a.x < r.x + r.w && a.y > r.y && a.y < r.y + r.d, `${name}: ${a.id} inside room ${a.room}`);
    assert.ok(a.x > 0 && a.x < a.L.W && a.y > 0 && a.y < a.L.D, `${name}: ${a.id} on its floor`);
    const lv = (cfg.operations[opOfId(cfg, a.id)] || {}).level;
    if (lv) assert.strictEqual(a.L.id, lv, `${name}: ${a.id} on its operation's floor`);
  }
  for (const L of LEVELS) for (let i = 0; i < L.agents.length; i++) for (let j = i + 1; j < L.agents.length; j++) {
    const [p, q] = [L.agents[i], L.agents[j]];
    assert.ok(Math.hypot(p.x - q.x, p.y - q.y) >= 1.5, `${name}: ${p.id} and ${q.id} do not overlap`);
  }
  const keys = LEVELS.map(L => L.key).filter(Boolean);
  assert.deepStrictEqual(keys, keys.map((_, i) => i + 1), `${name}: floor keys run 1..n`);
  assert.ok(keys.length <= 9, `${name}: at most 9 keyed floors`);
  assert.strictEqual(new Set(LEVELS.map(L => L.id)).size, LEVELS.length, `${name}: floor ids unique`);
  for (const L of LEVELS) assert.strictEqual(new Set(L.rooms.map(r => r.id)).size, L.rooms.length, `${name}: room ids unique on ${L.id}`);
  assert.strictEqual(LEVELS.some(L => L.id === 'supervisor'), !!cfg.maintainer, `${name}: supervisor office only with a maintainer`);
  assert.ok(JSON.stringify(fromConfig(cfg).LEVELS) === JSON.stringify(LEVELS), `${name}: deterministic`);
  return LEVELS;
}

const results = [];
const run = (name, f) => { try { f(); results.push(`ok   ${name}`); } catch (e) { results.push(`FAIL ${name}: ${e.message.split('\n')[0]}`); } };

run('example config', () => check('example', load('examples/instance/config.js')));
if (fs.existsSync('app/instance/config.js')) run('instance config', () => check('instance', load('app/instance/config.js')));
run('agents without rooms share one team room; unknown operation gets its own floor', () => {
  const L = check('bare', { operations: { web: { name: 'Web', level: 'web' } }, agents: { 'web/a': {}, 'web/b': {}, 'ops/c': {} } });
  assert.deepStrictEqual(L.map(l => [l.id, l.name, l.rooms.map(r => r.id)]), [['web', 'Web', ['team', 'lounge']], ['ops', 'ops', ['team', 'lounge']]]);
});
run('fallback operation is the den, without a key, first', () => {
  const L = check('den', { fallbackOperation: 'shared', operations: { shared: { level: 'den' }, web: { level: 'web' } }, agents: { 'orchestrator-1': {}, 'web/a': {} } });
  assert.deepStrictEqual(L.map(l => [l.id, l.key]), [['den', null], ['web', 1]]);
});
run('nine agents in one room wrap into rows', () => {
  const agents = Object.fromEntries([...Array(9)].map((_, i) => [`web/a${i}`, {}]));
  const [L] = check('rows', { operations: { web: { level: 'web' } }, agents });
  assert.strictEqual(new Set(L.agents.map(a => a.y)).size, 3);
});
run('a look in config wins over the generated one', () => {
  const look = { species: 'owl', fur: '#000', outfit: '#fff', prop: 'book' };
  const [L] = check('look', { operations: { web: { level: 'web' } }, agents: { 'web/a': { look } } });
  assert.deepStrictEqual(L.agents[0].look, look);
});

console.log(results.join('\n'));
process.exit(results.some(r => r.startsWith('FAIL')) ? 1 : 0);
