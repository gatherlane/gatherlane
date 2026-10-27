// SPDX-License-Identifier: Apache-2.0
// Gatherlane configuration: where status lives, which repos to watch, and what each agent is.
// This is the example fleet. Copy examples/instance/ to app/instance/ and edit it for your own.
// The building is generated from this file; building.js can replace it with a hand-drawn one.
(function (G) {
  const gh = r => `https://github.com/${r}`;
  const RB = r => `https://github.com/${r}/blob/main/.claude/agents/`;

  G.GATHERLANE_CONFIG = {
    // Status files: status/<operation>/<agent>.json and control/pause.json on this branch.
    statusRepo: 'acme/gatherlane',
    statusBranch: 'status',
    refreshSeconds: 120,      // status + PR labels
    runsRefreshSeconds: 300,  // workflow runs (failed-run inbox items)
    timeZone: 'UTC',
    // timeZoneLabel: 'UTC', // shown after times; leave out to use the browser's short name for timeZone
    // dayParts: ['night', 'morning', 'midday', 'afternoon'], // under the clock: 18-4, 4-11, 11-15, 15-18
    maintainer: 'maintainer', // written as "by" in pause entries
    defaultLevel: 'product',  // floor shown first on a phone
    fallbackOperation: 'shared', // operation for ids with no slash and no agentPrefixes match
    // Token owners are worked out from statusRepo and the repos below; list any extra ones here.
    extraTokenOwners: [],

    operations: {
      acme: {
        name: 'Product Studio', level: 'product',
        repos: ['acme/web', 'acme/api'],
        rooms: [{ id: 'build', name: 'Build room' }, { id: 'support', name: 'Support desk' }, { id: 'triage', name: 'Triage' }],
        roomRepos: { build: ['acme/web', 'acme/api'], support: ['acme/web'] },
        site: 'acme.example',
      },
      growth: {
        name: 'Growth Floor', level: 'growth', repos: ['acme/docs'],
        rooms: [{ id: 'content', name: 'Content pod' }, { id: 'insights', name: 'Insights' }, { id: 'launch', name: 'Launch room' }],
      },
      // agent ids starting with these prefixes report under this operation (keep in step with GATHERLANE_OPS)
      shared: { name: 'Coordination Den', level: 'den', repos: [], agentPrefixes: ['orchestrator'], rooms: [{ id: 'den', name: 'Orchestrator den' }] },
    },

    // PR labels that put a pull request in the inbox
    inboxLabels: { 'review:approved': 'ready to merge', 'review:needs-maintainer': 'needs maintainer' },

    agents: {
      'orchestrator-1': { room: 'den', role: 'Orchestrator session: runs implementer and reviewer cycles', runbook: null },

      'acme/implementer': { room: 'build', role: 'Implements one issue per pull request', runbook: RB('acme/web') + 'implementer.md', repo: 'acme/web' },
      'acme/pr-reviewer': { room: 'build', role: 'Reviews each pull request and sets a review:* label', runbook: RB('acme/web') + 'pr-reviewer.md', repo: 'acme/web' },
      'acme/support': { room: 'support', role: 'Answers customer email, escalates refunds', runbook: null },
      'acme/triage': { room: 'triage', role: 'Labels and routes new issues', runbook: null, repo: 'acme/api' },

      'growth/writer': { room: 'content', role: 'Drafts docs pages and release notes', runbook: null, repo: 'acme/docs' },
      'growth/analytics': { room: 'insights', role: 'Morning brief: sign-ups, retention, anomalies', runbook: null },
      'growth/social': { room: 'launch', role: 'Social posts from release notes', runbook: null, note: 'Not built yet' },
    },
  };
  G.GATHERLANE_CONFIG.gh = gh;
})(typeof window !== 'undefined' ? window : globalThis);
