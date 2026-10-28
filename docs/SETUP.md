# Setting up Gatherlane

Five steps take it from sample to live. Do steps 1 to 3 once; step 4 is per agent, and step 5 is
the list of things that keep the status current. In the commands below, `<owner>` is the GitHub
user or organisation that holds your Gatherlane repo.

## 1. Create the repo and the status branch

1. Create `<owner>/gatherlane` as a private repo and push this folder to `main`:

   ```sh
   gh repo create <owner>/gatherlane --private
   git remote add origin git@github.com:<owner>/gatherlane.git   # skip if origin is already set
   git push -u origin main
   ```

2. Make the writer token: a fine-grained token for `<owner>/gatherlane` only, with Contents: read
   and write. Save it as `export GATHERLANE_TOKEN=...` in `~/.config/gatherlane/env` (`chmod 600`).

3. Set up the office with `init`, naming your agents (`<operation>/<agent>`) and the repos whose
   pull requests and workflow runs should reach the inbox:

   ```sh
   python3 tools/gatherlane.py init --repo <owner>/gatherlane \
     --agent web/implementer --agent web/pr-reviewer --agent support/inbox \
     --watch <owner>/web --watch support:<owner>/helpdesk \
     --maintainer <your name> --tz Europe/Berlin
   ```

   It checks the token, creates the `status` branch with `control/pause.json`, writes
   `app/instance/` (config, a generated building, SAMPLE data), registers each agent as
   `not_deployed`, adds `GATHERLANE_REPO` and `GATHERLANE_TZ` to the env file (never the token),
   and prints the label commands and the remaining steps. `--watch OWNER/REPO` attaches the repo
   to the first operation that is not the shared den; `OPERATION:OWNER/REPO` picks one. It will not replace an existing
   instance without `--force`. Status files live only on `status`, so agent writes never touch
   `main` or trigger site builds.

   Without `init`: `python3 tools/gatherlane.py init-branch` creates the branch, and you copy
   `examples/instance/` to `app/instance/` and set `statusRepo` there and `GATHERLANE_REPO` in
   the env file yourself.

## 2. Host it on Cloudflare Pages behind Cloudflare Access

**Pages**
1. Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git → choose
   `<owner>/gatherlane`. If it is not listed, give the Cloudflare Pages GitHub app access to that
   repo in the owner's settings.
2. Production branch `main`. Framework preset: None. Build command: leave empty.
   Build output directory: `app`.
3. Settings → Builds → Branch control: set preview deployments to **None**, so the `status`
   branch never builds.
4. Optional custom domain, for example `office.example.com` (Custom domains → Set up).

`app/_headers` is picked up by Pages. It sets a Content-Security-Policy that only allows the page
to talk to `api.github.com`, and blocks framing.

**Access** (only your email can open it)
1. Zero Trust → Access → Applications → Add → Self-hosted.
2. Add both hostnames: your custom domain and `<project>.pages.dev` (the name Pages gave the
   project). Also add `*.<project>.pages.dev` in case a preview ever gets built.
3. Policy: Action Allow, Include → Emails → your address. Session duration 24 h or what you prefer.
4. Identity: the default one-time PIN by email works. Google login is nicer on the phone.

Nothing else runs on Cloudflare. The page is static, and your browser calls GitHub directly.

## 3. Read-only tokens (entered in the app, never committed)

Fine-grained tokens belong to one owner, so make one per owner whose repos you watch. GitHub →
Settings → Developer settings → Fine-grained tokens → Generate:

| Resource owner | Repositories | Permissions (all Read-only) |
|---|---|---|
| `<owner>` | gatherlane, plus any watched repos it owns | Contents, Issues, Pull requests, Actions, Metadata |
| each other owner in `app/instance/config.js` | the watched repos it owns | same |

Organisations can require approval for fine-grained tokens. Approve them under the org's
Settings → Personal access tokens → Pending requests. Set an expiry and a calendar reminder; an
expired token shows as errors in Settings → connections, not as fake data.

In the app: ⚙ → paste each token → tick "Remember tokens on this device" only on your own
devices → Save. The pill turns green (**LIVE**) and Settings lists every repo as ok or with its
error code.

**Optional: Run now.** "Run workflow" opens GitHub's dispatch page by default. To start runs from
Gatherlane itself, add a separate token per owner with Actions: Read and write on the agent repos
in the "run workflows" section. It is used only after you press "Run now" and confirm.

## 4. Make each agent report

