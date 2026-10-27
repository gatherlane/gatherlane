// SPDX-License-Identifier: Apache-2.0
// SAMPLE status records for the example fleet. Every record carries source:"sample". Nothing here is a live reading.
(function (G) {
  const T = (h, m = 0, d = 26) => `2026-10-${String(d).padStart(2, '0')}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00Z`;
  const S = (agent, operation, pod, status, o = {}) => ({
    schema: 'gatherlane.agent-status/v1', agent, operation, pod, status,
    current_task: null, last_run_at: null, last_result: null, last_result_url: null,
    next_run_at: null, schedule: null, needs_human: false, needs_human_reason: null, needs_human_kind: null,
    links: {}, updated_at: T(7, 15), source: 'sample', ...o,
  });

  const rows = [
    S('orchestrator-1', 'shared', 'den', 'running', { current_task: { title: 'Cycle: implementer then reviewer (sample)', url: null }, last_run_at: T(6, 40) }),

    S('acme/implementer', 'acme', 'build', 'running', { current_task: { title: 'Sample: issue #42 in acme/web', url: null }, last_run_at: T(7, 2) }),
    S('acme/pr-reviewer', 'acme', 'build', 'idle', { last_run_at: T(6, 10), last_result: 'success' }),
    S('acme/support', 'acme', 'support', 'waiting', {
      current_task: { title: 'Customer asks for a refund outside policy (sample)', url: null },
      last_run_at: T(7, 9), last_result: 'success', schedule: { cron: '*/15 * * * *', tz: 'UTC' }, next_run_at: T(7, 30),
      needs_human: true, needs_human_kind: 'escalation', needs_human_reason: 'Refund outside policy: the runbook says escalate (sample)',
    }),
    S('acme/triage', 'acme', 'triage', 'failed', { last_run_at: T(2, 0), last_result: 'failure', needs_human: true, needs_human_kind: 'failed_run', needs_human_reason: 'Nightly triage run failed (sample)' }),

    S('growth/writer', 'growth', 'content', 'blocked', { needs_human_reason: 'Waiting on product screenshots (sample)' }),
    S('growth/analytics', 'growth', 'insights', 'sleeping', { last_run_at: T(6, 0), last_result: 'success', schedule: { cron: '0 6 * * *', tz: 'UTC' }, next_run_at: T(6, 0, 27) }),
    S('growth/social', 'growth', 'launch', 'not_deployed'),
  ];

  // Inbox items the office derives from GitHub (PR labels), SAMPLE here.
  const prs = [
    { repo: 'acme/web', number: 41, title: 'Sample PR: checkout retries', label: 'review:approved', url: 'https://github.com/acme/web/pulls', source: 'sample' },
    { repo: 'acme/api', number: 17, title: 'Sample PR: rate limit headers', label: 'review:needs-maintainer', url: 'https://github.com/acme/api/pulls', source: 'sample' },
  ];

  const control = { schema: 'gatherlane.control/v1', paused: { 'growth/analytics': { since: T(21, 0, 25), by: 'maintainer', reason: 'sample pause' } }, source: 'sample' };

  G.SAMPLE = { rows, prs, control, now: '2026-10-26T07:21:00Z' };
})(typeof window !== 'undefined' ? window : globalThis);
