// SPDX-License-Identifier: Apache-2.0
// Read-only GitHub data layer. Everything returned is tagged source:"live"; nothing is synthesised.
(function (G) {
  const API = 'https://api.github.com';
  const STATUSES = ['idle', 'running', 'waiting', 'blocked', 'failed', 'sleeping', 'not_deployed'];

  class GitHub {
    constructor(tokens) { this.tokens = tokens || {}; this.cache = new Map(); this.rate = null; }
    tokenFor(repo) { const owner = (repo || '').split('/')[0]; return this.tokens[owner] || this.tokens['*'] || null; }
    hasToken() { return Object.values(this.tokens).some(Boolean); }
    async req(path, repo, opt = {}) {
      const tok = this.tokenFor(repo);
      const headers = { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
      if (tok) headers.Authorization = `Bearer ${tok}`;
      const c = this.cache.get(path);
      if (c && c.etag && !opt.method) headers['If-None-Match'] = c.etag;
      const res = await fetch(API + path, { method: opt.method || 'GET', headers: opt.body ? { ...headers, 'Content-Type': 'application/json' } : headers, body: opt.body ? JSON.stringify(opt.body) : undefined, cache: 'no-store' });
      const rl = res.headers.get('x-ratelimit-remaining'); if (rl) this.rate = { remaining: +rl, reset: +res.headers.get('x-ratelimit-reset') * 1000 };
      if (res.status === 304 && c) return c.data;
      if (opt.method && res.status === 204) return null;
      if (!res.ok) { const e = new Error(`${res.status} ${res.statusText}`); e.status = res.status; e.path = path; throw e; }
      const data = await res.json();
      if (!opt.method) this.cache.set(path, { etag: res.headers.get('etag'), data });
      return data;
    }
  }

  const b64 = s => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, '')), c => c.charCodeAt(0)));

  function validate(o, path) {
    const errs = [];
    if (!o || typeof o !== 'object') return ['not an object'];
    if (o.schema !== 'gatherlane.agent-status/v1') errs.push('schema');
    if (!o.agent) errs.push('agent');
    if (!STATUSES.includes(o.status)) errs.push('status');
    if (!o.updated_at || isNaN(Date.parse(o.updated_at))) errs.push('updated_at');
    if (typeof o.needs_human !== 'boolean') errs.push('needs_human');
    return errs;
  }

  async function pool(items, n, fn) {
    const out = []; let i = 0;
    await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k]).catch(e => ({ __err: e })); } }));
    return out;
  }

  const blobCache = new Map();
  async function loadStatus(gh, cfg) {
    const repo = cfg.statusRepo, br = cfg.statusBranch;
    const tree = await gh.req(`/repos/${repo}/git/trees/${encodeURIComponent(br)}?recursive=1`, repo);
    const files = tree.tree.filter(t => t.type === 'blob' && /^status\/.+\.json$/.test(t.path));
    const ctl = tree.tree.find(t => t.path === 'control/pause.json');
    const want = ctl ? [...files, ctl] : files;
    await pool(want.filter(f => !blobCache.has(f.sha)), 6, async f => {
      const b = await gh.req(`/repos/${repo}/git/blobs/${f.sha}`, repo);
      let parsed; try { parsed = JSON.parse(b64(b.content)); } catch (e) { parsed = { __parse: String(e) }; }
      blobCache.set(f.sha, parsed);
    });
    const rows = [], invalid = [];
    for (const f of files) {
      const o = blobCache.get(f.sha);
      const errs = o && !o.__parse ? validate(o, f.path) : ['invalid JSON'];
      if (errs.length) invalid.push({ path: f.path, errs });
      else rows.push({ ...o, source: 'live', _path: f.path });
    }
    const control = ctl ? { ...(blobCache.get(ctl.sha) || {}), source: 'live' } : { paused: {}, source: 'live', missing: true };
    return { rows, control, invalid, truncated: !!tree.truncated };
  }

  async function loadPRs(gh, repos) {
    const out = { prs: [], errors: {} };
    await pool(repos, 5, async r => {
      try {
        const list = await gh.req(`/repos/${r}/pulls?state=open&per_page=100`, r);
        for (const p of list) out.prs.push({ repo: r, number: p.number, title: p.title, url: p.html_url, labels: p.labels.map(l => l.name), draft: p.draft, updated_at: p.updated_at, user: p.user && p.user.login, source: 'live' });
      } catch (e) { out.errors[r] = e.status || e.message; }
    });
    return out;
  }

  async function loadFailedRuns(gh, repos) {
    const out = { runs: [], errors: {} };
    const weekAgo = Date.now() - 7 * 864e5;
    await pool(repos, 5, async r => {
      try {
        const d = await gh.req(`/repos/${r}/actions/runs?per_page=40&exclude_pull_requests=true`, r);
        const latest = new Map();
        for (const run of d.workflow_runs) {
          if (run.status !== 'completed' || run.event === 'pull_request') continue;
          if (!latest.has(run.workflow_id)) latest.set(run.workflow_id, run);
        }
        for (const run of latest.values())
          if (['failure', 'timed_out', 'startup_failure'].includes(run.conclusion) && Date.parse(run.updated_at) > weekAgo)
            out.runs.push({ repo: r, name: run.name, branch: run.head_branch, url: run.html_url, at: run.updated_at, conclusion: run.conclusion, source: 'live' });
      } catch (e) { out.errors[r] = e.status || e.message; }
    });
    return out;
  }

  async function loadRoom(gh, repos) {
    const res = { milestones: {}, prs: [], merged: [], errors: {} };
    await pool(repos, 4, async r => {
      try {
        const issues = await gh.req(`/repos/${r}/issues?state=open&per_page=100`, r);
        for (const i of issues) {
          if (i.pull_request) continue;
          const m = i.milestone ? i.milestone.title : 'No milestone';
          (res.milestones[m] = res.milestones[m] || { open: 0, items: [], due: i.milestone && i.milestone.due_on }).open++;
          res.milestones[m].items.push({ repo: r, number: i.number, title: i.title, url: i.html_url });
        }
        const prs = await gh.req(`/repos/${r}/pulls?state=open&per_page=50`, r);
        for (const p of prs) res.prs.push({ repo: r, number: p.number, title: p.title, url: p.html_url, labels: p.labels.map(l => l.name) });
        const closed = await gh.req(`/repos/${r}/pulls?state=closed&sort=updated&direction=desc&per_page=15`, r);
        for (const p of closed) if (p.merged_at) res.merged.push({ repo: r, number: p.number, title: p.title, url: p.html_url, at: p.merged_at });
      } catch (e) { res.errors[r] = e.status || e.message; }
    });
    res.merged.sort((a, b) => b.at.localeCompare(a.at));
    return res;
  }

  async function dispatch(gh, workflowUrl) {
    const m = /github\.com\/([^/]+\/[^/]+)\/actions\/workflows\/([^/?#]+)/.exec(workflowUrl || '');
    if (!m) throw new Error('No workflow URL in the status file');
    const [, repo, file] = m;
    const info = await gh.req(`/repos/${repo}`, repo);
    await gh.req(`/repos/${repo}/actions/workflows/${file}/dispatches`, repo, { method: 'POST', body: { ref: info.default_branch } });
    return { repo, file, ref: info.default_branch };
  }

  G.GLData = { GitHub, loadStatus, loadPRs, loadFailedRuns, loadRoom, dispatch, validate };
})(typeof window !== 'undefined' ? window : globalThis);