Agents write `status/<operation>/<agent>.json` on the `status` branch with `tools/gatherlane.py`.

**The writer token.** `GATHERLANE_TOKEN`: fine-grained, owner `<owner>`, repository gatherlane
only, Contents: Read and write. Store it as an Actions secret where agents run in GitHub Actions,
and on every machine that runs agents:

```sh
mkdir -p ~/.config/gatherlane && chmod 700 ~/.config/gatherlane
printf 'export GATHERLANE_TOKEN=%s\n' 'github_pat_...' > ~/.config/gatherlane/env
cat >> ~/.config/gatherlane/env <<'EOF'
export GATHERLANE_REPO=<owner>/gatherlane
export GATHERLANE_TZ=UTC                      # IANA name; schedules and timestamps use it
export GATHERLANE_OPS=                        # optional, see "Agent ids" below
EOF
chmod 600 ~/.config/gatherlane/env
git clone git@github.com:<owner>/gatherlane.git ~/gatherlane   # the reporter, where runbooks expect it
```

Type the token in your own terminal; do not paste it into an agent session. The reporter reads
this file itself for any `GATHERLANE_*` setting not already in the environment, so an agent session
does not need to source it. `GATHERLANE_ENV` points it at a different file.

**Agent ids.** An id is `<operation>/<agent>`, and the same id goes in `app/instance/config.js`
(and in `building.js` if you draw the building by hand) and on the reporter's `--agent`. The id's first part is its operation, and the
file goes to `status/<operation>/<agent>.json`. An id without a slash, such as `orchestrator-1`,
goes to `shared`. When several prefixes share one operation, list them in both places:
`agentPrefixes` on the operation in `config.js`, and `GATHERLANE_OPS` for the reporter, for
example `GATHERLANE_OPS=web=oss,api=oss,orchestrator=shared`. The office matches status
to characters by the `agent` field, so a file in another folder still shows; only the "no status
file at" hint uses the path.

**Wrapping a command.** The simplest wiring wraps the agent's command:

```sh
python3 ~/gatherlane/tools/gatherlane.py run --agent <operation>/<agent> --cron "*/15 * * * *" -- ./run-agent.sh
```

`run` checks the pause flag (skips the run if paused), reports `running`, runs the command, then
reports `idle`, `sleeping` (next run is more than an hour away), `failed` (non-zero exit, which
also puts it in your inbox), or `waiting` if the command wrote a request to `$GATHERLANE_OUT`:

```sh
echo '{"needs_human_kind":"escalation","reason":"Refund outside policy","issue":"https://github.com/..."}' > "$GATHERLANE_OUT"
```

`--cron` is read in `GATHERLANE_TZ` (UTC if unset). Set `timeZone` in `config.js` to the same
zone so the office shows times the way the agents report them.

**By runner:**

| Where the agent runs | Wiring |
|---|---|
| cron on an agent host | `run` wrapper, cron lines in `examples/cron-and-sessions.md` |
| GitHub Actions | `examples/github-actions-agent.yml` |
| n8n | Execute Command nodes, snippet in `examples/cron-and-sessions.md` |
| Claude Code subagents (`.claude/agents/*.md`) | the "Gatherlane status" section in `examples/cron-and-sessions.md`, appended to each agent file |
| Orchestrator sessions | report `running` at the start of a cycle and `idle` at the end, as `orchestrator-1`, `orchestrator-<n>` |

**Agents that are not running yet.** Mark them `not_deployed` once, so the office shows "not
deployed" instead of "no data". `examples/cron-and-sessions.md` has a loop over every id in
`config.js`. Each agent's own first report replaces it. This step is also how a new agent is
registered: the reporter refuses an id with no status file unless you pass `--new`, which catches
mistyped ids in runbooks.

**Review labels.** PR review state needs no reporting. PRs labelled `review:approved` or
`review:needs-maintainer` in any watched repo reach the inbox straight from GitHub, and so do
failed workflow runs from the last 7 days. Create the labels in every watched repo, with one
colour scheme everywhere:

```sh
for r in <owner>/<repo> ...; do
  gh label create review:approved          -R "$r" --color 0e8a16 --description "Reviewed and ready for the maintainer to merge"
  gh label create review:changes-requested -R "$r" --color d93f0b --description "Review found blocking issues"
  gh label create review:needs-maintainer  -R "$r" --color fbca04 --description "Needs a maintainer decision"
done
```

