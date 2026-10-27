// SPDX-License-Identifier: Apache-2.0
// Isometric renderer: building model + status -> SVG string. No dependencies.
(function (G) {
  const C = 0.8660254;

  function shade(hex, f) {
    const n = parseInt(hex.slice(1), 16);
    const ch = [n >> 16, (n >> 8) & 255, n & 255].map(v =>
      Math.max(0, Math.min(255, Math.round(f < 1 ? v * f : v + (255 - v) * (f - 1)))));
    return '#' + ch.map(v => v.toString(16).padStart(2, '0')).join('');
  }
  const f1 = v => (+v).toFixed(1);

  // ---------- status vocabulary (data-driven, never animated into existence) ----------
  const STATES = {
    running:      { c: '#2E9E68', label: 'running' },
    waiting:      { c: '#EE7E1A', label: 'waiting for you' },
    blocked:      { c: '#8662CC', label: 'blocked' },
    failed:       { c: '#D9434B', label: 'failed' },
    idle:         { c: '#7F93AD', label: 'idle' },
    sleeping:     { c: '#5B63C9', label: 'sleeping' },
    not_deployed: { c: '#A7A29B', label: 'not deployed' },
    unknown:      { c: '#BDB6AC', label: 'no data' },
  };

  function glyph(state, x, y, r) {
    const w = 'white';
    switch (state) {
      case 'running': return `<path d="M${f1(x - r * .32)},${f1(y - r * .45)} L${f1(x + r * .5)},${f1(y)} L${f1(x - r * .32)},${f1(y + r * .45)}Z" fill="${w}"/>`;
      case 'waiting': return `<rect x="${f1(x - r * .13)}" y="${f1(y - r * .55)}" width="${f1(r * .26)}" height="${f1(r * .68)}" rx="${f1(r * .1)}" fill="${w}"/><circle cx="${f1(x)}" cy="${f1(y + r * .43)}" r="${f1(r * .15)}" fill="${w}"/>`;
      case 'blocked': return `<rect x="${f1(x - r * .5)}" y="${f1(y - r * .14)}" width="${f1(r)}" height="${f1(r * .28)}" rx="${f1(r * .1)}" fill="${w}"/>`;
      case 'failed': return `<path d="M${f1(x - r * .38)},${f1(y - r * .38)}L${f1(x + r * .38)},${f1(y + r * .38)}M${f1(x + r * .38)},${f1(y - r * .38)}L${f1(x - r * .38)},${f1(y + r * .38)}" stroke="${w}" stroke-width="${f1(r * .28)}" stroke-linecap="round"/>`;
      case 'idle': return `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(r * .22)}" fill="${w}"/>`;
      case 'sleeping': return `<path d="M${f1(x - r * .35)},${f1(y - r * .35)}H${f1(x + r * .35)}L${f1(x - r * .35)},${f1(y + r * .35)}H${f1(x + r * .35)}" stroke="${w}" stroke-width="${f1(r * .2)}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>`;
      default: return '';
    }
  }

  // badge: dot (overview) or pill (floor view). Shape + glyph carry meaning, not only colour.
  function badge(x, y, st, mode, opts = {}) {
    const S = STATES[st.status] || STATES.unknown;
    const hollow = st.status === 'not_deployed' || st.status === 'unknown';
    const r = mode === 'pill' ? 11 : 6.5;
    let g = '';
    if (st.status === 'waiting') {
      g += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(r * 1.75)}" fill="${S.c}" opacity=".18"/><circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(r * 1.4)}" fill="none" stroke="${S.c}" stroke-width="1.5" opacity=".55"/>`;
    }
    if (mode === 'pill') {
      const txt = opts.text || S.label;
      const tw = txt.length * 6.3 + 30;
      const bx = x - r;
      g += `<rect x="${f1(bx - 2)}" y="${f1(y - r - 2)}" width="${f1(tw + 4)}" height="${f1(r * 2 + 4)}" rx="${f1(r + 2)}" fill="white" opacity=".92"/>`;
      g += `<rect x="${f1(bx)}" y="${f1(y - r)}" width="${f1(tw)}" height="${f1(r * 2)}" rx="${f1(r)}" fill="${hollow ? 'white' : S.c}" stroke="${S.c}" stroke-width="1.5" ${hollow ? 'stroke-dasharray="3 2.5"' : ''}/>`;
      g += hollow ? (st.status === 'unknown' ? `<text x="${f1(x)}" y="${f1(y + 4)}" font-size="11" text-anchor="middle" font-weight="800" fill="#9a9087">?</text>` : '') : glyph(st.status, x, y, r * .78);
      g += `<text x="${f1(x + r + 3)}" y="${f1(y + 4)}" font-size="11.5" font-weight="650" fill="${hollow ? '#7a7268' : 'white'}">${txt}</text>`;
      if (st.paused) g += pauseMark(bx + tw + 8, y);
    } else {
      g += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(r + 1.6)}" fill="white" opacity=".95"/>`;
      g += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(r)}" fill="${hollow ? 'white' : S.c}" stroke="${S.c}" stroke-width="1.4" ${hollow ? 'stroke-dasharray="2.2 1.8"' : ''}/>`;
      g += hollow ? (st.status === 'unknown' ? `<text x="${f1(x)}" y="${f1(y + 3.2)}" font-size="9" text-anchor="middle" font-weight="800" fill="#9a9087">?</text>` : '') : glyph(st.status, x, y, r);
      if (st.paused) g += pauseMark(x + r + 5, y - r, .7);
    }
    if (st.stale) g += `<text x="${f1(x - r - 2)}" y="${f1(y - r - 3)}" font-size="9" fill="#a0522d" font-weight="700">stale</text>`;
    return g;
  }
  function pauseMark(x, y, k = 1) {
    return `<g transform="translate(${f1(x)},${f1(y)}) scale(${k})"><circle r="8" fill="#3b3a4a"/><rect x="-3.6" y="-4" width="2.6" height="8" rx="1" fill="white"/><rect x="1" y="-4" width="2.6" height="8" rx="1" fill="white"/></g>`;
  }

  // ---------- props held by characters (job hints) ----------
  function prop(kind, x, y, k) {
    const s = k; const ln = '#4a3b33';
    const P = {
      laptop: `<rect x="${x - .3 * s}" y="${y - .2 * s}" width="${.6 * s}" height="${.38 * s}" rx="${.04 * s}" fill="#d9e4ef" stroke="${ln}" stroke-width=".8"/><rect x="${x - .38 * s}" y="${y + .18 * s}" width="${.76 * s}" height="${.08 * s}" rx="${.03 * s}" fill="#9aa9b8"/>`,
      headset: `<path d="M${x - .3 * s},${y} a${.3 * s},${.3 * s} 0 0 1 ${.6 * s},0" fill="none" stroke="#3b3a4a" stroke-width="${.08 * s}"/><rect x="${x - .36 * s}" y="${y - .05 * s}" width="${.14 * s}" height="${.22 * s}" rx="${.05 * s}" fill="#3b3a4a"/>`,
      coin: `<circle cx="${x}" cy="${y}" r="${.2 * s}" fill="#f2c14e" stroke="#b8862b" stroke-width=".9"/><text x="${x}" y="${y + .08 * s}" font-size="${.26 * s}" text-anchor="middle" fill="#8a5b12" font-weight="800">Rp</text>`,
      hardhat: '',
      kanban: `<rect x="${x - .26 * s}" y="${y - .26 * s}" width="${.52 * s}" height="${.46 * s}" rx="${.04 * s}" fill="#fff6d6" stroke="${ln}" stroke-width=".8"/><rect x="${x - .2 * s}" y="${y - .18 * s}" width="${.14 * s}" height="${.1 * s}" fill="#f7a8b8"/><rect x="${x + .02 * s}" y="${y - .18 * s}" width="${.14 * s}" height="${.1 * s}" fill="#9ed7c4"/><rect x="${x - .2 * s}" y="${y - .02 * s}" width="${.14 * s}" height="${.1 * s}" fill="#a9c7f2"/>`,
      wrench: `<path d="M${x - .25 * s},${y + .25 * s} L${x + .12 * s},${y - .12 * s}" stroke="#8a95a3" stroke-width="${.1 * s}" stroke-linecap="round"/><circle cx="${x + .17 * s}" cy="${y - .17 * s}" r="${.11 * s}" fill="none" stroke="#8a95a3" stroke-width="${.07 * s}"/>`,
      bugnet: `<path d="M${x - .3 * s},${y + .35 * s} L${x + .05 * s},${y - .05 * s}" stroke="#9b7650" stroke-width="${.06 * s}"/><ellipse cx="${x + .15 * s}" cy="${y - .17 * s}" rx="${.17 * s}" ry="${.14 * s}" fill="#ffffffaa" stroke="#6a8c6a" stroke-width=".9"/>`,
      rocket: `<path d="M${x},${y - .38 * s} q${.16 * s},${.16 * s} ${.12 * s},${.48 * s} h-${.24 * s} q-${.04 * s},-${.32 * s} ${.12 * s},-${.48 * s}z" fill="#f4f1ee" stroke="${ln}" stroke-width=".8"/><circle cx="${x}" cy="${y - .12 * s}" r="${.05 * s}" fill="#6fb3e0"/><path d="M${x - .12 * s},${y + .1 * s} l-${.1 * s},${.12 * s} h${.1 * s}z M${x + .12 * s},${y + .1 * s} l${.1 * s},${.12 * s} h-${.1 * s}z" fill="#e4605e"/><path d="M${x - .06 * s},${y + .12 * s} q${.06 * s},${.22 * s} ${.12 * s},0" fill="#f6a945"/>`,
      pencil: `<path d="M${x - .25 * s},${y + .28 * s} L${x + .18 * s},${y - .2 * s}" stroke="#f2c14e" stroke-width="${.12 * s}" stroke-linecap="butt"/><path d="M${x - .25 * s},${y + .28 * s} l${.02 * s},-${.1 * s} l${.07 * s},${.07 * s}z" fill="${ln}"/>`,
      brush: `<path d="M${x - .22 * s},${y + .26 * s} L${x + .1 * s},${y - .1 * s}" stroke="#9b7650" stroke-width="${.06 * s}"/><ellipse cx="${x + .15 * s}" cy="${y - .16 * s}" rx="${.06 * s}" ry="${.12 * s}" transform="rotate(40 ${x + .15 * s} ${y - .16 * s})" fill="#e8739a"/><circle cx="${x - .18 * s}" cy="${y - .05 * s}" r="${.13 * s}" fill="#fff3e0" stroke="#c9a77c" stroke-width=".8"/><circle cx="${x - .22 * s}" cy="${y - .09 * s}" r="${.03 * s}" fill="#5aa9e6"/><circle cx="${x - .13 * s}" cy="${y - .07 * s}" r="${.03 * s}" fill="#f2c14e"/>`,
      mic: `<rect x="${x - .07 * s}" y="${y - .3 * s}" width="${.14 * s}" height="${.24 * s}" rx="${.07 * s}" fill="#5b5f6b"/><path d="M${x},${y - .05 * s} v${.3 * s}" stroke="#5b5f6b" stroke-width="${.05 * s}"/>`,
      globe: `<circle cx="${x}" cy="${y}" r="${.2 * s}" fill="#9fd3f0" stroke="#4d7fa3" stroke-width=".9"/><path d="M${x - .2 * s},${y} h${.4 * s} M${x},${y - .2 * s} q${.14 * s},${.2 * s} 0 ${.4 * s} q-${.14 * s},-${.2 * s} 0 -${.4 * s}" fill="none" stroke="#4d7fa3" stroke-width=".7"/>`,
      star: `<path d="${starPath(x, y, .22 * s)}" fill="#f6c343" stroke="#c9952a" stroke-width=".8"/>`,
      phone: `<rect x="${x - .13 * s}" y="${y - .24 * s}" width="${.26 * s}" height="${.46 * s}" rx="${.05 * s}" fill="#3b3a4a"/><rect x="${x - .1 * s}" y="${y - .19 * s}" width="${.2 * s}" height="${.32 * s}" fill="#8fe0a8"/>`,
      megaphone: `<path d="M${x - .22 * s},${y - .06 * s} l${.36 * s},-${.16 * s} v${.4 * s} l-${.36 * s},-${.16 * s}z" fill="#f08a5d" stroke="${ln}" stroke-width=".7"/>`,
      chart: `<rect x="${x - .24 * s}" y="${y - .22 * s}" width="${.48 * s}" height="${.44 * s}" rx="${.04 * s}" fill="white" stroke="${ln}" stroke-width=".7"/><rect x="${x - .17 * s}" y="${y + .02 * s}" width="${.08 * s}" height="${.13 * s}" fill="#7cc4a4"/><rect x="${x - .04 * s}" y="${y - .08 * s}" width="${.08 * s}" height="${.23 * s}" fill="#7aa7e0"/><rect x="${x + .09 * s}" y="${y - .15 * s}" width="${.08 * s}" height="${.3 * s}" fill="#f0a35e"/>`,
      envelope: `<rect x="${x - .24 * s}" y="${y - .16 * s}" width="${.48 * s}" height="${.32 * s}" rx="${.03 * s}" fill="white" stroke="${ln}" stroke-width=".7"/><path d="M${x - .24 * s},${y - .16 * s} l${.24 * s},${.18 * s} l${.24 * s},-${.18 * s}" fill="none" stroke="${ln}" stroke-width=".7"/>`,
      book: `<rect x="${x - .22 * s}" y="${y - .2 * s}" width="${.44 * s}" height="${.4 * s}" rx="${.03 * s}" fill="#5d7fb5" stroke="${ln}" stroke-width=".7"/><rect x="${x - .16 * s}" y="${y - .14 * s}" width="${.32 * s}" height="${.06 * s}" fill="#f6e7c1"/>`,
      shield: `<path d="M${x},${y - .26 * s} l${.22 * s},${.08 * s} v${.14 * s} q0,${.18 * s} -${.22 * s},${.3 * s} q-${.22 * s},-${.12 * s} -${.22 * s},-${.3 * s} v-${.14 * s}z" fill="#7cc4a4" stroke="#3f7f66" stroke-width=".8"/>`,
      scales: `<path d="M${x},${y - .26 * s} v${.46 * s} M${x - .24 * s},${y - .16 * s} h${.48 * s}" stroke="#b8862b" stroke-width="${.05 * s}"/><path d="M${x - .32 * s},${y + .02 * s} q${.08 * s},${.1 * s} ${.16 * s},0z M${x + .16 * s},${y + .02 * s} q${.08 * s},${.1 * s} ${.16 * s},0z" fill="#f2c14e" stroke="#b8862b" stroke-width=".6"/>`,
      tag: `<path d="M${x - .2 * s},${y - .14 * s} h${.26 * s} l${.16 * s},${.14 * s} l-${.16 * s},${.14 * s} h-${.26 * s}z" fill="#f7a8b8" stroke="${ln}" stroke-width=".7"/><circle cx="${x - .12 * s}" cy="${y}" r="${.03 * s}" fill="${ln}"/>`,
      box: `<rect x="${x - .2 * s}" y="${y - .16 * s}" width="${.4 * s}" height="${.34 * s}" fill="#d8b07a" stroke="#8a6638" stroke-width=".8"/><path d="M${x - .2 * s},${y - .04 * s} h${.4 * s}" stroke="#8a6638" stroke-width=".7"/>`,
      camera: `<rect x="${x - .24 * s}" y="${y - .14 * s}" width="${.48 * s}" height="${.3 * s}" rx="${.05 * s}" fill="#4f5664"/><circle cx="${x}" cy="${y + .01 * s}" r="${.09 * s}" fill="#a9c7f2" stroke="white" stroke-width=".8"/>`,
      link: `<rect x="${x - .26 * s}" y="${y - .08 * s}" width="${.3 * s}" height="${.16 * s}" rx="${.08 * s}" fill="none" stroke="#5aa9e6" stroke-width="${.06 * s}"/><rect x="${x - .04 * s}" y="${y - .08 * s}" width="${.3 * s}" height="${.16 * s}" rx="${.08 * s}" fill="none" stroke="#5aa9e6" stroke-width="${.06 * s}"/>`,
      crate: `<rect x="${x - .22 * s}" y="${y - .2 * s}" width="${.44 * s}" height="${.38 * s}" fill="#c99a62" stroke="#7d5a2e" stroke-width=".8"/><path d="M${x - .22 * s},${y - .2 * s} l${.44 * s},${.38 * s} M${x + .22 * s},${y - .2 * s} l-${.44 * s},${.38 * s}" stroke="#7d5a2e" stroke-width=".7"/>`,
      clipboard: `<rect x="${x - .2 * s}" y="${y - .26 * s}" width="${.4 * s}" height="${.5 * s}" rx="${.04 * s}" fill="#c99a62" stroke="#7d5a2e" stroke-width=".8"/><rect x="${x - .15 * s}" y="${y - .19 * s}" width="${.3 * s}" height="${.38 * s}" fill="white"/><rect x="${x - .08 * s}" y="${y - .3 * s}" width="${.16 * s}" height="${.08 * s}" fill="#8a95a3"/><path d="M${x - .1 * s},${y - .08 * s}h${.2 * s}M${x - .1 * s},${y + .02 * s}h${.2 * s}M${x - .1 * s},${y + .12 * s}h${.12 * s}" stroke="#9aa9b8" stroke-width=".7"/>`,
      whistle: `<circle cx="${x}" cy="${y}" r="${.12 * s}" fill="#e5c74a" stroke="#9a7f1c" stroke-width=".8"/><rect x="${x}" y="${y - .12 * s}" width="${.22 * s}" height="${.1 * s}" fill="#e5c74a" stroke="#9a7f1c" stroke-width=".8"/>`,
      magnifier: `<circle cx="${x + .04 * s}" cy="${y - .08 * s}" r="${.17 * s}" fill="#d7efff" fill-opacity=".8" stroke="#6b5440" stroke-width="${.06 * s}"/><path d="M${x - .08 * s},${y + .05 * s} L${x - .28 * s},${y + .3 * s}" stroke="#6b5440" stroke-width="${.08 * s}" stroke-linecap="round"/>`,
      briefcase: `<rect x="${x - .24 * s}" y="${y - .12 * s}" width="${.48 * s}" height="${.34 * s}" rx="${.05 * s}" fill="#a0673f" stroke="#5e3a20" stroke-width=".8"/><rect x="${x - .08 * s}" y="${y - .2 * s}" width="${.16 * s}" height="${.09 * s}" fill="none" stroke="#5e3a20" stroke-width=".8"/>`,
      binoculars: `<circle cx="${x - .11 * s}" cy="${y}" r="${.11 * s}" fill="#4f5664"/><circle cx="${x + .11 * s}" cy="${y}" r="${.11 * s}" fill="#4f5664"/><circle cx="${x - .11 * s}" cy="${y}" r="${.05 * s}" fill="#a9c7f2"/><circle cx="${x + .11 * s}" cy="${y}" r="${.05 * s}" fill="#a9c7f2"/>`,
      tablet: `<rect x="${x - .2 * s}" y="${y - .26 * s}" width="${.4 * s}" height="${.5 * s}" rx="${.05 * s}" fill="#3b3a4a"/><rect x="${x - .16 * s}" y="${y - .21 * s}" width="${.32 * s}" height="${.38 * s}" fill="#ffe7a8"/>`,
      mug: `<rect x="${x - .12 * s}" y="${y - .12 * s}" width="${.22 * s}" height="${.26 * s}" rx="${.04 * s}" fill="#f4efe6" stroke="${ln}" stroke-width=".7"/><path d="M${x + .1 * s},${y - .06 * s} q${.12 * s},${.06 * s} 0 ${.14 * s}" fill="none" stroke="${ln}" stroke-width=".7"/>`,
      baton: `<path d="M${x - .22 * s},${y + .22 * s} L${x + .2 * s},${y - .26 * s}" stroke="#f4efe6" stroke-width="${.05 * s}" stroke-linecap="round"/><circle cx="${x + .2 * s}" cy="${y - .26 * s}" r="${.04 * s}" fill="#f2c14e"/>`,
    };
    return P[kind] || '';
  }
  function starPath(cx, cy, r) {
    let d = '';
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * .45 : r;
      d += (i ? 'L' : 'M') + f1(cx + rr * Math.cos(a)) + ',' + f1(cy + rr * Math.sin(a));
    }
    return d + 'Z';
  }

  // ---------- mascots ----------
  // a = {species, fur, outfit, accent, prop}; (x,y) = feet on screen; k = px per unit
  function mascot(x, y, k, a, opt = {}) {
    const ln = '#4a3b33', sw = Math.max(.7, k * .03);
    const fur = a.fur || '#e9b67c', out = a.outfit || '#8fb8de';
    const hx = x, hy = y - 1.12 * k, hr = .36 * k;
    const bodyTop = y - .8 * k;
    let g = `<g ${opt.dim ? 'opacity=".45"' : ''}>`;
    g += `<ellipse cx="${f1(x)}" cy="${f1(y)}" rx="${f1(.42 * k)}" ry="${f1(.15 * k)}" fill="#3a2a1f" opacity=".16"/>`;
    const sp = a.species;
    if (sp === 'turtle') g += `<ellipse cx="${f1(x - .1 * k)}" cy="${f1(y - .45 * k)}" rx="${f1(.42 * k)}" ry="${f1(.36 * k)}" fill="#8fbf7a" stroke="${ln}" stroke-width="${sw}"/>`;
    if (sp === 'octopus') {
      for (let i = 0; i < 6; i++) {
        const dx = (i - 2.5) * .13 * k;
        g += `<path d="M${f1(x + dx)},${f1(y - .55 * k)} q${f1(dx * .8)},${f1(.35 * k)} ${f1(dx * .6 + (i % 2 ? .1 : -.1) * k)},${f1(.5 * k)}" stroke="${fur}" stroke-width="${f1(.12 * k)}" fill="none" stroke-linecap="round"/>`;
      }
    } else {
      // legs
      g += `<rect x="${f1(x - .22 * k)}" y="${f1(y - .22 * k)}" width="${f1(.16 * k)}" height="${f1(.22 * k)}" rx="${f1(.06 * k)}" fill="${shade(out, .65)}"/><rect x="${f1(x + .06 * k)}" y="${f1(y - .22 * k)}" width="${f1(.16 * k)}" height="${f1(.22 * k)}" rx="${f1(.06 * k)}" fill="${shade(out, .65)}"/>`;
      g += `<rect x="${f1(x - .32 * k)}" y="${f1(bodyTop)}" width="${f1(.64 * k)}" height="${f1(.64 * k)}" rx="${f1(.24 * k)}" fill="${out}" stroke="${ln}" stroke-width="${sw}"/>`;
      if (a.batik) g += `<rect x="${f1(x - .32 * k)}" y="${f1(bodyTop)}" width="${f1(.64 * k)}" height="${f1(.64 * k)}" rx="${f1(.24 * k)}" fill="url(#kawung)" opacity=".55"/>`;
      if (a.accent) g += `<path d="M${f1(x - .1 * k)},${f1(bodyTop + .02 * k)} l${f1(.1 * k)},${f1(.16 * k)} l${f1(.1 * k)},-${f1(.16 * k)}" fill="${a.accent}"/>`;
      // arms
      g += `<ellipse cx="${f1(x - .34 * k)}" cy="${f1(bodyTop + .3 * k)}" rx="${f1(.08 * k)}" ry="${f1(.17 * k)}" fill="${out}" stroke="${ln}" stroke-width="${sw}"/>`;
    }
    // ears / head decorations behind head
    const E = (cx, cy, rx, ry, col, rot = 0) => `<ellipse cx="${f1(cx)}" cy="${f1(cy)}" rx="${f1(rx)}" ry="${f1(ry)}" fill="${col}" stroke="${ln}" stroke-width="${sw}" transform="rotate(${rot} ${f1(cx)} ${f1(cy)})"/>`;
    const T = (pts, col) => `<path d="M${pts.map(p => f1(p[0]) + ',' + f1(p[1])).join(' L')}Z" fill="${col}" stroke="${ln}" stroke-width="${sw}" stroke-linejoin="round"/>`;
    const inner = a.inner || '#f7c9c0';
    switch (sp) {
      case 'cat': case 'fox':
        g += T([[hx - hr * .95, hy - hr * .2], [hx - hr * .7, hy - hr * 1.35], [hx - hr * .15, hy - hr * .85]], fur);
        g += T([[hx + hr * .95, hy - hr * .2], [hx + hr * .7, hy - hr * 1.35], [hx + hr * .15, hy - hr * .85]], fur); break;
      case 'rabbit':
        g += E(hx - hr * .4, hy - hr * 1.3, hr * .24, hr * .7, fur, -8) + E(hx + hr * .4, hy - hr * 1.3, hr * .24, hr * .7, fur, 8);
        g += E(hx - hr * .4, hy - hr * 1.3, hr * .1, hr * .5, inner, -8) + E(hx + hr * .4, hy - hr * 1.3, hr * .1, hr * .5, inner, 8); break;
      case 'bear': case 'panda': case 'beaver': case 'mouse': case 'raccoon': {
        const er = sp === 'mouse' ? hr * .5 : hr * .3, col = sp === 'panda' ? '#3b3a4a' : fur;
        g += E(hx - hr * .75, hy - hr * .75, er, er, col) + E(hx + hr * .75, hy - hr * .75, er, er, col); break; }
      case 'monkey': case 'otter': case 'meerkat':
        g += E(hx - hr * 1.0, hy, hr * .26, hr * .26, fur) + E(hx + hr * 1.0, hy, hr * .26, hr * .26, fur); break;
      case 'elephant':
        g += E(hx - hr * 1.05, hy, hr * .55, hr * .7, fur) + E(hx + hr * 1.05, hy, hr * .55, hr * .7, fur); break;
      case 'kancil':
        g += E(hx - hr * .75, hy - hr * .9, hr * .16, hr * .4, fur, -30) + E(hx + hr * .75, hy - hr * .9, hr * .16, hr * .4, fur, 30); break;
      case 'goat': case 'cow': case 'buffalo': {
        const hc = sp === 'buffalo' ? '#6b5b4e' : '#efe3c8';
        if (sp === 'buffalo') g += `<path d="M${f1(hx - hr * .6)},${f1(hy - hr * .6)} q-${f1(hr * .9)},-${f1(hr * .1)} -${f1(hr * .6)},-${f1(hr * .9)} M${f1(hx + hr * .6)},${f1(hy - hr * .6)} q${f1(hr * .9)},-${f1(hr * .1)} ${f1(hr * .6)},-${f1(hr * .9)}" stroke="${hc}" stroke-width="${f1(hr * .22)}" fill="none" stroke-linecap="round"/>`;
        else g += `<path d="M${f1(hx - hr * .45)},${f1(hy - hr * .8)} l-${f1(hr * .2)},-${f1(hr * .5)} M${f1(hx + hr * .45)},${f1(hy - hr * .8)} l${f1(hr * .2)},-${f1(hr * .5)}" stroke="${hc}" stroke-width="${f1(hr * .18)}" stroke-linecap="round"/>`;
        g += E(hx - hr * 1.0, hy - hr * .2, hr * .32, hr * .16, fur, 20) + E(hx + hr * 1.0, hy - hr * .2, hr * .32, hr * .16, fur, -20); break; }
      case 'owl':
        g += T([[hx - hr * .9, hy - hr * .4], [hx - hr * .75, hy - hr * 1.2], [hx - hr * .3, hy - hr * .85]], fur);
        g += T([[hx + hr * .9, hy - hr * .4], [hx + hr * .75, hy - hr * 1.2], [hx + hr * .3, hy - hr * .85]], fur); break;
      case 'chicken': case 'rooster': {
        const cm = '#e4504e', n = sp === 'rooster' ? 3 : 2;
        for (let i = 0; i < n; i++) g += `<circle cx="${f1(hx - hr * .25 + i * hr * .25)}" cy="${f1(hy - hr * 1.0)}" r="${f1(hr * (sp === 'rooster' ? .24 : .18))}" fill="${cm}"/>`; break; }
      case 'human':
        break;
    }
    // head
    g += `<circle cx="${f1(hx)}" cy="${f1(hy)}" r="${f1(hr)}" fill="${fur}" stroke="${ln}" stroke-width="${sw}"/>`;
    if (sp === 'human') {
      g += `<path d="M${f1(hx - hr)},${f1(hy - hr * .05)} q0,-${f1(hr * 1.15)} ${f1(hr)},-${f1(hr)} q${f1(hr)},0 ${f1(hr)},${f1(hr)} q-${f1(hr * .4)},-${f1(hr * .55)} -${f1(hr * 1.2)},-${f1(hr * .45)}z" fill="#2f2622"/>`;
      g += `<rect x="${f1(hx - hr * .55)}" y="${f1(hy - hr * .02)}" width="${f1(hr * .45)}" height="${f1(hr * .3)}" rx="${f1(hr * .1)}" fill="none" stroke="#2f2622" stroke-width="${sw}"/><rect x="${f1(hx + hr * .1)}" y="${f1(hy - hr * .02)}" width="${f1(hr * .45)}" height="${f1(hr * .3)}" rx="${f1(hr * .1)}" fill="none" stroke="#2f2622" stroke-width="${sw}"/>`;
    }
    // face markings
    if (sp === 'fox') g += `<path d="M${f1(hx - hr * .8)},${f1(hy + hr * .1)} q${f1(hr * .8)},${f1(hr * 1.1)} ${f1(hr * 1.6)},0 q-${f1(hr * .8)},${f1(hr * .2)} -${f1(hr * 1.6)},0z" fill="#fff4e6"/>`;
    if (sp === 'panda' || sp === 'raccoon' || sp === 'meerkat') g += E(hx - hr * .38, hy - hr * .02, hr * .24, hr * .2, sp === 'panda' ? '#3b3a4a' : '#5b4a40', -20) + E(hx + hr * .38, hy - hr * .02, hr * .24, hr * .2, sp === 'panda' ? '#3b3a4a' : '#5b4a40', 20);
    if (sp === 'otter' || sp === 'monkey' || sp === 'beaver' || sp === 'cow' || sp === 'goat' || sp === 'buffalo' || sp === 'bear') g += E(hx, hy + hr * .35, hr * .45, hr * .32, sp === 'cow' ? '#f7c9c0' : '#f6e3cc');
    if (sp === 'owl') g += `<circle cx="${f1(hx - hr * .38)}" cy="${f1(hy - hr * .02)}" r="${f1(hr * .32)}" fill="#fff8ec"/><circle cx="${f1(hx + hr * .38)}" cy="${f1(hy - hr * .02)}" r="${f1(hr * .32)}" fill="#fff8ec"/>`;
    if (sp === 'frog') g += `<circle cx="${f1(hx - hr * .45)}" cy="${f1(hy - hr * .8)}" r="${f1(hr * .3)}" fill="${fur}" stroke="${ln}" stroke-width="${sw}"/><circle cx="${f1(hx + hr * .45)}" cy="${f1(hy - hr * .8)}" r="${f1(hr * .3)}" fill="${fur}" stroke="${ln}" stroke-width="${sw}"/>`;
    if (sp === 'cow') g += `<circle cx="${f1(hx + hr * .45)}" cy="${f1(hy - hr * .45)}" r="${f1(hr * .2)}" fill="#4a3b33" opacity=".75"/>`;
    // eyes
    const ey = sp === 'frog' ? hy - hr * .8 : hy - hr * .02, ex = sp === 'frog' ? hr * .45 : hr * .36;
    const eyeCol = (sp === 'panda' || sp === 'raccoon' || sp === 'meerkat') ? 'white' : '#2f2622';
    if (opt.sleep) g += `<path d="M${f1(hx - ex - hr * .1)},${f1(ey)} h${f1(hr * .2)} M${f1(hx + ex - hr * .1)},${f1(ey)} h${f1(hr * .2)}" stroke="#2f2622" stroke-width="${sw * 1.2}" stroke-linecap="round"/>`;
    else g += `<circle cx="${f1(hx - ex)}" cy="${f1(ey)}" r="${f1(hr * .1)}" fill="${eyeCol}"/><circle cx="${f1(hx + ex)}" cy="${f1(ey)}" r="${f1(hr * .1)}" fill="${eyeCol}"/>`;
    // muzzle
    if (['duck', 'chicken', 'rooster', 'owl', 'parrot', 'penguin', 'bird'].includes(sp)) {
      const bc = sp === 'duck' ? '#f4a63a' : '#f2b84b';
      g += sp === 'duck' ? E(hx, hy + hr * .32, hr * .36, hr * .15, bc) : T([[hx - hr * .16, hy + hr * .18], [hx + hr * .16, hy + hr * .18], [hx, hy + hr * .48]], bc);
      if (sp === 'chicken' || sp === 'rooster') g += E(hx + hr * .05, hy + hr * .62, hr * .1, hr * .14, '#e4504e');
    } else if (sp === 'elephant') {
      g += `<path d="M${f1(hx)},${f1(hy + hr * .2)} q-${f1(hr * .05)},${f1(hr * .8)} ${f1(hr * .35)},${f1(hr * .75)}" stroke="${fur}" stroke-width="${f1(hr * .32)}" fill="none" stroke-linecap="round"/>`;
    } else if (sp !== 'human' && sp !== 'frog' && sp !== 'octopus') {
      g += `<ellipse cx="${f1(hx)}" cy="${f1(hy + hr * .26)}" rx="${f1(hr * .1)}" ry="${f1(hr * .07)}" fill="#4a3b33"/>`;
    }
    if (sp === 'beaver') g += `<rect x="${f1(hx - hr * .1)}" y="${f1(hy + hr * .38)}" width="${f1(hr * .2)}" height="${f1(hr * .18)}" fill="white" stroke="${ln}" stroke-width=".5"/>`;
    if (sp === 'penguin') g += E(hx, hy + hr * .05, hr * .62, hr * .55, '#fff8ec') + `<circle cx="${f1(hx - hr * .25)}" cy="${f1(hy - hr * .05)}" r="${f1(hr * .09)}" fill="#2f2622"/><circle cx="${f1(hx + hr * .25)}" cy="${f1(hy - hr * .05)}" r="${f1(hr * .09)}" fill="#2f2622"/>` + T([[hx - hr * .14, hy + hr * .18], [hx + hr * .14, hy + hr * .18], [hx, hy + hr * .4]], '#f2b84b');
    // blush
    g += `<circle cx="${f1(hx - hr * .62)}" cy="${f1(hy + hr * .25)}" r="${f1(hr * .12)}" fill="#f29a9a" opacity=".55"/><circle cx="${f1(hx + hr * .62)}" cy="${f1(hy + hr * .25)}" r="${f1(hr * .12)}" fill="#f29a9a" opacity=".55"/>`;
    // hats
    if (a.hat === 'hardhat') g += `<path d="M${f1(hx - hr * 1.0)},${f1(hy - hr * .35)} q0,-${f1(hr * .95)} ${f1(hr)},-${f1(hr * .95)} q${f1(hr)},0 ${f1(hr)},${f1(hr * .95)}z" fill="#f6c343" stroke="${ln}" stroke-width="${sw}"/>`;
    if (a.hat === 'peci') g += `<rect x="${f1(hx - hr * .75)}" y="${f1(hy - hr * 1.28)}" width="${f1(hr * 1.5)}" height="${f1(hr * .48)}" rx="${f1(hr * .12)}" fill="#2f2b3a"/>`;
    if (a.hat === 'blangkon') g += `<path d="M${f1(hx - hr * 1.0)},${f1(hy - hr * .35)} q0,-${f1(hr * .9)} ${f1(hr)},-${f1(hr * .9)} q${f1(hr)},0 ${f1(hr)},${f1(hr * .9)}z" fill="#7a4b2a"/><path d="M${f1(hx - hr * 1.0)},${f1(hy - hr * .35)} q0,-${f1(hr * .9)} ${f1(hr)},-${f1(hr * .9)} q${f1(hr)},0 ${f1(hr)},${f1(hr * .9)}z" fill="url(#kawung)" opacity=".6"/>`;
    if (a.hat === 'headphones') g += `<path d="M${f1(hx - hr * .95)},${f1(hy)} a${f1(hr * .95)},${f1(hr * .95)} 0 0 1 ${f1(hr * 1.9)},0" fill="none" stroke="#3b3a4a" stroke-width="${f1(hr * .14)}"/><rect x="${f1(hx - hr * 1.12)}" y="${f1(hy - hr * .15)}" width="${f1(hr * .3)}" height="${f1(hr * .5)}" rx="${f1(hr * .1)}" fill="#e8739a"/><rect x="${f1(hx + hr * .82)}" y="${f1(hy - hr * .15)}" width="${f1(hr * .3)}" height="${f1(hr * .5)}" rx="${f1(hr * .1)}" fill="#e8739a"/>`;
    if (a.hat === 'headset') g += `<path d="M${f1(hx - hr * .95)},${f1(hy)} a${f1(hr * .95)},${f1(hr * .95)} 0 0 1 ${f1(hr * 1.9)},0" fill="none" stroke="#3b3a4a" stroke-width="${f1(hr * .12)}"/><path d="M${f1(hx - hr * .95)},${f1(hy + hr * .1)} q0,${f1(hr * .55)} ${f1(hr * .6)},${f1(hr * .6)}" fill="none" stroke="#3b3a4a" stroke-width="${f1(hr * .08)}"/><circle cx="${f1(hx - hr * .3)}" cy="${f1(hy + hr * .7)}" r="${f1(hr * .1)}" fill="#3b3a4a"/>`;
    // right arm + prop
    if (sp !== 'octopus') g += `<ellipse cx="${f1(x + .34 * k)}" cy="${f1(bodyTop + .3 * k)}" rx="${f1(.08 * k)}" ry="${f1(.17 * k)}" fill="${out}" stroke="${ln}" stroke-width="${sw}"/>`;
    if (a.prop) g += `<g>${prop(a.prop, x + .48 * k, bodyTop + .28 * k, k * .95)}</g>`;
    if (opt.sleep) g += `<text x="${f1(hx + hr * .9)}" y="${f1(hy - hr * .9)}" font-size="${f1(k * .32)}" fill="#5B63C9" font-weight="700">z</text>`;
    g += '</g>';
    return g;
  }

  // ---------- scene ----------
  class Scene {
    constructor(s, ox, oy, rot = 0, W = 30, D = 12) { Object.assign(this, { s, ox, oy, rot, W, D, z0: 0, items: [] }); }
    r(x, y) {
      const { W, D } = this;
      switch (this.rot & 3) {
        case 1: return [D - y, x];
        case 2: return [W - x, D - y];
        case 3: return [y, W - x];
        default: return [x, y];
      }
    }
    p(x, y, z = 0) { const [a, b] = this.r(x, y); if (this._first == null) this._first = a + b; return [this.ox + (a - b) * C * this.s, this.oy + (a + b) * .5 * this.s - (z + this.z0) * this.s]; }
    pts(arr) { return arr.map(a => this.p(...a).map(f1).join(',')).join(' '); }
    poly(arr, fill, extra = '') { return `<polygon points="${this.pts(arr)}" fill="${fill}" ${extra}/>`; }
    depth(x, y) { const [a, b] = this.r(x, y); return a + b; }
    rect(x, y, w, d) { // rotate a rect, return normalized rect in rotated space and inverse helper
      const c = [this.r(x, y), this.r(x + w, y), this.r(x + w, y + d), this.r(x, y + d)];
      const xs = c.map(q => q[0]), ys = c.map(q => q[1]);
      return [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
    }
    // box in floor coords; faces computed in rotated space
    box(x, y, z, w, d, h, col, o = {}) {
      const [X, Y, Wd, Dd] = this.rect(x, y, w, d);
      if (this._first == null) this._first = X + Wd / 2 + Y + Dd / 2;
      const q = (a, b, c) => [this.ox + (a - b) * C * this.s, this.oy + (a + b) * .5 * this.s - (c + this.z0) * this.s];
      const P = arr => arr.map(v => q(...v).map(f1).join(',')).join(' ');
      const st = o.stroke || shade(col, .62);
      const sa = `stroke="${st}" stroke-width="${o.sw || .7}" stroke-linejoin="round"`;
      const top = [[X, Y, z + h], [X + Wd, Y, z + h], [X + Wd, Y + Dd, z + h], [X, Y + Dd, z + h]];
      const right = [[X + Wd, Y, z], [X + Wd, Y + Dd, z], [X + Wd, Y + Dd, z + h], [X + Wd, Y, z + h]];
      const left = [[X, Y + Dd, z], [X + Wd, Y + Dd, z], [X + Wd, Y + Dd, z + h], [X, Y + Dd, z + h]];
      let g = `<polygon points="${P(left)}" fill="${o.left || shade(col, .8)}" ${sa}/>`;
      g += `<polygon points="${P(right)}" fill="${o.right || shade(col, .9)}" ${sa}/>`;
      g += `<polygon points="${P(top)}" fill="${o.top || col}" ${sa}/>`;
      if (o.leftPattern) g += `<polygon points="${P(left)}" fill="${o.leftPattern}" opacity="${o.patOp || .5}"/>`;
      if (o.rightPattern) g += `<polygon points="${P(right)}" fill="${o.rightPattern}" opacity="${o.patOp || .5}"/>`;
      if (o.topPattern) g += `<polygon points="${P(top)}" fill="${o.topPattern}" opacity="${o.patOp || .5}"/>`;
      return g;
    }
    // depth comes from the first primitive drawn since the previous add, so ordering survives rotation
    add(d, svg) { const dd = this._first != null ? this._first : d; this._first = null; this.items.push({ d: dd, svg }); }
    addAt(d, svg) { this._first = null; this.items.push({ d, svg }); }
    reset() { this._first = null; }
    // which original sides face the viewer's back for this rotation
    sides() {
      const { W, D } = this;
      return { y0: [[0, 0], [W, 0]], xW: [[W, 0], [W, D]], yD: [[W, D], [0, D]], x0: [[0, D], [0, 0]] };
    }
    isBack(side) {
      const [p1, p2] = this.sides()[side];
      const a = this.r(...p1), b = this.r(...p2);
      return (a[0] === 0 && b[0] === 0) || (a[1] === 0 && b[1] === 0);
    }
    wall(side, svg) { this._first = null; if (this.isBack(side)) this.items.push({ d: -1, svg }); }
    flush() { const s = this.items.sort((a, b) => a.d - b.d).map(i => i.svg).join(''); this.items = []; return s; }
  }

  // ---------- furniture library (floor coords) ----------
  const F = {
    desk(sc, x, y, o = {}) {
      const top = o.wood || '#e8c9a0';
      let g = sc.box(x, y, 0, 1.5, .8, .72, top);
      g += sc.box(x + .45, y + .15, .72, .6, .12, .45, '#4f5664', { top: '#3f4552' });
      g += sc.poly([[x + .5, y + .28, .8], [x + 1.0, y + .28, .8], [x + 1.0, y + .28, 1.12], [x + .5, y + .28, 1.12]], o.screen || '#bfe3f5', 'opacity=".95"');
      if (o.mug) g += sc.box(x + 1.15, y + .5, .72, .14, .14, .14, '#f4efe6');
      return g;
    },
    chair(sc, x, y, col = '#7aa7c7') { return sc.box(x, y, 0, .5, .5, .4, col) + sc.box(x, y + .38, .4, .5, .12, .45, col); },
    plant(sc, x, y, big = 1) {
      let g = sc.box(x, y, 0, .45 * big, .45 * big, .4 * big, '#d98e6a', { top: '#7a5136' });
      const [px, py] = sc.p(x + .22 * big, y + .22 * big, .4 * big);
      const s = sc.s * big;
      g += `<circle cx="${f1(px)}" cy="${f1(py - s * .35)}" r="${f1(s * .38)}" fill="#7dbb7a"/><circle cx="${f1(px - s * .22)}" cy="${f1(py - s * .62)}" r="${f1(s * .26)}" fill="#91cc86"/><circle cx="${f1(px + s * .2)}" cy="${f1(py - s * .7)}" r="${f1(s * .24)}" fill="#6aad6c"/>`;
      return g;
    },
    tree(sc, x, y) {
      let g = sc.box(x, y, 0, .3, .3, 1.4, '#8a6240');
      const [px, py] = sc.p(x + .15, y + .15, 1.4); const s = sc.s;
      g += `<circle cx="${f1(px)}" cy="${f1(py - s * .3)}" r="${f1(s * .9)}" fill="#86c47f"/><circle cx="${f1(px - s * .5)}" cy="${f1(py - s * .6)}" r="${f1(s * .55)}" fill="#9bd18f"/><circle cx="${f1(px + s * .45)}" cy="${f1(py - s * .75)}" r="${f1(s * .55)}" fill="#74b56f"/>`;
      for (let i = 0; i < 5; i++) g += `<circle cx="${f1(px - s * .6 + i * s * .3)}" cy="${f1(py - s * (.2 + (i % 2) * .5))}" r="${f1(s * .1)}" fill="#fff4e0"/><circle cx="${f1(px - s * .6 + i * s * .3)}" cy="${f1(py - s * (.2 + (i % 2) * .5))}" r="${f1(s * .04)}" fill="#f2c14e"/>`;
      return g;
    },
    shelf(sc, x, y, w, o = {}) {
      let g = sc.box(x, y, 0, w, .45, 2.0, o.wood || '#c7956a');
      const cols = ['#e8739a', '#7aa7e0', '#f2c14e', '#7cc4a4', '#b49be0', '#f08a5d'];
      for (let r = 0; r < 3; r++) for (let i = 0; i < Math.floor(w / .22); i++) {
        const xx = x + .08 + i * .22, zz = .2 + r * .62;
        g += sc.poly([[xx, y + .45, zz], [xx + .16, y + .45, zz], [xx + .16, y + .45, zz + .42 + (i % 3) * .05], [xx, y + .45, zz + .42 + (i % 3) * .05]], cols[(i + r * 2) % 6]);
      }
      return g;
    },
    pallet(sc, x, y, stacks = 3) {
      let g = sc.box(x, y, 0, 1.3, 1.3, .16, '#c99a62');
      for (let l = 0; l < stacks; l++) for (let i = 0; i < 2; i++)
        g += sc.box(x + .06 + i * .6, y + .08, .16 + l * .3, .56, 1.14, .3, '#efe2c4', { top: '#f6ecd4' });
      const [lx, ly] = sc.p(x + .66, y + 1.25, .16 + stacks * .3 - .18);
      g += `<text x="${f1(lx)}" y="${f1(ly)}" font-size="${f1(sc.s * .18)}" fill="#8a6a3a" text-anchor="middle" font-weight="700">PAKAN</text>`;
      return g;
    },
    rug(sc, x, y, w, d, col, pat) {
      let g = sc.poly([[x, y, .03], [x + w, y, .03], [x + w, y + d, .03], [x, y + d, .03]], col, `stroke="${shade(col, .8)}" stroke-width="1"`);
      if (pat) g += sc.poly([[x, y, .03], [x + w, y, .03], [x + w, y + d, .03], [x, y + d, .03]], pat, 'opacity=".45"');
      return g;
    },
    beanbag(sc, x, y, col) {
      const [px, py] = sc.p(x, y, 0); const s = sc.s;
      return `<ellipse cx="${f1(px)}" cy="${f1(py - s * .2)}" rx="${f1(s * .55)}" ry="${f1(s * .35)}" fill="${col}" stroke="${shade(col, .7)}" stroke-width=".8"/><ellipse cx="${f1(px - s * .1)}" cy="${f1(py - s * .38)}" rx="${f1(s * .3)}" ry="${f1(s * .16)}" fill="${shade(col, 1.15)}"/>`;
    },
    arcade(sc, x, y) {
      let g = sc.box(x, y, 0, .8, .7, 1.8, '#8d6cc7', { top: '#a68ad6' });
      g += sc.poly([[x + .1, y + .7, 1.0], [x + .7, y + .7, 1.0], [x + .7, y + .7, 1.55], [x + .1, y + .7, 1.55]], '#1f2a44');
      g += sc.poly([[x + .18, y + .7, 1.1], [x + .62, y + .7, 1.1], [x + .62, y + .7, 1.45], [x + .18, y + .7, 1.45]], '#5ee0c2', 'opacity=".75"');
      g += sc.box(x + .05, y + .7, .85, .7, .25, .08, '#3b3a4a');
      return g;
    },
    gamelan(sc, x, y) {
      let g = sc.box(x, y, 0, 1.6, .5, .35, '#a0673f', { leftPattern: 'url(#kawung)', patOp: .35 });
      for (let i = 0; i < 6; i++) g += sc.box(x + .1 + i * .25, y + .12, .35, .16, .26, .05, '#e2b54e');
      // gong frame
      g += sc.box(x + 2.0, y, 0, .12, .12, 1.5, '#7a4b2a') + sc.box(x + 2.0, y + 1.0, 0, .12, .12, 1.5, '#7a4b2a') + sc.box(x + 2.0, y, 1.5, .12, 1.12, .12, '#7a4b2a');
      const [gx, gy] = sc.p(x + 2.06, y + .56, .85);
      g += `<ellipse cx="${f1(gx)}" cy="${f1(gy)}" rx="${f1(sc.s * .42)}" ry="${f1(sc.s * .5)}" fill="#d9a441" stroke="#8a6020" stroke-width="1"/><ellipse cx="${f1(gx)}" cy="${f1(gy)}" rx="${f1(sc.s * .12)}" ry="${f1(sc.s * .14)}" fill="#c58e2e"/>`;
      return g;
    },
    counter(sc, x, y, w, d, col, o = {}) { return sc.box(x, y, 0, w, d, 1.0, col, { top: o.top || '#f4e6cf', leftPattern: o.batik ? 'url(#kawung)' : null, rightPattern: o.batik ? 'url(#kawung)' : null, patOp: .4 }); },
    table(sc, x, y, w, d, col = '#e8c9a0') { return sc.box(x, y, 0, w, d, .7, col); },
    rack(sc, x, y) {
      let g = sc.box(x, y, 0, .8, .8, 2.0, '#3e4656', { top: '#4c5568' });
      for (let i = 0; i < 6; i++) { const [lx, ly] = sc.p(x + .2 + (i % 2) * .3, y + .8, .4 + Math.floor(i / 2) * .5); g += `<circle cx="${f1(lx)}" cy="${f1(ly)}" r="${f1(sc.s * .05)}" fill="${['#5ee08a', '#5ee08a', '#f2c14e', '#5ee08a', '#5ee0c2', '#5ee08a'][i]}"/>`; }
      return g;
    },
    cone(sc, x, y) {
      const [px, py] = sc.p(x, y, 0); const s = sc.s;
      return `<path d="M${f1(px - s * .18)},${f1(py)} L${f1(px)},${f1(py - s * .6)} L${f1(px + s * .18)},${f1(py)}Z" fill="#f08a3a" stroke="#a5521c" stroke-width=".7"/><path d="M${f1(px - s * .1)},${f1(py - s * .3)} h${f1(s * .2)}" stroke="white" stroke-width="${f1(s * .07)}"/>`;
    },
    scaffold(sc, x, y, w, d, h) {
      let g = '';
      const posts = [[x, y], [x + w, y], [x, y + d], [x + w, y + d], [x + w / 2, y + d], [x + w, y + d / 2]];
      for (const [px, py] of posts) { const a = sc.p(px, py, 0), b = sc.p(px, py, h); g += `<line x1="${f1(a[0])}" y1="${f1(a[1])}" x2="${f1(b[0])}" y2="${f1(b[1])}" stroke="#9aa3ad" stroke-width="${f1(sc.s * .06)}"/>`; }
      for (const zz of [h * .5, h]) {
        const r = [[x, y + d, zz], [x + w, y + d, zz], [x + w, y, zz]];
        g += `<polyline points="${sc.pts(r)}" fill="none" stroke="#9aa3ad" stroke-width="${f1(sc.s * .06)}"/>`;
        g += sc.box(x + w * .05, y + d - .5, zz - .06, w * .9, .45, .06, '#d8b07a');
      }
      return g;
    },
    tape(sc, x, y, w, d) {
      const pts = [[x, y + d, .5], [x + w, y + d, .5], [x + w, y, .5]];
      return `<polyline points="${sc.pts(pts)}" fill="none" stroke="#f6c343" stroke-width="${f1(sc.s * .1)}" stroke-dasharray="${f1(sc.s * .25)} ${f1(sc.s * .25)}"/><polyline points="${sc.pts(pts)}" fill="none" stroke="#3b3a4a" stroke-width="${f1(sc.s * .1)}" stroke-dasharray="${f1(sc.s * .25)} ${f1(sc.s * .25)}" stroke-dashoffset="${f1(sc.s * .25)}" opacity=".85"/>`;
    },
    lamp(sc, x, y, z = 2.3) {
      const [px, py] = sc.p(x, y, z);
      return `<circle cx="${f1(px)}" cy="${f1(py + sc.s * 1.4)}" r="${f1(sc.s * 2.2)}" fill="url(#warm)"/><path d="M${f1(px)},${f1(py - sc.s * .8)} v${f1(sc.s * .5)}" stroke="#8a7a6a" stroke-width=".8"/><path d="M${f1(px - sc.s * .3)},${f1(py)} q${f1(sc.s * .3)},-${f1(sc.s * .4)} ${f1(sc.s * .6)},0z" fill="#f6d7a0" stroke="#b08a5a" stroke-width=".7"/>`;
    },
    sign(sc, x, y, z, text, col = '#fff8ec', fg = '#5a4636', size = .3) {
      const [px, py] = sc.p(x, y, z); const fs = Math.max(8, sc.s * size);
      const w = text.length * fs * .56 + fs;
      return `<rect x="${f1(px - w / 2)}" y="${f1(py - fs * .95)}" width="${f1(w)}" height="${f1(fs * 1.45)}" rx="${f1(fs * .35)}" fill="${col}" stroke="${shade(col === '#fff8ec' ? '#d9c6ad' : col, .75)}" stroke-width=".8"/><text x="${f1(px)}" y="${f1(py + fs * .22)}" font-size="${f1(fs)}" text-anchor="middle" fill="${fg}" font-weight="650">${text}</text>`;
    },
  };

  // wall-mounted board on the back wall (plane y = 0) from x0..x1, z0..z1
  function wallBoardY0(sc, x0, x1, z0, z1, col) { return sc.poly([[x0, .05, z0], [x1, .05, z0], [x1, .05, z1], [x0, .05, z1]], col, `stroke="${shade(col, .7)}" stroke-width="1"`); }
  function wallBoardX0(sc, y0, y1, z0, z1, col) { return sc.poly([[.05, y0, z0], [.05, y1, z0], [.05, y1, z1], [.05, y0, z1]], col, `stroke="${shade(col, .7)}" stroke-width="1"`); }

  G.Iso = { Scene, F, mascot, badge, STATES, shade, wallBoardY0, wallBoardX0, f1, prop, starPath };
})(typeof window !== 'undefined' ? window : globalThis);
