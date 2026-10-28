// SPDX-License-Identifier: Apache-2.0
// Gatherlane app: views, controls, inbox, cards. Status shown only from data; decoration is CSS only.
(function () {
  const CFG = GATHERLANE_CONFIG, LEVELS = Building.LEVELS, esc = Office.esc, ghUrl = CFG.gh;
  const $ = id => document.getElementById(id);
  const mobileQ = matchMedia('(max-width: 820px)');

  // ---------- storage (best effort) ----------
  const ls = {
    get(k, sess) { try { const s = (sess ? sessionStorage : localStorage).getItem(k); return s ? JSON.parse(s) : null; } catch (e) { return null; } },
    set(k, v, sess) { try { (sess ? sessionStorage : localStorage).setItem(k, JSON.stringify(v)); } catch (e) {} },
    del(k, sess) { try { (sess ? sessionStorage : localStorage).removeItem(k); } catch (e) {} },
  };
  const prefs = Object.assign({ useSample: false, remember: false, rot: 0, focus: false, legend: false }, ls.get('gl.prefs') || {});
  const loadTokens = k => ls.get(k) || ls.get(k, true) || {};
  let tokens = loadTokens('gl.tokens'), dtokens = loadTokens('gl.dtokens');

  // ---------- state ----------
  const S = {
    view: 'building', level: null, rot: prefs.rot, focus: prefs.focus, selected: null, room: null,
    cam: { x: 0, y: 0, k: 1 }, svgW: 0, svgH: 0, you: {}, filter: 'all', night: false, tab: 'floor', scene: null,
  };
  const D = { mode: 'sample', rows: [], control: { paused: {} }, prs: [], runs: [], statusErr: null, invalid: [], prErr: {}, runErr: {}, updated: null, rate: null };
  const allRepos = [...new Set(Object.values(CFG.operations).flatMap(o => o.repos))];
  // A repo is labelled by its name, or by owner/name when another watched repo has the same name.
  const repoLabel = r => { const n = r.split('/')[1]; return allRepos.some(x => x !== r && x.split('/')[1] === n) ? r : n; };
  const opForRepo = r => Object.keys(CFG.operations).find(k => CFG.operations[k].repos.includes(r));
  const levelOfOp = op => (CFG.operations[op] || {}).level;
  const opOfLevel = lv => Object.keys(CFG.operations).find(k => CFG.operations[k].level === lv);
  // Same rule as tools/gatherlane.py: an agentPrefixes match, else the id's first part, else the fallback.
  const opOfId = id => Layout.opOfId(CFG, id);
  const pathOf = id => { const parts = id.split('/'), op = opOfId(id); return `status/${op}/${parts.length === 2 && parts[0] === op ? parts[1] : id.replace('/', '-')}.json`; };
  const ownerOf = r => (r || '').split('/')[0];
  const OWNERS = [...new Set([ownerOf(CFG.statusRepo), ...allRepos.map(ownerOf), ...(CFG.extraTokenOwners || [])].filter(Boolean))];
  S.level = CFG.defaultLevel || (LEVELS.find(L => L.key) || LEVELS[0]).id;
  const agentDef = id => { for (const L of LEVELS) { const a = L.agents.find(a => a.id === id); if (a) return { ...a, level: L.id }; } return null; };

  // ---------- time ----------
  const TZ = CFG.timeZone;
  const TZL = CFG.timeZoneLabel || (new Intl.DateTimeFormat('en-GB', { timeZone: TZ, timeZoneName: 'short' }).formatToParts(new Date()).find(p => p.type === 'timeZoneName') || {}).value || TZ;
  const fmt = (iso, withDay) => {
    if (!iso) return '—';
    const d = new Date(iso);
    const t = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(d);
    const day = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, day: 'numeric', month: 'short' }).format(d);
    const today = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, day: 'numeric', month: 'short' }).format(new Date());
    return (day === today && !withDay ? '' : day + ' ') + t + ' ' + TZL;
  };
  const ago = iso => { const m = Math.round(((D.mode === 'sample' ? Date.parse(SAMPLE.now) : Date.now()) - Date.parse(iso)) / 60000); return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`; };
  const DAYPARTS = CFG.dayParts || ['night', 'morning', 'midday', 'afternoon'];
  function localHour() { return +new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', hourCycle: 'h23' }).format(new Date()); }
  function tickClock() {
    const now = new Date(), h = localHour();
    const part = DAYPARTS[h < 4 ? 0 : h < 11 ? 1 : h < 15 ? 2 : h < 18 ? 3 : 0];
    $('clock').innerHTML = `<b>${new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(now)} ${esc(TZL)}</b><br>${new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' }).format(now)} · ${part}`;
    const sky = h >= 5 && h < 7 ? ['#f6c9a8', '#f7e3d0'] : h >= 7 && h < 16 ? ['#cfe6f5', '#f7e3d0'] : h >= 16 && h < 18 ? ['#f3b48f', '#f6d6c2'] : ['#26304f', '#4a4a6e'];
    document.documentElement.style.setProperty('--sky1', sky[0]); document.documentElement.style.setProperty('--sky2', sky[1]);
    const night = h >= 18 || h < 5;
    if (night !== S.night) { S.night = night; document.body.classList.toggle('night', night); renderStage(false); }
  }

  // ---------- data ----------
  const PREVIEW = !!window.GL_PREVIEW;
  function useSampleNow() { return PREVIEW || prefs.useSample || !Object.values(tokens).some(Boolean); }
  function loadSample() {
    Object.assign(D, { mode: 'sample', rows: SAMPLE.rows, control: SAMPLE.control, prs: SAMPLE.prs.map(p => ({ ...p, labels: [p.label] })), runs: [], statusErr: null, invalid: [], prErr: {}, runErr: {}, updated: null });
  }
  // A Save during a read replaces gh (also when it turns on sample data, the only way to), so that
  // read is dropped when it returns, and a forced refresh asked for meanwhile runs once it has ended.
  let gh = null, lastRuns = 0, refreshing = false, again = false;
  async function refresh(force) {
    if (useSampleNow()) { loadSample(); renderAll(); return; }
    if (refreshing) { if (force) again = true; return; }
    refreshing = true;
    const g = gh = gh || new GLData.GitHub(tokens);
    D.mode = 'live';
    try {
      let st;
      try { st = await GLData.loadStatus(g, CFG); st.statusErr = null; } catch (e) {
        st = { rows: [], control: { paused: {} }, invalid: D.invalid, statusErr: e.status === 404 ? `status branch “${CFG.statusBranch}” not found in ${CFG.statusRepo}, or the ${ownerOf(CFG.statusRepo)} token can't read it` : (e.status ? `${e.status} reading ${CFG.statusRepo}` : String(e.message)) };
      }
      const pr = await GLData.loadPRs(g, allRepos);
      const runs = force || Date.now() - lastRuns > CFG.runsRefreshSeconds * 1000 ? await GLData.loadFailedRuns(g, allRepos) : null;
      if (gh !== g) return;
      Object.assign(D, { rows: st.rows, control: st.control, invalid: st.invalid, statusErr: st.statusErr, prs: pr.prs, prErr: pr.errors });
      if (runs) { D.runs = runs.runs; D.runErr = runs.errors; lastRuns = Date.now(); }
      D.updated = new Date().toISOString(); D.rate = g.rate;
      renderAll();
    } finally {
      refreshing = false;
      if (again) { again = false; refresh(true); }
    }
  }

  function statusIndex() { return Office.statusMap(D.rows, D.control, D.mode === 'sample' ? Date.parse(SAMPLE.now) : Date.now()); }

  function inbox() {
    const items = [];
    for (const p of D.prs) for (const l of p.labels || []) {
      const kind = CFG.inboxLabels[l]; if (!kind) continue;
      items.push({ kind, tone: kind === 'ready to merge' ? 'ok' : 'warn', group: 'pr', title: `${repoLabel(p.repo)} #${p.number} · ${p.title}`, url: p.url, link: 'Open PR', source: p.source, op: opForRepo(p.repo), agent: null });
    }
    for (const r of D.rows) {
      if (!(r.needs_human || r.status === 'failed')) continue;
      const kind = r.status === 'failed' ? 'failed run' : ({ escalation: 'escalation', approval: 'approval', review: 'review', failed_run: 'failed run' }[r.needs_human_kind] || 'needs you');
      const L = r.links || {}, cfgA = CFG.agents[r.agent] || {};
      const url = L.issue || L.pr || r.last_result_url || L.runbook || cfgA.runbook || null;
      const link = L.issue ? 'Open issue' : L.pr ? 'Open PR' : r.last_result_url ? 'Open run' : url ? 'Open runbook' : null;
      items.push({ kind, tone: kind === 'failed run' ? 'bad' : kind === 'escalation' ? 'warn' : 'info', group: kind === 'failed run' ? 'failed' : kind === 'escalation' ? 'esc' : 'other', title: `${(agentDef(r.agent) || { name: r.agent }).name} — ${r.needs_human_reason || 'run failed'}`, url, link, source: r.source, op: r.operation, agent: r.agent });
    }
    for (const run of D.runs) items.push({ kind: 'failed run', tone: 'bad', group: 'failed', title: `${repoLabel(run.repo)} · workflow “${run.name}” failed on ${run.branch}`, url: run.url, link: 'Open run', source: run.source, op: opForRepo(run.repo), agent: null });
    const rank = { 'escalation': 0, 'failed run': 1, 'ready to merge': 2, 'needs maintainer': 3, 'approval': 4, 'review': 5, 'needs you': 6 };
    return items.sort((a, b) => rank[a.kind] - rank[b.kind]);
  }

  // ---------- rendering ----------
  function renderAll() { renderTop(); renderSide(); renderStage(false); renderCards(); renderCrumbs(); renderCtrl(); renderLegend(); }

  function renderTop() {
    const items = inbox();
    $('inboxN').textContent = items.length; $('inboxNm').textContent = items.length;
    const lvWait = new Set(items.map(i => levelOfOp(i.op)).filter(Boolean));
    const keyOf = L => L.key ? String(L.key) : L.short;
    $('chips').innerHTML = (mobileQ.matches ? '' : `<button class="chip ${S.view === 'building' ? 'on' : ''}" data-go="building"><b>All</b></button>`) +
      LEVELS.map(L => `<button class="chip ${S.view === 'floor' && S.level === L.id ? 'on' : ''}" data-go="${L.id}" title="${esc(L.name)}"><b>${keyOf(L)}</b>${mobileQ.matches ? `<span class="nm">${esc(L.name.split(' ')[0])}</span>` : ''}${lvWait.has(L.id) ? '<span class="dot"></span>' : ''}</button>`).join('');
    const p = $('srcPill');
    if (D.mode === 'sample') { p.className = 'pill src sample'; p.textContent = PREVIEW ? 'SAMPLE DATA · preview build' : Object.values(tokens).some(Boolean) ? 'SAMPLE DATA · live data turned off' : 'SAMPLE DATA · add tokens to go live'; }
    else if (D.statusErr) { p.className = 'pill src err'; p.textContent = 'LIVE PRs · status files unreachable'; }
    else { p.className = 'pill src live'; p.textContent = D.updated ? `LIVE · GitHub · ${fmt(D.updated)}` : 'LIVE · loading…'; }
    $('focusBtn').setAttribute('aria-pressed', S.focus);
  }

  function renderSide() {
    const all = inbox();
    const f = S.filter, items = all.filter(i => f === 'all' || (f === 'pr' && i.group === 'pr') || (f === 'esc' && i.group === 'esc') || (f === 'failed' && i.group === 'failed') || (f === 'other' && i.group === 'other'));
    const n = g => all.filter(i => i.group === g).length;
    const opName = op => (CFG.operations[op] || {}).name || op || '';
    let h = `<h2>Waiting for you <span class="cnt">${all.length}</span></h2>
      <div class="sub">${D.mode === 'sample' ? '<span class="tag sample">SAMPLE</span> These items are examples, not your real queue.' : 'Live from GitHub and your status files.'} Escalations first, then failures, merges, approvals.</div>
      <div class="ftabs">${[['all', 'All', all.length], ['pr', 'PRs', n('pr')], ['esc', 'Escalations', n('esc')], ['failed', 'Failed', n('failed')], ['other', 'Other', n('other')]].map(([k, t, c]) => `<button data-filter="${k}" class="${S.filter === k ? 'on' : ''}">${t} ${c}</button>`).join('')}</div>`;
    if (!items.length) h += `<div class="empty">${D.mode === 'live' && D.statusErr ? 'PR labels are live; agent escalations will appear once status files are readable.' : 'Nothing needs you right now.'}</div>`;
    for (const i of items) h += `<div class="item"><div class="k ${i.tone}"><i></i>${esc(i.kind)}<span class="tag ${i.source === 'live' ? 'live' : 'sample'}">${i.source === 'live' ? 'LIVE' : 'SAMPLE'}</span></div>
      <button class="t" ${i.agent ? `data-agent-jump="${esc(i.agent)}"` : i.op ? `data-level-jump="${esc(levelOfOp(i.op) || '')}"` : ''}>${esc(i.title)}</button>
      <div class="m"><span>${esc(opName(i.op))}</span>${i.url ? `<a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.link)} ↗</a>` : '<span>no link in status file</span>'}</div></div>`;
    h += `<div class="sub" style="margin-top:12px">PRs appear when labelled <b>review:approved</b> or <b>review:needs-maintainer</b>. Other items come from status files with <b>needs_human: true</b> or <b>status: failed</b>, and from failed GitHub Actions runs in the last 7 days.</div>`;
    $('side').innerHTML = h;
  }

  function youAgent() {
    if (S.level === 'supervisor') return [];
    const L = LEVELS.find(l => l.id === S.level);
    const p = S.you[S.level] || (S.you[S.level] = { x: L.W * .5, y: L.D - 1.3 });
    return [{ id: 'you', name: 'you', walker: true, x: p.x, y: p.y, look: { species: 'human', fur: '#d7a77e', outfit: '#3d6f8f', batik: true } }];
  }

  function renderStage(fit) {
    const st = statusIndex();
    if (mobileQ.matches && S.view === 'building') S.view = 'floor';
    let out;
    if (S.view === 'building') out = Office.buildingSVG(st, { rot: S.rot, focus: S.focus, night: S.night });
    else out = Office.floorSVG(S.level, st, { rot: S.rot, focus: S.focus, selected: S.selected, extraAgents: youAgent(), night: S.night, s: 34 });
    S.scene = out.scene || null;
    $('viewport').innerHTML = out.svg;
    const changed = S.svgW !== out.w || S.svgH !== out.h;
    S.svgW = out.w; S.svgH = out.h;
    if (fit || (changed && fit !== false)) fitView();
    applyCam();
    updateHint();
  }

  function fitView() {
    const r = $('stage').getBoundingClientRect();
    if (S.view === 'building') {
      const k = Math.min(1, (r.width - 20) / S.svgW);
      S.cam = { k, x: (r.width - S.svgW * k) / 2, y: 10 };
    } else {
      const padL = mobileQ.matches ? 0 : (S.selected || S.room ? 420 : 0);
      let k = Math.min(1.4, (r.width - padL - 20) / S.svgW, (r.height - 20) / S.svgH);
      if (mobileQ.matches) k = Math.min((r.height - 120) / S.svgH, (r.width / S.svgW) * 2.3);
      S.cam = { k, x: padL + (r.width - padL - S.svgW * k) / 2, y: (r.height - S.svgH * k) / 2 };
    }
  }
  function applyCam() { $('viewport').style.transform = `translate(${S.cam.x}px,${S.cam.y}px) scale(${S.cam.k})`; }
  function zoomAt(f, cx, cy) {
    const r = $('stage').getBoundingClientRect();
    if (cx == null) { cx = r.width / 2; cy = r.height / 2; }
    const k = Math.max(.2, Math.min(4, S.cam.k * f)); const ratio = k / S.cam.k;
    S.cam.x = cx - (cx - S.cam.x) * ratio; S.cam.y = cy - (cy - S.cam.y) * ratio; S.cam.k = k; applyCam();
  }

  function renderCrumbs() {
    const L = LEVELS.find(l => l.id === S.level);
    $('crumbs').innerHTML = S.view === 'building'
      ? `<b>Whole building</b> · click a floor to step inside · ${D.mode === 'sample' ? '<span class="tag sample">SAMPLE</span>' : '<span class="tag live">LIVE</span>'}`
      : `${mobileQ.matches ? '' : '<button data-go="building">Building</button> › '}<b>${L.key ? L.key + ' · ' : ''}${esc(L.name)}</b>${L.site ? ' · ' + L.site : ''}${L.note ? ` · <span style="color:#8a5b12">${esc(L.note)}</span>` : ''}`;
  }

  function renderCtrl() {
    const floor = S.view === 'floor';
    $('ctrl').innerHTML = (floor ? `<div class="ctrlrow"><span class="cb ghost"></span><button class="cb" data-move="up" aria-label="Walk up">▲</button><span class="cb ghost"></span></div>
      <div class="ctrlrow"><button class="cb" data-move="left" aria-label="Walk left">◀</button><button class="cb" data-move="down" aria-label="Walk down">▼</button><button class="cb" data-move="right" aria-label="Walk right">▶</button></div>` : '') +
      `<div class="ctrlrow"><button class="cb" data-act="rotl" title="Rotate (Shift+R)">⟲</button><button class="cb" data-act="rotr" title="Rotate (R)">⟳</button><button class="cb" data-act="zout" title="Zoom out (−)">−</button><button class="cb" data-act="zin" title="Zoom in (+)">+</button><button class="cb" data-act="fit" title="Fit (0)">⤢</button><button class="cb" data-act="legend" title="Legend">?</button></div>
      <div class="help">${floor ? 'WASD / arrows walk · Enter talks · Esc back' : 'scroll or right-drag to pan · Ctrl+scroll zoom · 1–' + Math.max(1, ...LEVELS.map(L => L.key || 0)) + ' floors'} · I inbox · F focus</div>`;
  }

  function renderLegend() {
    const el = $('legend'); el.hidden = !prefs.legend || mobileQ.matches;
    if (el.hidden) return;
    const order = ['waiting', 'running', 'blocked', 'failed', 'idle', 'sleeping', 'not_deployed', 'unknown'];
    const label = k => k === 'unknown' ? 'no data' : Iso.STATES[k].label;
    el.innerHTML = `<h4>Status badges</h4><div class="lg">${order.map(k => `<div><svg width="22" height="22" viewBox="-11 -11 22 22">${Iso.badge(0, 0, { status: k }, 'dot')}</svg>${label(k)}</div>`).join('')}</div>
      <div class="note">Badges come only from status data. Walking, bobbing and lamps are decoration. A ❚❚ mark means the pause flag is set; <b style="color:#a0522d">stale</b> means the status file is older than its schedule allows.</div>`;
  }

  // ---------- cards ----------
  const STC = k => (Iso.STATES[k] || Iso.STATES.unknown).c;
  function srcTag(r) { return D.mode === 'sample' ? '<span class="tag sample">SAMPLE</span>' : r && r.source === 'live' ? '<span class="tag live">LIVE</span>' : '<span class="tag nodata">NO STATUS FILE</span>'; }
  function lever(href, title, sub, cls = '') { return href ? `<a class="lv ${cls}" href="${esc(href)}" target="_blank" rel="noopener">${title} ↗<small>${sub}</small></a>` : `<span class="lv off">${title}<small>${sub}</small></span>`; }

  function agentCard(id) {
    const A = agentDef(id), cfgA = CFG.agents[id] || {}, st = statusIndex()[id];
    const r = st || { status: 'unknown' }, L = r.links || {};
    const label = r.status === 'unknown' ? 'no data' : Iso.STATES[r.status].label;
    const hollow = r.status === 'not_deployed' || r.status === 'unknown';
    const runbook = L.runbook || cfgA.runbook;
    const statusFile = D.mode === 'live' && r._path ? `${ghUrl(CFG.statusRepo)}/blob/${CFG.statusBranch}/${r._path}` : null;
    const editPause = `${ghUrl(CFG.statusRepo)}/edit/${CFG.statusBranch}/control/pause.json`;
    const owner = L.workflow && (/github\.com\/([^/]+)\//.exec(L.workflow) || [])[1];
    const canDispatch = L.workflow && owner && dtokens[owner] && D.mode === 'live';
    let h = `<div class="card" data-card="agent"><button class="x" data-close="agent" aria-label="Close">×</button>
      <h3>${esc(A ? A.name : id)} <span class="badge" style="background:${hollow ? '#fff' : STC(r.status)};color:${hollow ? '#7a7268' : '#fff'};border:1.5px ${hollow ? 'dashed' : 'solid'} ${STC(r.status)}">${esc(label)}</span>${srcTag(st)}${r.paused ? '<span class="tag warn">❚❚ PAUSED</span>' : ''}${r.stale ? '<span class="tag warn">STALE</span>' : ''}</h3>
      <div class="role">${esc(cfgA.role || '')}${cfgA.note ? `<br>${esc(cfgA.note)}` : ''}</div><div class="kv">`;
    h += `<span>Runbook</span><span>${runbook ? `<a href="${esc(runbook)}" target="_blank" rel="noopener">${esc(runbook.replace(/^https:\/\/github\.com\/[^/]+\//, '').replace('/blob/main/', '/'))} ↗</a>` : 'none found'}</span>`;
    if (r.needs_human || r.needs_human_reason) h += `<span>Needs you</span><span><b>${esc(r.needs_human_reason || 'yes')}</b></span>`;
    if (st) {
      h += `<span>Current task</span><span>${r.current_task ? (r.current_task.url ? `<a href="${esc(r.current_task.url)}" target="_blank" rel="noopener">${esc(r.current_task.title)} ↗</a>` : esc(r.current_task.title)) : '—'}</span>`;
      h += `<span>Last run</span><span>${fmt(r.last_run_at)}${r.last_result ? ` · <b style="color:${r.last_result === 'success' ? 'var(--ok)' : 'var(--bad)'}">${esc(r.last_result)}</b>` : ''}${r.last_result_url ? ` · <a href="${esc(r.last_result_url)}" target="_blank" rel="noopener">log ↗</a>` : ''}</span>`;
      h += `<span>Next run</span><span>${fmt(r.next_run_at)}${r.schedule ? ` · <code>${esc(r.schedule.cron)}</code>` : ''}</span>`;
      h += `<span>Status file</span><span>${r.updated_at ? `${fmt(r.updated_at)} (${ago(r.updated_at)})` : '—'}${r.reported_by ? ` · ${esc(r.reported_by)}` : ''}${statusFile ? ` · <a href="${esc(statusFile)}" target="_blank" rel="noopener">view ↗</a>` : ''}</span>`;
    } else {
      h += `<span>Status</span><span>${D.mode === 'sample' ? 'Not in the sample set.' : `No status file at <code>${esc(pathOf(id))}</code> yet.`} Nothing is shown until the agent reports.</span>`;
    }
    h += `</div><div class="levers">`;
    h += L.issue ? lever(L.issue, 'Open issue', 'from status file') : L.pr ? lever(L.pr, 'Open PR', 'from status file') : lever(cfgA.repo ? `${ghUrl(cfgA.repo)}/issues` : null, 'Open issues', cfgA.repo ? repoLabel(cfgA.repo) : 'no issue linked');
    h += lever(runbook, 'Open runbook', runbook ? 'on GitHub' : 'no runbook found');
    h += lever(L.workflow, 'Run workflow', L.workflow ? 'opens GitHub dispatch page' : 'no workflow in status file');
    h += `<button class="lv dark" data-pause="${esc(id)}" data-href="${esc(editPause)}">${r.paused ? '▶ Resume agent' : '❚❚ Pause agent'}<small>${r.paused ? 'remove its entry in' : 'copies entry, opens'} control/pause.json</small></button>`;
    if (canDispatch) h += `<button class="lv" data-dispatch="${esc(L.workflow)}" style="grid-column:1/-1">⚡ Run now via API<small>uses your dispatch token for ${esc(owner)} · asks first</small></button>`;
    h += `</div></div>`;
    return h;
  }

  const roomCache = new Map();
  function roomCard(key) {
    const [lv, rid] = key.split(':'), L = LEVELS.find(l => l.id === lv), room = L.rooms.find(r => r.id === rid);
    const opk = opOfLevel(lv), op = CFG.operations[opk] || { repos: [] };
    const repos = (op.roomRepos && op.roomRepos[rid]) || op.repos;
    let h = `<div class="card" data-card="room"><button class="x" data-close="room" aria-label="Close">×</button><h3 style="font-size:15px">${esc(room.name)} · ${esc(op.name || L.name)} ${D.mode === 'sample' ? '<span class="tag sample">SAMPLE</span>' : repos.length ? '<span class="tag live">LIVE</span>' : ''}</h3>`;
    if (!repos.length) return h + `<div class="role">No GitHub repos are configured for this operation${op.note ? ` (${esc(op.note)})` : ''}. Add them in <code>instance/config.js</code>.</div></div>`;
    if (D.mode === 'sample') {
      return h + `<div class="role">${repos.map(r => repoLabel(r)).join(' · ')}</div><div class="section">Issues by milestone</div><div class="row-i"><span>Sample milestone A</span><span>4 open</span></div><div class="row-i"><span>Sample milestone B</span><span>7 open</span></div><div class="section">Open PRs</div><div class="row-i"><span>#57 sample PR</span><span class="lbl ok">review:approved</span></div><div class="row-i"><span>#60 sample PR</span><span class="lbl n">no review label</span></div><div class="section">Changelog</div><div class="row-i"><span>sample merged PR</span><span>25 Oct</span></div></div>`;
    }
    const ck = repos.join(','), c = roomCache.get(ck);
    if (!c || Date.now() - c.at > 120000) {
      // Save replaces gh and clears the cache, so a room read started with the old tokens is dropped
      if (!c || !c.loading) { const g = gh = gh || new GLData.GitHub(tokens); roomCache.set(ck, { loading: true, at: Date.now(), data: c && c.data }); GLData.loadRoom(g, repos).then(d => { if (g !== gh) return; roomCache.set(ck, { at: Date.now(), data: d }); renderCards(); }).catch(() => {}); }
      if (!c || !c.data) return h + `<div class="role">${repos.map(r => repoLabel(r)).join(' · ')}</div><div class="empty">Loading from GitHub…</div></div>`;
    }
    const d = (roomCache.get(ck) || c).data;
    h += `<div class="role">${repos.map(r => `<a href="${ghUrl(r)}" target="_blank" rel="noopener">${repoLabel(r)}</a>`).join(' · ')}</div>`;
    // when no repo could be read, empty lists would claim there is nothing open; show only the errors
    const errs = Object.entries(d.errors), cannot = `<div class="section">Could not read</div>` + errs.map(([r, e]) => `<div class="row-i"><span>${esc(r)}</span><span class="lbl bad">${esc(e)}</span></div>`).join('');
    if (errs.length === repos.length) return h + cannot + '</div>';
    // when some repos could not be read, say so first, and name the repos the lists cover
    const scope = errs.length ? ` in ${repos.filter(r => !(r in d.errors)).map(r => esc(repoLabel(r))).join(', ')}` : '';
    if (errs.length) h += cannot;
    h += `<div class="section">Issues by milestone${errs.length ? ` (${scope.trim()})` : ''}</div>`;
    const ms = Object.entries(d.milestones).sort((a, b) => (a[0] === 'No milestone') - (b[0] === 'No milestone') || b[1].open - a[1].open);
    h += ms.length ? ms.slice(0, 8).map(([m, v]) => `<div class="row-i"><span>${esc(m)}</span><span>${v.open} open</span></div>`).join('') : `<div class="row-i"><span>No open issues${scope}</span></div>`;
    h += `<div class="section">Open PRs (${d.prs.length}${scope})</div>`;
    h += d.prs.length ? d.prs.slice(0, 10).map(p => { const rl = p.labels.find(l => l.startsWith('review:')); const cls = rl === 'review:approved' ? 'ok' : rl === 'review:needs-maintainer' ? 'warn' : rl === 'review:changes-requested' ? 'bad' : 'n'; return `<div class="row-i"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(repoLabel(p.repo))} #${p.number} ${esc(p.title.slice(0, 48))}</a><span class="lbl ${cls}">${esc(rl || 'no review label')}</span></div>`; }).join('') : `<div class="row-i"><span>None open${scope}</span></div>`;
    h += `<div class="section">Changelog (merged)</div>`;
    h += d.merged.length ? d.merged.slice(0, 6).map(p => `<div class="row-i"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(repoLabel(p.repo))} #${p.number} ${esc(p.title.slice(0, 44))}</a><span>${fmt(p.at, true).replace(/ \d\d:\d\d .*$/, '')}</span></div>`).join('') : `<div class="row-i"><span>No merged PRs recently${scope}</span></div>`;
    return h + '</div>';
  }

  function renderCards() {
    let h = '';
    if (S.selected) h += agentCard(S.selected);
    if (S.room && S.view === 'floor') h += roomCard(S.room);
    $('cards').innerHTML = h;
  }

  // ---------- navigation ----------
  function goBuilding() { if (mobileQ.matches) return; S.view = 'building'; S.room = null; renderAll(); fitView(); applyCam(); }
  function goFloor(id) { S.view = 'floor'; S.level = id; S.room = null; if (S.selected && (agentDef(S.selected) || {}).level !== id) S.selected = null; S.tab = 'floor'; applyTab(); renderAll(); fitView(); applyCam(); }
  function selectAgent(id) {
    const A = agentDef(id); if (!A) return;
    S.selected = id;
    if (S.view === 'floor' && S.level !== A.level) { goFloor(A.level); S.selected = id; }
    if (mobileQ.matches) { S.tab = 'floor'; applyTab(); if (S.level !== A.level) goFloor(A.level); S.selected = id; }
    renderStage(false); renderCards();
    if (S.view === 'floor' && !mobileQ.matches) { fitView(); applyCam(); }
  }
  function applyTab() { document.body.classList.toggle('tab-inbox', S.tab === 'inbox'); document.querySelectorAll('#tabsM button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.tab)); }

  // walking (screen-relative directions mapped through the current rotation)
  function walk(dir) {
    if (S.view !== 'floor' || S.level === 'supervisor') return;
    const L = LEVELS.find(l => l.id === S.level), p = S.you[S.level];
    const st = .35, v = { up: [-st, -st], down: [st, st], left: [-st, st], right: [st, -st] }[dir];
    const [da, db] = v; let dx, dy;
    switch (S.rot & 3) { case 1: dx = db; dy = -da; break; case 2: dx = -da; dy = -db; break; case 3: dx = -db; dy = da; break; default: dx = da; dy = db; }
    p.x = Math.max(.4, Math.min(L.W - .4, p.x + dx)); p.y = Math.max(.4, Math.min(L.D - .4, p.y + dy));
    renderStage(false); follow();
  }
  function follow() {
    if (!S.scene) return;
    const p = S.you[S.level]; if (!p) return;
    const [sx, sy] = S.scene.p(p.x, p.y, 0), r = $('stage').getBoundingClientRect();
    const X = S.cam.x + sx * S.cam.k, Y = S.cam.y + sy * S.cam.k, m = .22;
    if (X < r.width * m) S.cam.x += r.width * m - X; if (X > r.width * (1 - m)) S.cam.x -= X - r.width * (1 - m);
    if (Y < r.height * m) S.cam.y += r.height * m - Y; if (Y > r.height * (1 - m)) S.cam.y -= Y - r.height * (1 - m);
    applyCam();
  }
  function nearby() {
    if (S.view !== 'floor' || S.level === 'supervisor') return null;
    const p = S.you[S.level], L = LEVELS.find(l => l.id === S.level); if (!p) return null;
    let best = null, bd = 1.6;
    for (const a of L.agents) { if (a.decor) continue; const d = Math.hypot(a.x - p.x, a.y - p.y); if (d < bd) { bd = d; best = a; } }
    return best;
  }
  function updateHint() { const a = nearby(); const el = $('hint'); el.hidden = !a || S.selected === (a && a.id); if (a) el.textContent = `Enter — talk to ${a.name}`; }

  // ---------- events ----------
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-go],[data-filter],[data-agent-jump],[data-level-jump],[data-close],[data-act],[data-move],[data-pause],[data-dispatch],[data-tab]');
    if (!t) return;
    if (t.dataset.go) t.dataset.go === 'building' ? goBuilding() : goFloor(t.dataset.go);
    else if (t.dataset.filter) { S.filter = t.dataset.filter; renderSide(); }
    else if (t.dataset.agentJump) { const A = agentDef(t.dataset.agentJump); if (A) { if (!mobileQ.matches) goFloor(A.level); selectAgent(A.id); } }
    else if (t.dataset.levelJump) goFloor(t.dataset.levelJump);
    else if (t.dataset.close) { if (t.dataset.close === 'agent') S.selected = null; else S.room = null; renderStage(false); renderCards(); }
    else if (t.dataset.act) {
      const a = t.dataset.act;
      if (a === 'rotl' || a === 'rotr') { S.rot = (S.rot + (a === 'rotr' ? 1 : 3)) & 3; prefs.rot = S.rot; ls.set('gl.prefs', prefs); renderStage(true); }
      if (a === 'zin') zoomAt(1.2); if (a === 'zout') zoomAt(1 / 1.2); if (a === 'fit') { fitView(); applyCam(); }
      if (a === 'legend') { prefs.legend = !prefs.legend; ls.set('gl.prefs', prefs); renderLegend(); }
    }
    else if (t.dataset.move) walk(t.dataset.move);
    else if (t.dataset.pause) pauseFlow(t.dataset.pause, t.dataset.href);
    else if (t.dataset.dispatch) dispatchFlow(t.dataset.dispatch);
    else if (t.dataset.tab) { S.tab = t.dataset.tab; applyTab(); if (S.tab === 'floor') { renderStage(true); } }
  });

  function toast(msg) { const el = $('toast'); el.textContent = msg; el.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => el.hidden = true, 4200); }
  async function pauseFlow(id, href) {
    const paused = !!(D.control.paused || {})[id];
    const entry = `"${id}": { "since": "${new Date().toISOString()}", "by": "${CFG.maintainer || 'maintainer'}", "reason": "" }`;
    if (!paused) { try { await navigator.clipboard.writeText(entry); toast('Pause entry copied. Paste it inside "paused": { } and commit.'); } catch (e) { toast(`Add inside "paused": ${entry}`); } }
    else toast(`Delete the "${id}" entry from "paused" and commit to resume.`);
    if (!PREVIEW) window.open(href, '_blank', 'noopener');
  }
  function dispatchFlow(url) {
    $('cfT').textContent = 'Run this workflow now?'; $('cfB').textContent = `${url.replace('https://github.com/', '')} on the default branch. This starts a real run.`;
    $('confirm').hidden = false;
    $('cfYes').onclick = async () => {
      $('confirm').hidden = true;
      try { const owner = /github\.com\/([^/]+)\//.exec(url)[1]; const r = await GLData.dispatch(new GLData.GitHub({ [owner]: dtokens[owner] }), url); toast(`Dispatched ${r.file} on ${r.ref}. It will report its own status.`); }
      catch (e) { toast(`Dispatch failed: ${e.message}`); }
    };
  }
  $('cfNo').onclick = () => $('confirm').hidden = true;

  // stage pointer handling: click, pan (right/middle drag, or left drag on empty space, or touch), pinch
  const stage = $('stage'); const ptrs = new Map(); let drag = null, pinch = null;
  stage.addEventListener('contextmenu', e => e.preventDefault());
  stage.addEventListener('pointerdown', e => {
    if (e.target.closest('.cards,.ctrl,.crumbs,.legend')) return;
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    stage.setPointerCapture(e.pointerId);
    if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), k: S.cam.k }; drag = null; return; }
    drag = { x: e.clientX, y: e.clientY, cx: S.cam.x, cy: S.cam.y, moved: false, btn: e.button, target: e.target };
  });
  stage.addEventListener('pointermove', e => {
    if (!ptrs.has(e.pointerId)) return; ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && ptrs.size === 2) { const [a, b] = [...ptrs.values()]; const r = stage.getBoundingClientRect(); const f = Math.hypot(a.x - b.x, a.y - b.y) / pinch.d; zoomAt(pinch.k * f / S.cam.k, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top); return; }
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 5) drag.moved = true;
    if (drag.moved) { S.cam.x = drag.cx + dx; S.cam.y = drag.cy + dy; applyCam(); }
  });
  const end = e => {
    ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch = null;
    if (!drag || e.type === 'pointercancel') { drag = null; return; }
    const d = drag; drag = null;
    if (d.moved || d.btn !== 0) return;
    const stack = document.elementsFromPoint(e.clientX, e.clientY);
    const pick = sel => { for (const el of stack) { const m = el.closest && el.closest(sel); if (m) return m; } return null; };
    const ag = pick('[data-agent]'), rm = pick('[data-room]'), lv = pick('[data-level]');
    if (ag) selectAgent(ag.dataset.agent);
    else if (S.view === 'building' && lv) goFloor(lv.dataset.level);
    else if (S.view === 'floor' && rm) { S.room = rm.dataset.room; renderCards(); if (!mobileQ.matches) { fitView(); applyCam(); } }
  };
  stage.addEventListener('pointerup', end); stage.addEventListener('pointercancel', end);
  stage.addEventListener('wheel', e => {
    if (e.target.closest('.cards')) return;
    e.preventDefault();
    const r = stage.getBoundingClientRect();
    if (e.ctrlKey || e.metaKey) zoomAt(Math.exp(-e.deltaY * .0025), e.clientX - r.left, e.clientY - r.top);
    else { S.cam.x -= e.deltaX; S.cam.y -= e.deltaY; applyCam(); }
  }, { passive: false });

  document.addEventListener('keydown', e => {
    if (e.target.closest('input,textarea,select')) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (k === 'Escape') {
      if (!$('confirm').hidden) { $('confirm').hidden = true; return; }
      if (!$('settings').hidden) { $('settings').hidden = true; return; }
      if (!$('soundPop').hidden) { $('soundPop').hidden = true; return; }
      if (S.selected || S.room) { S.selected = null; S.room = null; renderStage(false); renderCards(); return; }
      if (mobileQ.matches && S.tab === 'inbox') { S.tab = 'floor'; applyTab(); return; }
      if (S.view === 'floor') goBuilding(); return;
    }
    if (/^[1-9]$/.test(k)) { const L = LEVELS.find(l => String(l.key) === k); if (L) goFloor(L.id); return; }
    if (k === 'i' || k === 'I') { if (mobileQ.matches) { S.tab = S.tab === 'inbox' ? 'floor' : 'inbox'; applyTab(); } else { const s = $('side'); s.classList.remove('flash'); void s.offsetWidth; s.classList.add('flash'); s.scrollTop = 0; const f = s.querySelector('.item .t'); if (f) f.focus(); } return; }
    if (k === 'f' || k === 'F') { S.focus = !S.focus; prefs.focus = S.focus; ls.set('gl.prefs', prefs); renderTop(); renderStage(false); return; }
    if (k === 'r') { S.rot = (S.rot + 1) & 3; renderStage(true); return; } if (k === 'R') { S.rot = (S.rot + 3) & 3; renderStage(true); return; }
    if (k === '+' || k === '=') return zoomAt(1.2); if (k === '-' || k === '_') return zoomAt(1 / 1.2); if (k === '0') { fitView(); applyCam(); return; }
    const dir = { ArrowUp: 'up', w: 'up', ArrowDown: 'down', s: 'down', ArrowLeft: 'left', a: 'left', ArrowRight: 'right', d: 'right' }[k];
    if (dir && S.view === 'floor') { e.preventDefault(); walk(dir); return; }
    if (k === 'Enter' && S.view === 'floor') { const a = nearby(); if (a) selectAgent(a.id); }
  });

  $('focusBtn').onclick = () => { S.focus = !S.focus; prefs.focus = S.focus; ls.set('gl.prefs', prefs); renderTop(); renderStage(false); };
  $('inboxBtn').onclick = () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'i' }));
  $('soundBtn').onclick = () => { $('soundPop').hidden = !$('soundPop').hidden; };
  const sndLabel = () => { const s = GLAudio.state(); $('soundBtn').firstChild.textContent = (s.music || s.amb ? '🔊 ' : '🔇 '); };
  $('musicT').onchange = e => { GLAudio.setMusic(e.target.checked); sndLabel(); };
  $('ambT').onchange = e => { GLAudio.setAmbience(e.target.checked); sndLabel(); };
  $('volR').oninput = e => GLAudio.setVolume(+e.target.value);
  $('srcPill').onclick = () => PREVIEW ? toast('This preview only shows SAMPLE data. The hosted app reads GitHub.') : openSettings();
  $('settingsBtn').onclick = () => openSettings();
  if (PREVIEW) $('settingsBtn').hidden = true;

  // ---------- settings ----------
  function openSettings() {
    $('tokRows').innerHTML = OWNERS.map(o => `<div class="tok"><label for="t-${o}">${o}</label><input id="t-${o}" type="password" autocomplete="off" placeholder="github_pat_…" value="${esc(tokens[o] || '')}"></div>`).join('');
    $('dispRows').innerHTML = OWNERS.map(o => `<div class="tok"><label for="d-${o}">${o}</label><input id="d-${o}" type="password" autocomplete="off" placeholder="optional" value="${esc(dtokens[o] || '')}"></div>`).join('');
    $('remember').checked = !!prefs.remember; $('useSample').checked = !!prefs.useSample;
    const rows = [];
    rows.push(`<div><span>Status files · ${esc(CFG.statusRepo)}@${esc(CFG.statusBranch)}</span><b>${D.mode === 'sample' ? 'sample mode' : D.statusErr ? esc(D.statusErr) : `${D.rows.length} files read${D.invalid.length ? `, ${D.invalid.length} invalid` : ''}`}</b></div>`);
    for (const r of allRepos) { const e = D.prErr[r] || D.runErr[r]; rows.push(`<div><span>${esc(r)}</span><b style="color:${D.mode === 'sample' ? 'var(--muted)' : e ? 'var(--bad)' : 'var(--ok)'}">${D.mode === 'sample' ? '—' : e ? esc(String(e)) : 'ok'}</b></div>`); }
    if (D.invalid.length) rows.push(...D.invalid.map(i => `<div><span>${esc(i.path)}</span><b style="color:var(--bad)">invalid: ${esc(i.errs.join(', '))}</b></div>`));
    if (D.rate) rows.push(`<div><span>GitHub API requests left this hour</span><b>${D.rate.remaining}</b></div>`);
    // sample rows are invented, so only a finished live read of the status files says who reports
    const read = D.mode === 'live' && D.updated && !D.statusErr;
    const chk = Layout.check(CFG, LEVELS, read ? D.rows.map(r => r.agent) : []);
    const list = ids => ids.map(esc).join(', ');
    rows.push(...chk.problems.map(p => `<div><span>config.js</span><b style="color:var(--bad)">${esc(p)}</b></div>`));
    if (read) {
      if (chk.unplaced.length) rows.push(`<div><span>Reporting, but on no floor (add to ${Building.generated ? 'config.js' : 'building.js'})</span><b style="color:var(--bad)">${list(chk.unplaced)}</b></div>`);
      if (chk.silent.length) rows.push(`<div><span>On a floor, but no status file read</span><b style="color:var(--muted)">${list(chk.silent)}</b></div>`);
    }
    $('conn').innerHTML = `<div class="conn">${rows.join('')}</div>`;
    $('settings').hidden = false;
  }
  $('setClose').onclick = () => $('settings').hidden = true;
  $('setSave').onclick = () => {
    const nt = {}, nd = {};
    OWNERS.forEach(o => { const v = $('t-' + o).value.trim(); if (v) nt[o] = v; const w = $('d-' + o).value.trim(); if (w) nd[o] = w; });
    prefs.remember = $('remember').checked; prefs.useSample = $('useSample').checked; ls.set('gl.prefs', prefs);
    ['gl.tokens', 'gl.dtokens'].forEach(k => { ls.del(k); ls.del(k, true); });
    ls.set('gl.tokens', nt, !prefs.remember); ls.set('gl.dtokens', nd, !prefs.remember);
    tokens = nt; dtokens = nd; gh = null; roomCache.clear(); lastRuns = 0; D.updated = null; // a read still in flight is dropped, so D.updated next comes from a read with these tokens
    $('settings').hidden = true; refresh(true);
  };

  // ---------- boot ----------
  mobileQ.addEventListener('change', () => { renderAll(); fitView(); applyCam(); });
  addEventListener('resize', () => { clearTimeout(window.__rz); window.__rz = setTimeout(() => { fitView(); applyCam(); }, 150); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  if (mobileQ.matches) { S.view = 'floor'; S.level = CFG.defaultLevel || S.level; }
  applyTab();
  tickClock(); setInterval(tickClock, 30000);
  if (useSampleNow()) loadSample(); else Object.assign(D, { mode: 'live', rows: [], prs: [], runs: [], control: { paused: {} } });
  renderAll(); fitView(); applyCam();
  const cfgProblems = Layout.check(CFG, LEVELS, []).problems;
  if (cfgProblems.length) { cfgProblems.forEach(p => console.warn('config.js:', p)); toast(`config.js has ${cfgProblems.length} problem${cfgProblems.length > 1 ? 's' : ''}; see Settings`); }
  refresh(true);
  setInterval(() => refresh(), CFG.refreshSeconds * 1000);
  setInterval(() => { if (D.updated) renderTop(); }, 60000);
  window.__gl = { S, D, refresh };
})();