**Pause flag.** Gatherlane's Pause button copies an entry and opens `control/pause.json` on
GitHub for you to commit. Agents wrapped with `run` honour it on their next run; agents that report
by hand call `gatherlane.py check-pause --agent ID` before acting (exit code 3 means paused).

**Checking the status branch.** Validate every file on a fresh checkout:

```sh
git clone -q --branch status --single-branch git@github.com:<owner>/gatherlane.git /tmp/gl-status
cd /tmp/gl-status && python3 tools/gatherlane.py validate $(find control status -name '*.json')
```

## 5. What must keep running

- **The runners themselves.** Status is only as fresh as the last report: GitHub Actions
  schedules, cron hosts (powered on and online), and n8n. A runner that stops leaves its last
  status in place, and the office marks it **stale** once it is older than twice the schedule
  interval.
- **GitHub Actions schedules in quiet repos.** GitHub disables scheduled workflows in public repos
  after 60 days without activity. Re-enable them from the Actions tab if that happens.
- **Tokens.** The writer token (agents) and your read tokens (browser) expire on the dates you set.
- **Nothing else.** Gatherlane has no server, database or poller. While the page is open it
  refreshes status and PR labels every 2 minutes and workflow runs every 5. Unchanged responses
  return 304 and do not count against GitHub's 5,000 requests per hour.

## Adding or changing agents and repos

Everything below is in `app/instance/`. A new office starts as a copy of `examples/instance/`.

- New repo to watch: add it to the operation's `repos` in `config.js`.
- New agent: add it to `agents` in `config.js` with its role and runbook, and optionally a
  `room`, a `name` and a `look`. Its id is what the reporter uses with `--agent`; register it once
  with `report --status not_deployed --new`.
- New operation: add it to `operations` in `config.js` with a `level` (its floor) and, if you like,
  `rooms: [{ id, name }]` to name and order the rooms. If its agents use more than one id prefix,
  list them in `agentPrefixes` and in `GATHERLANE_OPS`.
- The building is generated from `config.js` (`app/js/layout.js`): one floor per `level`, one room
  per agent `room` (default `team`) plus a lounge, a desk per agent, a look worked out from the id,
  and a supervisor office when `maintainer` is set. To draw it by hand instead, define
  `G.Building` in `building.js`; `examples/building-custom.js` is a full example.
- Instance settings in `config.js`: `timeZone`, `timeZoneLabel` and `dayParts` (the words under
  the clock), `maintainer` (written in
  pause entries), `defaultLevel` (first floor on a phone), `extraTokenOwners`. Token owners are
  otherwise worked out from `statusRepo` and the watched repos.
- Inbox labels: `inboxLabels` in `config.js`.

## Tests

CI (`.github/workflows/ci.yml`) runs all of these on every pull request. Locally:

```sh
npm ci && npx playwright install chromium   # Playwright is pinned to 1.49.0 in package.json
npm run test:py        # reporter unit tests and the engine-is-generic check (standard library only)
npm run test:layout    # the generated building: every agent placed once, in its room, no overlaps
npm run test:browser   # sample mode and mocked live mode, against app/instance
npm run test:example   # the same two, against examples/instance
```

Screenshots land in `out/`. The browser tests read the floors, agents and repos from the instance
under test, so they need no edits when the fleet changes, and they exit non-zero on any page error.
`live-mock.js` injects one invalid status file and one 404 repo on purpose and checks that the app
reports both rather than hiding them. `GATHERLANE_INSTANCE=<dir>` runs either script against
another instance folder.

`tests/fake_github.py <port>` is the fake GitHub contents API the reporter tests use; point the
reporter at it by hand with `GATHERLANE_API=http://127.0.0.1:<port> GATHERLANE_TOKEN=x`.

If Playwright is installed outside this folder, point Node at it with
`NODE_PATH=/path/to/node_modules`. With Node 26, `playwright install` for 1.49 can hang while
unpacking the browser. Download the zip yourself and unpack it with the system `unzip`:

```sh
curl -fLo /tmp/hs.zip https://playwright.download.prss.microsoft.com/dbazure/download/playwright/builds/chromium/1148/chromium-headless-shell-mac-arm64.zip
D=~/Library/Caches/ms-playwright/chromium_headless_shell-1148
mkdir -p "$D" && unzip -q /tmp/hs.zip -d "$D" && touch "$D/INSTALLATION_COMPLETE"
```

Use the `-linux` or `-mac` zip instead of `-mac-arm64` on other machines.
