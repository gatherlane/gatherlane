// SPDX-License-Identifier: Apache-2.0
// Checks the generated building (app/js/layout.js): node tests/layout.test.js
// Runs on the example config, this repository's instance config, and small edge cases.
// A hand-drawn instance building.js is checked against its config.js too.
const assert = require('assert'), path = require('path'), fs = require('fs');
const load = f => { delete globalThis.GATHERLANE_CONFIG; delete globalThis.Building; delete require.cache[path.resolve(f)]; require(path.resolve(f)); return globalThis.GATHERLANE_CONFIG; };
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

run('config check: reporting agents off the map, configured agents with no status file', () => {
  const cfg = { operations: { web: { level: 'web' } }, agents: { 'web/a': {}, 'web/b': {} }, maintainer: 'robin' };
  const r = globalThis.Layout.check(cfg, fromConfig(cfg).LEVELS, ['web/a', 'web/ghost', 'ops/x']);
  assert.deepStrictEqual(r, { problems: [], unplaced: ['ops/x', 'web/ghost'], silent: ['web/b'] });
});
run('config check: the maintainer is not an agent that should report', () => {
  const cfg = { operations: { web: { level: 'web' } }, agents: { 'web/a': {} }, maintainer: 'robin' };
  assert.deepStrictEqual(globalThis.Layout.check(cfg, fromConfig(cfg).LEVELS, ['web/a']), { problems: [], unplaced: [], silent: [] });
});
run('config check: decorative characters in a drawn building never report', () => {
  const levels = [{ id: 'web', key: 1, agents: [{ id: 'web/a' }, { id: 'office-cat', decor: true }, { id: 'visitor', walker: true }, { id: 'robin', human: true }] }];
  assert.deepStrictEqual(globalThis.Layout.check({ operations: {} }, levels, []), { problems: [], unplaced: [], silent: ['web/a'] });
});
run('config check: a level called supervisor is a problem', () => {
  const cfg = { operations: { boss: { level: 'supervisor' } }, agents: { 'boss/a': {} } };
  const { problems } = globalThis.Layout.check(cfg, fromConfig(cfg).LEVELS, []);
  assert.strictEqual(problems.length, 1);
  assert.match(problems[0], /“boss”.*supervisor/);
});
run('config check: an agent family called supervisor is a problem', () => {
  const cfg = { operations: { web: { level: 'web' } }, agents: { 'web/a': {}, 'supervisor/x': {} }, maintainer: 'robin' };
  const { problems } = globalThis.Layout.check(cfg, fromConfig(cfg).LEVELS, []);
  assert.strictEqual(problems.length, 1);
  assert.match(problems[0], /“supervisor”.*supervisor\/x/);
});
run('config check: a fallback operation called supervisor is a problem', () => {
  const cfg = { fallbackOperation: 'supervisor', operations: { web: { level: 'web' } }, agents: { 'web/a': {}, solo: {} }, maintainer: 'robin' };
  const { problems } = globalThis.Layout.check(cfg, fromConfig(cfg).LEVELS, []);
  assert.strictEqual(problems.length, 1);
  assert.match(problems[0], /“supervisor”.*solo/);
});
run('config check: a drawn supervisor office with the maintainer and a cat is fine', () => {
  const levels = [{ id: 'web', key: 1, agents: [{ id: 'web/a' }] }, { id: 'supervisor', key: null, agents: [{ id: 'robin', human: true }, { id: 'cat', decor: true }] }];
  assert.deepStrictEqual(globalThis.Layout.check({ operations: {} }, levels, []).problems, []);
});
run('config check: a character office.js shows a status on is not unplaced; the walker is', () => {
  const cfg = { operations: { web: { level: 'web' } }, agents: { 'web/a': {} }, maintainer: 'robin' };
  const levels = [...fromConfig(cfg).LEVELS, { id: 'den', key: null, agents: [{ id: 'office-cat', decor: true }, { id: 'visitor', walker: true }] }];
  assert.deepStrictEqual(globalThis.Layout.check(cfg, levels, ['web/a', 'robin', 'office-cat', 'visitor']), { problems: [], unplaced: ['visitor'], silent: [] });
});
run('config check: more than nine keyed floors is a problem; nine is fine', () => {
  const office = n => {
    const operations = {}, agents = {};
    for (let i = 0; i < n; i++) { operations['op' + i] = { level: 'f' + i }; agents[`op${i}/a`] = {}; }
    return { operations, agents };
  };
  const nine = office(9), ten = office(10);
  assert.deepStrictEqual(globalThis.Layout.check(nine, fromConfig(nine).LEVELS, []).problems, []);
  const { problems } = globalThis.Layout.check(ten, fromConfig(ten).LEVELS, []);
  assert.strictEqual(problems.length, 1);
  assert.match(problems[0], /^10 floors/);
});
run('the example and instance configs pass the check', () => {
  for (const f of ['examples/instance/config.js', 'app/instance/config.js'].filter(f => fs.existsSync(f))) {
    const cfg = load(f);
    assert.deepStrictEqual(globalThis.Layout.check(cfg, fromConfig(cfg).LEVELS, []).problems, [], f);
  }
});

// A hand-drawn building.js is what the instance renders, so it is held to config.js the same way.
// examples/building-custom.js is the hand-drawn reference for the example config. A building.js that
// defines no Building is left to the generated one, which the checks above cover, so it is a skip.
const drawnChecks = [
  ['examples/instance', 'examples/instance/config.js', 'examples/instance/building.js'],
  ['app/instance', 'app/instance/config.js', 'app/instance/building.js'],
  ['examples/building-custom.js', 'examples/instance/config.js', 'examples/building-custom.js'],
];
for (const [name, cfgFile, bFile] of drawnChecks) {
  if (!fs.existsSync(cfgFile) || !fs.existsSync(bFile)) continue;
  const label = `${name}: the building drawn matches config.js`;
  const cfg = load(cfgFile);
  delete require.cache[require.resolve('../app/js/render.js')]; require('../app/js/render.js');
  const f = path.resolve(bFile); delete require.cache[f]; require(f);
  if (!globalThis.Building) { results.push(`skip ${label} (no Building defined, the generated one is used)`); continue; }
  run(label, () => {
    const LEVELS = globalThis.Building.LEVELS;
    const drawn = LEVELS.flatMap(L => L.agents.filter(a => !a.human && !a.decor && !a.walker).map(a => ({ id: a.id, L: L.id })));
    for (const id of Object.keys(cfg.agents)) {
      const at = drawn.filter(a => a.id === id);
      assert.strictEqual(at.length, 1, `${id} is drawn exactly once, not ${at.length} times`);
      const lv = (cfg.operations[opOfId(cfg, id)] || {}).level;
      if (lv) assert.strictEqual(at[0].L, lv, `${id} is drawn on its operation's level`);
    }
    const keys = LEVELS.map(L => L.key).filter(Boolean);
    assert.deepStrictEqual([...keys].sort((a, b) => a - b), keys.map((_, i) => i + 1), `floor keys are unique and run 1..n: ${keys}`);
    const { problems, unplaced } = globalThis.Layout.check(cfg, LEVELS, Object.keys(cfg.agents));
    assert.deepStrictEqual({ problems, unplaced }, { problems: [], unplaced: [] }, 'Layout.check: no problems, nothing unplaced');
  });
}

console.log(results.join('\n'));
process.exit(results.some(r => r.startsWith('FAIL')) ? 1 : 0);
