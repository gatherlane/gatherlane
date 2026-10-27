// SPDX-License-Identifier: Apache-2.0
// Compose levels into SVG views, and derive the human inbox from status + GitHub data.
(function (G) {
  const { Scene, mascot, badge, STATES, shade, f1 } = G.Iso;
  const C = 0.8660254;

  // ---------- status interpretation (data only) ----------
  function intervalMinutes(cron) {
    if (!cron) return null;
    const [m, h] = cron.trim().split(/\s+/);
    const step = s => { const k = /^\*\/(\d+)$/.exec(s); return k ? +k[1] : null; };
    if (step(m)) return step(m);
    if (m !== '*' && h === '*') return 60;
    if (step(h)) return step(h) * 60;
    return 24 * 60; // daily or weekly: treat as daily for staleness
  }
  function isStale(r, now) {
    if (!r || !r.updated_at || r.status === 'not_deployed') return false;
    const iv = intervalMinutes(r.schedule && r.schedule.cron);
    const lim = r.stale_after_minutes || (iv ? Math.max(30, iv * 2) : 60 * 24);
    return (now - Date.parse(r.updated_at)) / 60000 > lim;
  }
  function statusMap(rows, control, now = Date.now()) {
    const m = {};
    for (const r of rows || []) m[r.agent] = { ...r, paused: !!(control && control.paused && control.paused[r.agent]), stale: isStale(r, now) };
    return m;
  }

  function sideWall(sc, L, side, H, o) {
    const sd = sc.sides()[side];
    const [[x1, y1], [x2, y2]] = sd;
    const P = (t, z) => [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, z];
    const len = Math.hypot(x2 - x1, y2 - y1);
    const wallCol = side === 'y0' || side === 'yD' ? L.wall : shade(L.wall, .93);
    let g = '';
    if (L.glass) {
      g += sc.poly([P(0, 0), P(1, 0), P(1, H), P(0, H)], '#cfe8f5', 'opacity=".5" stroke="#8fb8d0"');
      for (let t = 0; t <= len; t += 2) g += `<polyline points="${sc.pts([P(t / len, 0), P(t / len, H)])}" stroke="#a9c4d4" stroke-width="1.4"/>`;
      if (o.night) g += sc.poly([P(0, .1), P(1, .1), P(1, H), P(0, H)], '#1d2440', 'opacity=".45"');
      return g;
    }
    g += sc.poly([P(0, 0), P(1, 0), P(1, H), P(0, H)], wallCol, `stroke="${shade(wallCol, .8)}"`);
    g += sc.poly([P(0, H * .12), P(1, H * .12), P(1, H * .24), P(0, H * .24)], 'url(#kawungWall)', 'opacity=".5"');
    const win = o.night ? '#ffd982' : '#d7eef8';
    const skip = (L.windowSkip && L.windowSkip[side]) || [];
    for (let t = 2; t < len - 1; t += 4) {
      if (skip.some(([a, b]) => t >= a && t <= b)) continue;
      g += sc.poly([P(t / len, 1.05), P((t + 1.8) / len, 1.05), P((t + 1.8) / len, 2.15), P(t / len, 2.15)], win, `stroke="${shade(wallCol, .7)}" stroke-width="1"`);
    }
    return g;
  }

  function drawLevel(sc, L, st, o = {}) {
    const { W, D } = L, H = 2.6;
    let base = sc.box(0, 0, -.45, W, D, .45, L.floor, { top: L.floor, left: shade(L.tint, 1.55), right: shade(L.tint, 1.7), stroke: shade(L.tint, 1.1) });
    for (const r of L.rooms) {
      const pts = [[r.x, r.y, .01], [r.x + r.w, r.y, .01], [r.x + r.w, r.y + r.d, .01], [r.x, r.y + r.d, .01]];
      base += `<g class="room" data-room="${L.id}:${r.id}">` + sc.poly(pts, r.col, `stroke="${shade(r.col, .82)}" stroke-width="1"`);
      if (r.construction) base += sc.poly(pts, 'url(#hatch)', 'opacity=".55"');
      base += '</g>';
    }
    for (const side of ['y0', 'xW', 'yD', 'x0']) if (sc.isBack(side)) base += sideWall(sc, L, side, H, o);
    sc.reset();
    for (const r of L.rooms) {
      if (r.y > 0) { sc.reset(); sc.add(0, sc.box(r.x, r.y - .06, 0, r.w, .12, .55, shade(r.col, .9), { top: '#ffffff' })); }
      if (r.x > 0) { sc.reset(); sc.add(0, sc.box(r.x - .06, r.y, 0, .12, r.d, .55, shade(r.col, .9), { top: '#ffffff' })); }
    }
    sc.reset();
    L.furnish(sc);
    const extra = o.extraAgents || [];
    for (const a of [...L.agents, ...extra]) {
      const s = a.walker ? null : (st[a.id] || (a.decor || a.human ? null : { status: 'unknown' }));
      const [px, py] = sc.p(a.x, a.y, 0);
      sc.reset();
      const k = sc.s * (o.charScale || 1);
      const dim = o.focus && !(s && (s.status === 'running' || s.status === 'waiting'));
      const delay = ((a.x * 7 + a.y * 13) % 30) / 10;
      let g = `<g class="agent${a.decor || a.human || a.walker ? ' decor' : ''}" ${a.decor || a.walker ? '' : `data-agent="${a.id}"`}>`;
      if (o.selected === a.id) g += `<ellipse cx="${f1(px)}" cy="${f1(py)}" rx="${f1(k * .7)}" ry="${f1(k * .3)}" fill="none" stroke="#EE7E1A" stroke-width="2.4" stroke-dasharray="5 3"/>`;
      g += `<g class="bob" style="animation-delay:-${delay}s">` + mascot(px, py, k, a.look, { dim: dim || (s && (s.status === 'not_deployed' || s.status === 'unknown')), sleep: s && s.status === 'sleeping' }) + '</g>';
      if (s) g += `<g ${dim ? 'opacity=".35"' : ''}>` + badge(px, py - k * 1.75 - (o.pill ? 6 : 2), s, o.pill ? 'pill' : 'dot', { text: o.pill ? (s.status === 'unknown' ? 'no data' : (STATES[s.status] || STATES.unknown).label) : null }) + '</g>';
      if (o.names && !a.decor && !a.walker) {
        const nm = a.name, fs = Math.max(9, k * .24), w = nm.length * fs * .56 + 10;
        g += `<rect x="${f1(px - w / 2)}" y="${f1(py + 4)}" width="${f1(w)}" height="${f1(fs * 1.5)}" rx="${f1(fs * .5)}" fill="white" opacity=".88"/><text x="${f1(px)}" y="${f1(py + 4 + fs * 1.1)}" font-size="${f1(fs)}" text-anchor="middle" fill="#4a3b33" font-weight="600">${esc(nm)}</text>`;
      }
      g += '</g>';
      sc.addAt(sc.depth(a.x, a.y) + .5, g);
    }
    let out = base + sc.flush();
    if (o.roomLabels !== false) for (const r of L.rooms) {
      const cs = [[r.x + .35, r.y + r.d - .35], [r.x + r.w - .35, r.y + r.d - .35], [r.x + r.w - .35, r.y + .35], [r.x + .35, r.y + .35]].map(([x, y]) => sc.p(x, y, .02));
      const [px, py] = cs.reduce((a, b) => (b[1] > a[1] + .5 || (Math.abs(b[1] - a[1]) <= .5 && b[0] < a[0]) ? b : a));
      const fs = Math.max(9, sc.s * .3), w = r.name.length * fs * .57 + fs;
      out += `<g class="room-label" data-room="${L.id}:${r.id}" transform="translate(${f1(px - w / 2)},${f1(py - 4)})"><rect x="0" y="${f1(-fs * 1.05)}" width="${f1(w)}" height="${f1(fs * 1.55)}" rx="${f1(fs * .4)}" fill="${shade(r.col, .55)}" opacity=".9"/><text x="${f1(fs * .5)}" y="${f1(fs * .12)}" font-size="${f1(fs)}" fill="white" font-weight="650">${esc(r.name)}</text></g>`;
    }
    if (L.onHold) {
      const [px, py] = sc.p(L.W * .45, L.D * .5, 3.3);
      const fs = Math.max(10, sc.s * .36), w = L.onHold.length * fs * .55 + fs * 2;
      out += `<g transform="translate(${f1(px)},${f1(py)})"><rect x="${f1(-w / 2)}" y="${f1(-fs * 1.2)}" width="${f1(w)}" height="${f1(fs * 1.9)}" rx="${f1(fs * .5)}" fill="#3b3a4a" opacity=".86"/><text x="0" y="${f1(fs * .2)}" font-size="${f1(fs)}" fill="#ffe39a" text-anchor="middle" font-weight="650">${esc(L.onHold)}</text></g>`;
    }
    if (o.night) out = `<g class="night">${out}</g>`;
    return out;
  }
  const esc = t => String(t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function defs() {
    return `<defs>
      <pattern id="kawung" width="16" height="16" patternUnits="userSpaceOnUse">
        <g fill="none" stroke="#7a4b2a" stroke-width="1" opacity=".7">
          <ellipse cx="8" cy="3.6" rx="2.4" ry="3.4"/><ellipse cx="8" cy="12.4" rx="2.4" ry="3.4"/>
          <ellipse cx="3.6" cy="8" rx="3.4" ry="2.4"/><ellipse cx="12.4" cy="8" rx="3.4" ry="2.4"/>
        </g><circle cx="8" cy="8" r=".9" fill="#7a4b2a" opacity=".6"/></pattern>
      <pattern id="kawungWall" width="12" height="12" patternUnits="userSpaceOnUse">
        <g fill="none" stroke="#a0673f" stroke-width=".8"><ellipse cx="6" cy="2.8" rx="1.8" ry="2.6"/><ellipse cx="6" cy="9.2" rx="1.8" ry="2.6"/><ellipse cx="2.8" cy="6" rx="2.6" ry="1.8"/><ellipse cx="9.2" cy="6" rx="2.6" ry="1.8"/></g></pattern>
      <pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(30)"><line x1="0" y1="0" x2="0" y2="10" stroke="#c9b48a" stroke-width="3"/></pattern>
      <pattern id="stripes" width="12" height="12" patternUnits="userSpaceOnUse"><rect width="6" height="12" fill="#fff4e6"/></pattern>
      <radialGradient id="warm"><stop offset="0" stop-color="#ffd98a" stop-opacity=".38"/><stop offset="1" stop-color="#ffd98a" stop-opacity="0"/></radialGradient>
    </defs>`;
  }

  function counts(L, st) {
    const c = {};
    for (const a of L.agents) { if (a.decor || a.human) continue; const s = (st[a.id] || {}).status || 'unknown'; c[s] = (c[s] || 0) + 1; }
    return c;
  }

  function chipsSVG(c) {
    const order = ['waiting', 'failed', 'blocked', 'running', 'idle', 'sleeping', 'not_deployed', 'unknown'];
    const name = k => k === 'not_deployed' ? 'not deployed' : k === 'unknown' ? 'no data' : k;
    const chips = order.filter(k => c[k]).map(k => ({ k, t: `${c[k]} ${name(k)}` })).map(x => ({ ...x, w: x.t.length * 6.4 + 22 }));
    const rows = [[]]; let rw = 0;
    chips.forEach(ch => { if (rw + ch.w > 330 && rows[rows.length - 1].length) { rows.push([]); rw = 0; } rows[rows.length - 1].push(ch); rw += ch.w + 6; });
    let lab = '';
    rows.forEach((row, ri) => {
      let cx = -row.reduce((a, r) => a + r.w + 6, 0);
      row.forEach(({ k, t, w }) => {
        const S = STATES[k]; const hollow = k === 'not_deployed' || k === 'unknown';
        lab += `<g transform="translate(${f1(cx)},${34 + ri * 25})" text-anchor="start"><rect width="${f1(w)}" height="20" rx="10" fill="${hollow ? 'white' : shade(S.c, 1.75)}" stroke="${S.c}" ${hollow ? 'stroke-dasharray="3 2"' : ''}/><circle cx="11" cy="10" r="4.5" fill="${hollow ? 'white' : S.c}" stroke="${S.c}"/><text x="20" y="14" font-size="11" font-weight="650" fill="${shade(S.c, .6)}">${t}</text></g>`;
        cx += w + 6;
      });
    });
    return lab;
  }

  // Whole building: exploded floor stack
  function buildingSVG(st, o = {}) {
    const s = o.s || 14, gap = o.gap || 19;
    const levels = G.Building.LEVELS;
    const rot = o.rot || 0;
    const width = 1180, ox = 720, top = 60;
    const oy0 = top + (levels.length - 1) * gap * s + 2.6 * s + 40;
    let out = '';
    levels.forEach((L, i) => {
      let lox = ox, loy = oy0;
      if (L.offset) {
        const tmp = new Scene(s, 0, 0, rot, 30, 12);
        const [cx, cy] = tmp.p(L.offset[0] + L.W / 2, L.offset[1] + L.D / 2, 0);
        const tmp2 = new Scene(s, 0, 0, rot, L.W, L.D);
        const [dx, dy] = tmp2.p(L.W / 2, L.D / 2, 0);
        lox += cx - dx; loy += cy - dy;
      }
      const sc = new Scene(s, lox, loy, rot, L.W, L.D);
      sc.z0 = i * gap;
      out += `<g class="level" data-level="${L.id}">` + drawLevel(sc, L, st, { roomLabels: false, focus: o.focus, charScale: 1.3, night: o.night }) + '</g>';
      const corners = [[0, 0], [L.W, 0], [L.W, L.D], [0, L.D]].map(([x, y]) => sc.p(x, y, 0));
      const [lx, ly] = corners.reduce((a, b) => b[0] < a[0] ? b : a);
      let lab = `<g class="level-label" data-level="${L.id}" transform="translate(${f1(lx - 26)},${f1(ly - 28)})" text-anchor="end">`;
      lab += `<text x="0" y="0" font-size="17" font-weight="750" fill="var(--ink)"><tspan fill="${L.tint}">${L.key || L.short}</tspan>  ${esc(L.name)}</text>`;
      if (L.site) lab += `<text x="0" y="17" font-size="11.5" fill="var(--muted)">${L.site}</text>`;
      lab += chipsSVG(counts(L, st)) + '</g>';
      out += lab;
    });
    const h = oy0 + 21 * s + 60;
    return { svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" font-family="Inter, system-ui, sans-serif">${defs()}${out}</svg>`, w: width, h };
  }

  function floorSVG(levelId, st, o = {}) {
    const L = G.Building.LEVELS.find(l => l.id === levelId);
    const s = o.s || 34, rot = o.rot || 0;
    const odd = rot & 1, RW = odd ? L.D : L.W, RD = odd ? L.W : L.D;
    const width = (RW + RD) * C * s + 120, h = (RW + RD) * .5 * s + 2.6 * s + 140;
    const sc = new Scene(s, RD * C * s + 60, 2.6 * s + 70, rot, L.W, L.D);
    const body = drawLevel(sc, L, st, { pill: true, names: true, charScale: o.charScale || 1.4, focus: o.focus, selected: o.selected, extraAgents: o.extraAgents, night: o.night });
    return { svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f1(width)} ${f1(h)}" width="${f1(width)}" height="${f1(h)}" font-family="Inter, system-ui, sans-serif">${defs()}${body}</svg>`, w: width, h, scene: sc };
  }

  G.Office = { statusMap, buildingSVG, floorSVG, counts, isStale, intervalMinutes, esc };
})(typeof window !== 'undefined' ? window : globalThis);
