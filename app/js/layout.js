// SPDX-License-Identifier: Apache-2.0
// Building generated from config.js, used when the instance's building.js does not define one.
// Layout only: floors, rooms, desks and characters. No status lives here.
//
// config.js drives it:
//   operations.<op>.level   the floor the operation's agents sit on; operations sharing a level share a floor
//   operations.<op>.rooms   optional [{ id, name }] in order; otherwise rooms come from the agents
//   agents.<id>.room        optional room id (default 'team'); agents.<id>.look overrides the generated look
//   agents.<id>.name        optional label (default: the part of the id after the slash)
//   maintainer              when set, a glass supervisor office with "<maintainer> (you)" on top
(function (G) {
  const SPECIES = ['bear', 'beaver', 'cat', 'fox', 'owl', 'otter', 'raccoon', 'rabbit', 'penguin', 'frog', 'duck', 'monkey', 'panda', 'goat', 'meerkat', 'turtle', 'mouse', 'elephant'];
  const FUR = ['#c89a6e', '#a0673f', '#f5e2c8', '#f39a5a', '#c7a27c', '#8a6a50', '#a6a3a6', '#f7f1ea', '#3b3a4a', '#9fd18a', '#fff4d6', '#b5835a', '#e3c08f'];
  const OUTFIT = ['#6c9fd6', '#f28fa2', '#6fb8b1', '#9ed7c4', '#f2c14e', '#8d6cc7', '#e4605e', '#7aa7e0', '#3d8fb0', '#f08a5d', '#c9b56a', '#5d6694'];
  const PROPS = ['laptop', 'wrench', 'magnifier', 'pencil', 'chart', 'clipboard', 'phone', 'book', 'kanban', 'star', 'camera', 'globe'];
  const FLOORS = [ // floor, wall, tint
    ['#f4e3d7', '#f2d4c4', '#d0674f'], ['#e3eef2', '#cfe3ea', '#3d8fb0'], ['#e6efe4', '#d3e5d2', '#3f8f5f'],
    ['#f1e9f2', '#e6d8ea', '#8d5fa8'], ['#efe6d2', '#e8d7b8', '#b8862b'], ['#f3e6cf', '#f1d9c0', '#a0673f'],
  ];
  const ROOMS = ['#e9dff3', '#fde1e4', '#fff1cc', '#e2f4e4', '#dfe8fb', '#fbe6ef', '#f6efdb', '#ece4f7'];
  const PER_ROW = 4, MAX_ROW = 6, DESK = 3, ROW = 4.6, LOUNGE = 4; // desks per row (min, max), spacing, lounge depth

  const hash = s => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };
  const pick = (list, id, salt) => list[hash(salt + id) % list.length];
  const lookFor = id => ({ species: pick(SPECIES, id, 's'), fur: pick(FUR, id, 'f'), outfit: pick(OUTFIT, id, 'o'), prop: pick(PROPS, id, 'p') });

  // Same rule as tools/gatherlane.py: an agentPrefixes match, else the id's first part, else the fallback.
  function opOfId(cfg, id) {
    const head = id.split('/')[0];
    for (const [k, o] of Object.entries(cfg.operations || {})) {
      const ps = o.agentPrefixes || [];
      if (ps.includes(head) || ps.includes(head.split('-')[0])) return k;
    }
    return id.includes('/') ? head : cfg.fallbackOperation || 'shared';
  }

  function fromConfig(cfg) {
    const ops = cfg.operations || {};
    const fallback = cfg.fallbackOperation || 'shared';
    // floors in the order their operations are listed; the fallback operation's floor is the den
    const floors = [];
    const floorOf = {};
    for (const [k, o] of Object.entries(ops)) {
      const lv = o.level || k;
      if (!floorOf[lv]) floors.push(floorOf[lv] = { id: lv, ops: [], agents: [] });
      floorOf[lv].ops.push(k);
    }
    for (const [id, a] of Object.entries(cfg.agents || {})) {
      const op = opOfId(cfg, id), lv = (ops[op] && ops[op].level) || op; // an operation missing from config gets its own floor
      if (!floorOf[lv]) floors.push(floorOf[lv] = { id: lv, ops: [], agents: [] });
      floorOf[lv].agents.push({ id, ...a });
    }
    const denId = ops[fallback] ? ops[fallback].level || fallback : null;
    const ordered = [...floors.filter(f => f.id === denId), ...floors.filter(f => f.id !== denId)].filter(f => f.agents.length);
    let key = 0;
    const LEVELS = ordered.map((f, i) => level(f, f.id === denId ? null : ++key, ops, i));
    if (cfg.maintainer) LEVELS.push(supervisor(cfg.maintainer));
    return { LEVELS, generated: true };
  }

  function level(f, key, ops, i) {
    const op = ops[f.ops[0]] || {};
    const declared = f.ops.flatMap(k => ops[k].rooms || []);
    const order = [...declared.map(r => r.id), ...f.agents.map(a => a.room || 'team')].filter((r, j, all) => all.indexOf(r) === j);
    const names = Object.fromEntries(declared.map(r => [r.id, r.name]));
    let x = 0;
    const rooms = [], agents = [], desks = [];
    order.forEach((rid, ri) => {
      const cast = f.agents.filter(a => (a.room || 'team') === rid);
      if (!cast.length) return;
      // big rooms get wider rows (up to MAX_ROW) so they stay shallow
      const per = Math.min(MAX_ROW, Math.max(PER_ROW, Math.ceil(Math.sqrt(cast.length * 1.5))));
      const cols = Math.min(per, cast.length), rows = Math.ceil(cast.length / per);
      const w = Math.max(6, cols * DESK + 1.5), d = Math.max(6, rows * ROW + 1.8);
      rooms.push({ id: rid, name: names[rid] || (rid === 'team' ? 'Team' : rid), x, y: 0, w, d, col: ROOMS[(i * 3 + ri) % ROOMS.length] });
      cast.forEach((a, n) => {
        const dx = x + 1.2 + (n % per) * DESK, dy = 1.2 + Math.floor(n / per) * ROW;
        desks.push([dx, dy]);
        agents.push({ id: a.id, name: a.name || a.id.split('/').pop(), room: rid, x: dx + .7, y: dy + 1.5, look: a.look || lookFor(a.id) });
      });
      x += w;
    });
    const W = Math.max(16, x), Dr = Math.max(...rooms.map(r => r.d));
    rooms.forEach(r => { r.d = Dr; });
    rooms.push({ id: 'lounge', name: 'Lounge', x: 0, y: Dr, w: W, d: LOUNGE, col: '#f6e8dc' });
    const [floor, wall, tint] = FLOORS[i % FLOORS.length];
    const name = f.ops.length > 1 ? f.ops.map(k => ops[k].name || k).join(' · ') : op.name || f.id;
    return {
      id: f.id, key, name, short: key ? String(key) : 'B', site: op.site, note: op.note, W, D: Dr + LOUNGE,
      floor, wall, tint, rooms, agents,
      furnish(sc) {
        const { F } = G.Iso;
        desks.forEach(([dx, dy]) => { sc.add(dx + dy + .6, F.desk(sc, dx, dy)); sc.add(dx + dy + 1.2, F.chair(sc, dx + .5, dy + 1, '#9a86c9')); });
        rooms.filter(r => r.id !== 'lounge').forEach(r => sc.add(5, F.lamp(sc, r.x + r.w / 2, r.d / 2)));
        sc.add(Dr + 1, F.plant(sc, .5, Dr + LOUNGE - .8, 1.1));
        sc.add(W + Dr, F.plant(sc, W - .8, Dr + LOUNGE - .8));
        if (W >= 16) { sc.add(W / 4 + Dr, F.rug(sc, W / 4 - 3, Dr + .6, 6, LOUNGE - 1.2, '#f1c6b4')); sc.add(W / 4 + Dr + 1, F.table(sc, W / 4 - 1.5, Dr + 1.3, 3, 1.2)); } // clear of the walker's start at W/2
      },
    };
  }

  function supervisor(who) {
    return {
      id: 'supervisor', key: null, name: 'Supervisor office', short: 'S', W: 12, D: 8,
      floor: '#f6ead7', wall: '#cfe6f2', tint: '#7a4b2a', glass: true, offset: [9, 2],
      rooms: [{ id: 'office', name: `${who} · supervisor`, x: 0, y: 0, w: 12, d: 8, col: '#f6ead7' }],
      agents: [{ id: who, name: `${who} (you)`, room: 'office', x: 6, y: 4.6, look: { species: 'human', fur: '#d7a77e', outfit: '#3d6f8f', prop: 'mug' }, human: true }],
      furnish(sc) {
        const { F } = G.Iso;
        sc.add(9, F.rug(sc, 2, 2, 8, 4, '#e9b9a0'));
        sc.add(11, sc.box(4.6, 2.6, 0, 3, 1.1, .75, '#a0673f', { top: '#c08a5e' }));
        sc.add(12, F.plant(sc, 1, 6.8, 1.2));
      },
    };
  }

  // What Settings lists about config.js, the building and the status files read. These are facts about
  // files, never an agent status. `reported` is the agent ids that have a status file.
  function check(cfg, levels, reported) {
    const problems = [];
    const reports = a => !a.human && !a.decor && !a.walker; // the characters expected to have a status file
    // The maintainer's office holds only the maintainer and decoration. Any other floor with that id, from a
    // declared operation, an agent prefix or fallbackOperation, cannot be walked on.
    for (const L of levels.filter(L => L.id === 'supervisor')) {
      const cast = L.agents.filter(reports);
      if (!cast.length) continue;
      const ops = [...new Set(cast.map(a => opOfId(cfg, a.id)))].map(k => `“${k}”`).join(', ');
      problems.push(`operation ${ops} (${cast.map(a => a.id).join(', ')}) is on the level id “supervisor”, which is reserved for the maintainer's office`);
    }
    const keyed = levels.filter(L => L.key).length;
    if (keyed > 9) problems.push(`${keyed} floors have number keys, but only 1 to 9 work; give some operations a shared level`);
    // office.js shows a status file's status on any drawn character except the walker, so only an id it
    // cannot show is unplaced; the maintainer and decoration are just not expected to report
    const drawn = levels.flatMap(L => L.agents.filter(a => !a.walker).map(a => a.id));
    const placed = levels.flatMap(L => L.agents.filter(reports).map(a => a.id));
    const seen = new Set(reported);
    return { problems, unplaced: [...seen].filter(id => !drawn.includes(id)).sort(), silent: placed.filter(id => !seen.has(id)).sort() };
  }

  G.Layout = { fromConfig, opOfId, lookFor, check };
  if (!G.Building && G.GATHERLANE_CONFIG) G.Building = fromConfig(G.GATHERLANE_CONFIG);
})(typeof window !== 'undefined' ? window : globalThis);
