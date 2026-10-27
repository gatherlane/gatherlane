// SPDX-License-Identifier: Apache-2.0
// Building: floors, rooms, furniture and the cast for the example fleet. Layout only, no status lives here.
// Each agent id here must match an id in config.js and the --agent the reporter is given.
(function (G) {
  const { F } = G.Iso;

  // look = {species, fur, outfit, accent, prop, hat, batik}
  const A = (id, name, room, x, y, look, extra = {}) => ({ id, name, room, x, y, look, ...extra });

  const LEVELS = [
    {
      id: 'den', key: null, name: 'Coordination Den', short: 'B', W: 24, D: 10,
      floor: '#cfd3e6', wall: '#b7bdd9', tint: '#5d6694',
      rooms: [
        { id: 'den', name: 'Orchestrator den', x: 0, y: 0, w: 16, d: 10, col: '#c9cde4' },
        { id: 'servers', name: 'Runner closet', x: 16, y: 0, w: 8, d: 10, col: '#bfc4dc' },
      ],
      agents: [
        A('orchestrator-1', 'Orchestrator session', 'den', 8, 5.6, { species: 'octopus', fur: '#c79be0', outfit: '#c79be0', prop: 'baton' }),
      ],
      furnish(sc) {
        sc.wall('y0', G.Iso.wallBoardY0(sc, 2, 14, .7, 2.1, '#fbf7ee'));
        sc.wall('y0', cycleBoard(sc, 2, 14));
        sc.add(12, F.table(sc, 6, 3.4, 4.4, 1.8, '#b9a4d9'));
        sc.add(21, F.rack(sc, 17.6, 1)); sc.add(22, F.rack(sc, 18.8, 1));
        sc.add(26, F.desk(sc, 19, 5, { screen: '#5ee0c2' }));
        sc.add(4, F.plant(sc, 1, 8.4));
        sc.add(5, F.lamp(sc, 8, 4.4, 2.3));
      },
    },
    {
      id: 'product', key: 1, name: 'Product Studio', short: '1', site: 'acme.example', W: 30, D: 12,
      floor: '#f4e3d7', wall: '#f2d4c4', tint: '#d0674f',
      rooms: [
        { id: 'build', name: 'Build room', x: 0, y: 0, w: 12, d: 6, col: '#e9dff3' },
        { id: 'support', name: 'Support desk', x: 12, y: 0, w: 10, d: 6, col: '#fde1e4' },
        { id: 'triage', name: 'Triage', x: 22, y: 0, w: 8, d: 6, col: '#fff1cc' },
        { id: 'lounge', name: 'Lounge', x: 0, y: 6, w: 30, d: 6, col: '#f6e8dc' },
      ],
      agents: [
        A('acme/implementer', 'implementer', 'build', 3.4, 3.4, { species: 'beaver', fur: '#a0673f', outfit: '#6c9fd6', prop: 'wrench' }),
        A('acme/pr-reviewer', 'pr-reviewer', 'build', 8.2, 3.4, { species: 'owl', fur: '#c7a27c', outfit: '#6c9fd6', prop: 'magnifier' }),
        A('acme/support', 'support', 'support', 16.6, 3.4, { species: 'cat', fur: '#f5e2c8', outfit: '#f28fa2', hat: 'headset', prop: 'phone' }),
        A('acme/triage', 'triage', 'triage', 25.8, 3.4, { species: 'fox', fur: '#f39a5a', outfit: '#6fb8b1', prop: 'clipboard' }),
      ],
      furnish(sc) {
        sc.add(2.5, F.desk(sc, 2.7, 1.6, { mug: true })); sc.add(3.2, F.chair(sc, 3.2, 2.6, '#9a86c9'));
        sc.add(7.3, F.desk(sc, 7.5, 1.6)); sc.add(8, F.chair(sc, 8, 2.6, '#9a86c9'));
        sc.add(16, F.desk(sc, 15.9, 1.6)); sc.add(16.6, F.chair(sc, 16.4, 2.6, '#f2a0b0'));
        sc.add(19, F.sign(sc, 20, 1.0, 2.0, 'customer inbox', '#fff8ec', '#b2475e', .24));
        sc.add(25, F.desk(sc, 25.1, 1.6)); sc.add(25.8, F.chair(sc, 25.6, 2.6, '#c9b56a'));
        sc.add(28, F.plant(sc, 29, .4));
        sc.add(10, F.rug(sc, 3, 7.4, 9, 3.4, '#f1c6b4'));
        sc.add(14, F.table(sc, 5.5, 8.3, 4, 1.6, '#e8c9a0'));
        sc.add(22, F.beanbag(sc, 17, 8.6, '#a9c7f2')); sc.add(24, F.beanbag(sc, 19.4, 8.8, '#ffd98a'));
        sc.add(26, F.arcade(sc, 25, 7.2));
        sc.add(15, F.plant(sc, .5, 10.8, 1.2)); sc.add(36, F.plant(sc, 29, 10.8));
        sc.add(5, F.lamp(sc, 5, 3)); sc.add(5, F.lamp(sc, 17, 3)); sc.add(5, F.lamp(sc, 26, 3));
      },
    },
    {
      id: 'growth', key: 2, name: 'Growth Floor', short: '2', W: 30, D: 12,
      floor: '#e3eef2', wall: '#cfe3ea', tint: '#3d8fb0',
      rooms: [
        { id: 'content', name: 'Content pod', x: 0, y: 0, w: 10, d: 6, col: '#fbe6ef' },
        { id: 'insights', name: 'Insights', x: 10, y: 0, w: 10, d: 6, col: '#e2f4e4' },
        { id: 'launch', name: 'Launch room (being built)', x: 20, y: 0, w: 10, d: 6, col: '#ece6dc', construction: true },
        { id: 'library', name: 'Library', x: 0, y: 6, w: 30, d: 6, col: '#efdcc0' },
      ],
      agents: [
        A('growth/writer', 'writer', 'content', 5, 3.4, { species: 'owl', fur: '#b08a6a', outfit: '#9ed7c4', prop: 'pencil' }),
        A('growth/analytics', 'analytics', 'insights', 15, 3.4, { species: 'penguin', fur: '#3b3a4a', outfit: '#9fd3f0', prop: 'chart' }),
        A('growth/social', 'social', 'launch', 25, 3.6, { species: 'monkey', fur: '#b5835a', outfit: '#f08a5d', hat: 'hardhat', prop: 'camera' }),
      ],
      furnish(sc) {
        sc.add(4.6, F.desk(sc, 4.4, 1.6)); sc.add(5.2, F.chair(sc, 4.9, 2.6, '#f7a8b8'));
        sc.add(14.6, F.desk(sc, 14.4, 1.6, { screen: '#9fd3f0' })); sc.add(15.2, F.chair(sc, 14.9, 2.6, '#9fd3f0'));
        sc.add(27, F.cone(sc, 21.6, 4.6)); sc.add(29.5, F.cone(sc, 28.6, 4.8));
        sc.add(27, F.tape(sc, 20.6, .4, 9.0, 5.2));
        sc.add(9, F.shelf(sc, 1, 6.4, 3.6)); sc.add(12, F.shelf(sc, 5.2, 6.4, 3.6));
        sc.add(20, F.rug(sc, 12, 7.4, 8, 3.4, '#bfe0d2'));
        sc.add(22, F.table(sc, 14, 8.3, 4, 1.4, '#e8c9a0'));
        sc.add(30, F.tree(sc, 26, 9));
        sc.add(5, F.lamp(sc, 5, 3)); sc.add(5, F.lamp(sc, 15, 3));
      },
    },
    {
      id: 'supervisor', key: null, name: 'Supervisor office', short: 'S', W: 14, D: 9,
      floor: '#f6ead7', wall: '#cfe6f2', tint: '#7a4b2a', glass: true, offset: [8, 1.5],
      rooms: [{ id: 'office', name: 'Maintainer · supervisor', x: 0, y: 0, w: 14, d: 9, col: '#f6ead7' }],
      agents: [A('maintainer', 'Maintainer (you)', 'office', 7.4, 5, { species: 'human', fur: '#d7a77e', outfit: '#3d6f8f', prop: 'mug' }, { human: true })],
      furnish(sc) {
        sc.add(9, F.rug(sc, 2.5, 2.6, 9, 4.6, '#e9b9a0'));
        sc.add(11, sc.box(6, 3, 0, 3, 1.1, .75, '#a0673f', { top: '#c08a5e' }));
        sc.add(12, F.plant(sc, 1, 7.8, 1.3)); sc.add(22, F.plant(sc, 12.8, 7.6, 1.2));
        sc.add(5, F.lamp(sc, 7.4, 3.6));
      },
    },
  ];

  // ---------- wall decorations ----------
  function cycleBoard(sc, x0, x1) {
    const steps = ['issue', 'implementer', 'pr-reviewer', 'review:approved', 'you merge'];
    let g = '';
    steps.forEach((t, i) => {
      const x = x0 + .4 + i * ((x1 - x0 - .6) / steps.length);
      g += sc.poly([[x, .06, 1.15], [x + 2, .06, 1.15], [x + 2, .06, 1.75], [x, .06, 1.75]], ['#dfe8fb', '#efe2f4', '#e2f4e4', '#fff1cc', '#fde1e4'][i], 'stroke="#b7bdd9" stroke-width=".8"');
      const [tx, ty] = sc.p(x + 1, .06, 1.38);
      g += `<text x="${G.Iso.f1(tx)}" y="${G.Iso.f1(ty)}" font-size="${G.Iso.f1(Math.max(6, sc.s * .2))}" text-anchor="middle" fill="#4a4f7a" font-weight="700">${t}</text>`;
    });
    return g;
  }

  G.Building = { LEVELS };
})(typeof window !== 'undefined' ? window : globalThis);
