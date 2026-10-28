# Gatherlane roadmap: open-source core and cloud

Updated 27 October 2026. Plans change; the issues and milestones on GitHub are the current state.

## The rule every milestone keeps

The office never shows a status that did not come from a status file or from GitHub. Every badge
links to the event behind it, sample data is always labelled SAMPLE, and live and sample data are
never mixed. A feature that would need to guess a state is out of scope, in the free core and in
the cloud alike. This is the product's main promise, so it is also a test requirement: each
milestone adds tests that fail if the office shows a state with no source.

## Where it stands

| Area | Today |
|---|---|
| Site | Static single-page app, about 2,100 lines of plain JavaScript, no build step, no backend |
| Data | GitHub only: status files on a `status` branch, PR labels, Actions runs, read with fine-grained tokens kept in the browser |
| Reporter | `tools/gatherlane.py`, standard library only. Settings come from the environment or `~/.config/gatherlane/env` |
| Fleet setup | Generic engine in `app/js/`. The instance (`config.js`, `building.js`, `sample.js`) lives in `app/instance/`, with a neutral example in `examples/instance/`; a test fails if an instance name leaks outside it. The building layout is still drawn by hand |
| Tests | Reporter unit tests (standard library), two Playwright smoke scripts run against both instances, CI on every pull request, Playwright pinned in `package.json` |
| Licence | None |

## M0: Ready to publish

Goal: someone who is not the maintainer can clone it, see a demo, and get their own office live.

- **Done.** Move the instance files out of the engine. They live in `app/instance/`
  (`config.js`, `building.js`, `sample.js`); `examples/instance/` is a neutral example fleet that
  the public repo ships in their place. A private instance keeps its own `app/instance/`.
- **Done.** Licence files and headers (Apache-2.0 for the core), `CONTRIBUTING.md`, `SECURITY.md`,
  a code of conduct.
- **Done.** `package.json` with Playwright pinned, a Python test file for the reporter (operation
  mapping, env file parsing, pause handling, cron parsing), and a GitHub Actions CI job that runs
  both, against the instance and against the example.
- A public demo on Cloudflare Pages in sample mode, with the SAMPLE label kept.
- Publish from a fresh history: `tools/export_public.py` builds the public tree (engine plus the
  example instance), scans it for the private instance's names and commits it as one first
  commit. The private repository keeps its own history.

Done means: a fresh clone passes CI, the demo is online, and `git grep` for the instance's
organisation and people names finds nothing.

## M1: Your office in ten minutes

Goal: no hand-drawn layout. The biggest barrier today is `building.js`.

- **Done.** Auto-layout: floors and rooms are built from `config.js` (an operation's `level` is its
  floor, an agent's `room` its room, desks in order). `building.js` stays as an optional override
  for people who want to arrange furniture.
- **Done.** `gatherlane init`: creates the status branch, writes a starter `app/instance/`,
  registers the agents, adds the settings to the env file, and prints the label commands and the
  Pages and token steps. Labels are printed rather than created, because the reporter's token
  normally only reaches the status repo.
- **Done.** A config check in the app: Settings lists agents that report but are on no floor, and
  agents on a floor with no status file. It also flags a level named `supervisor` (reserved for
  the maintainer's office) and more than nine numbered floors, with a notice when the app opens.

Done means: a new user goes from clone to a live office with three agents in under ten minutes,
timed with someone who has not seen the project.

## M2: Report from anywhere

Goal: every common agent runner can report without copy-pasting shell.

- A published GitHub Action (`uses: gatherlane/report@v1`) that wraps `run`.
- A Claude Code plugin: a skill that appends the "Gatherlane status" section to `.claude/agents/*.md`
  and a hook that reports `running` and `idle` around subagent runs.
- An MCP server exposing `report` and `check_pause` as tools, so any MCP-capable agent can report
  without shell access.
- The reporter on PyPI (`pipx install gatherlane`), still dependency-free.
- n8n community node, once the n8n snippet has real users asking for it.

Done means: each path has an example repo whose status shows in the public demo's live mode.

## M3: More than GitHub

Goal: the same office on other forges.

- A data-source interface in `data.js` with GitHub as the first implementation.
- GitLab (status branch, merge request labels, pipelines) and Gitea or Forgejo.
- The reporter writes through the same interface.

Done means: the live-mock test passes against a mocked GitLab API.

## M4: Cloud foundation

Goal: the hosted version, built only after enough outside teams run their own office and ask for a
hosted one.

- A GitHub App replaces personal tokens: sign-in, read access, and write access for Pause and
  Run now without a manual commit.
- A small ingest API on Cloudflare Workers with D1 or KV. Reporters can post status over HTTPS
  instead of committing; the git mode stays for self-hosting. Committing on every status change
  hits GitHub's rate limits for large fleets and fills the branch with noise; the API removes both.
- Status history (a timeline per agent) and alerts by Web Push, Telegram, Slack, email and
  WhatsApp, triggered only by real events.
- Multi-user offices with roles.

Done means: three outside teams use the cloud for a month with no state shown that cannot be
traced to an event.

## M5: Enterprise edition

- SAML SSO and SCIM, audit log, longer history, multiple offices per organisation, export.
- These live in an `ee/` directory under the enterprise licence, the way OpenCTI separates its
  editions. Everything outside `ee/` stays Apache-2.0.

## Order and pace

M0 and M1 come first and in that order; nothing public happens before M0. M2 can overlap M1. M3
waits for requests from outside users. M4 and M5 wait for demand from outside teams. At part-time pace (about eight hours a week), M0 is roughly two weeks and
M1 about a month.
