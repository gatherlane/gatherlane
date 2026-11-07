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

Cloudflare Access is a precondition here, not an option. Pages serves everything in `app/` to
anyone who can reach the address, and that includes `app/instance/`: `config.js` names every repo
you watch, your agents and their owners, and your runbook links, and `building.js` and
`sample.js` carry the same names. Live GitHub data is not exposed this way, because each viewer's
browser fetches it with that viewer's own tokens, but the instance files are. So the steps below
put Access in front of the project before the office is first deployed, and never let a custom
domain serve the office before Access covers it. Do them in this order.

Every deployment also has its own address, `<hash>.<project>.pages.dev`, which keeps serving that
deployment's files, `app/instance/` included, after newer deployments replace it. Cloudflare
documents these addresses for preview deployments
([Preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/#preview-aliases));
its docs do not say the same of production deployments, so this guide assumes they have one too
and checks it. The Access application for `*.<project>.pages.dev` below is what covers these
addresses, so keep it even though preview deployments are off.

The Cloudflare steps follow Cloudflare's documentation as read on 2026-10-29. They have not been
run end to end on a live account; where a step goes beyond those docs, it says so.

**Pages, with a placeholder first**
1. Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git → choose
   `<owner>/gatherlane`. If it is not listed, give the Cloudflare Pages GitHub app access to that
   repo in the owner's settings.
2. Production branch `main`. Framework preset: None. For now, do not build the office: set the
   build command to `mkdir -p placeholder && echo ok > placeholder/index.html` and the build
   output directory to `placeholder`. Creating the project deploys straight away, and this way
   the first deployment holds one page that says `ok` and none of `app/instance/`. Note the
   project's address, `<project>.pages.dev`. Keep this placeholder deployment: the custom domain
   steps and "Is my office public right now?" roll production back to it.
3. Settings → Builds & deployments: set preview deployments to **None**, so the `status` branch
   never builds.

**Access** (only your email can open it). These are Cloudflare's steps for putting Access on a
`pages.dev` domain
([Known issues: Enable Access on your `*.pages.dev` domain](https://developers.cloudflare.com/pages/platform/known-issues/#enable-access-on-your-pagesdev-domain)).
1. Workers & Pages → your project → Settings → General → **Enable access policy**. This creates
   an Access application for `*.<project>.pages.dev`, which covers the per-deployment addresses
   but not `<project>.pages.dev` itself.
2. Select **Manage** on that policy. In Zero Trust, under Access → Applications, select the
   project's application → **Configure**. Under **Public hostname**, delete the `*` from the
   **Subdomain** field and select **Save** (change the **Application name** if saving gives an
   error). That application now covers `<project>.pages.dev`.
3. Back in the project, Settings → General → **Enable access policy** again. Zero Trust now lists
   two applications for the project, one for `<project>.pages.dev` and one for
   `*.<project>.pages.dev`. Keep both.
4. Open each application's policy and make sure it is Action Allow, Include Emails with your
   address (or the people you choose), never Everyone, and never a Bypass action, which lets
   anyone through without signing in. Cloudflare's docs say only that the policy
   restricts viewing to your Cloudflare account, not exactly what it contains, so check it. For
   identity, the default one-time PIN by email works; Google login is nicer on the phone.
5. In a private window, open `https://<project>.pages.dev/`, then the placeholder's own address
   (Deployments → the placeholder deployment → its `<hash>.<project>.pages.dev` address). Each
   should give the Access sign-in, not the page that says `ok`. If either shows `ok`, stop: do
   not deploy the office. Fix the Access applications (steps 1 to 4) and check again.

**Then deploy the office**
1. Settings → Builds & deployments → Build configuration: clear the build command and set the
   build output directory to `app`.
2. Push to `main` to deploy it (`git commit --allow-empty -m "Deploy" && git push` if there is
   nothing new).
3. In a private window, open `https://<project>.pages.dev/instance/config.js`, then the same path
   on the new deployment's own `<hash>.<project>.pages.dev` address (Deployments → the latest
   deployment). Each should give the Access sign-in, not the file. If you see the file, follow
   "Is my office public right now?" below.

`app/_headers` is picked up by Pages. It sets a Content-Security-Policy that only allows the page
to talk to `api.github.com`, and blocks framing.

**Custom domain** (optional, for example `office.example.com`). Cloudflare cannot add a custom
domain that already has an Access policy on it, because the certificate check needs
`/.well-known/acme-challenge/` on that hostname to get through
([Known issues: Custom Domains](https://developers.cloudflare.com/pages/platform/known-issues/#custom-domains)).
So the domain is added while production serves the placeholder, and the office comes back only
once Access covers the domain.
1. Settings → Builds & deployments → Configure Production deployments: untick **Enable automatic
   production branch deployments** and save, so no push puts the office back in production
   halfway through
   ([Branch deployment controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/)).
2. Deployments → All deployments → the placeholder deployment → ⋯ → **Rollback to this
   deployment**. Production changes to the placeholder at once
   ([Rollbacks](https://developers.cloudflare.com/pages/configuration/rollbacks/)).
3. Custom domains → **Set up a domain** → `office.example.com` → Continue, and finish the DNS step
   it asks for
   ([Custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)). Wait
   until Cloudflare shows the domain as active.
4. Put the domain behind Access (Known issues, steps 10 to 13): Zero Trust → Access controls →
   Applications → **Create new application** → **Self-hosted and private** → **Add public
   hostname**. The Domain list offers the zones on your Cloudflare account, not hostnames, so for
   `office.example.com` set Subdomain `office`, Domain `example.com`, and leave Path empty
   ([Publish a self-hosted application](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)).
   Add a policy with Action Allow, Include Emails, your address, as above, then **Create**. If
   `example.com` is not in the Domain list, its DNS is not a zone on this Cloudflare account (for
   example, the domain's CNAME is at another DNS provider), and Access cannot cover the domain:
   stop here and follow "If the domain cannot go behind Access" below. If the screen also offers
   **Switch to custom input**, Cloudflare documents that option for Cloudflare for SaaS custom
   hostnames and does not say whether it covers a Pages custom domain, so do not rely on it: step
   5 is what shows whether the domain is covered.
5. In a private window, open `https://office.example.com/`. You should get the Access sign-in, not
   the page that says `ok`. If you see `ok`, stop: do not go on to step 6. Fix the domain's Access
   application and check again, or follow "If the domain cannot go behind Access" below.
6. Deployments → the latest office deployment → ⋯ → **Rollback to this deployment**, then tick
   **Enable automatic production branch deployments** again and save.
7. In a private window, open `https://office.example.com/instance/config.js`. You should get the
   Access sign-in, not the file. If you see the file, stop and roll back to the placeholder at
   once (steps 2 and 1: roll back, then untick automatic deployments), then fix the domain's
   Access application and repeat from step 5, or follow "If the domain cannot go behind Access".

**If the domain cannot go behind Access** (custom domain step 4 sent you here), production is
still the placeholder and automatic production deployments are still off. Remove the domain the
way Cloudflare documents
([Custom domains: Delete a custom domain](https://developers.cloudflare.com/pages/configuration/custom-domains/#delete-a-custom-domain)):
first delete the project's CNAME record for the domain in the DNS records where you created it,
then in the project, Custom domains → ⋯ → **Remove domain**. Once Custom domains no longer lists
it, roll forward: Deployments → the latest office deployment → ⋯ → **Rollback to this
deployment**, then tick **Enable automatic production branch deployments** again and save. The
office is then only on the `pages.dev` addresses, which Access covers. Do not roll forward while
the project still lists a custom domain that has no Access application of its own.

**Certificate renewal.** Cloudflare's Known issues tie Pages custom domains to Cloudflare for
SaaS (Advanced Certificates "cannot be used with Cloudflare Pages due to Cloudflare for SaaS's
certificate prioritization"). Cloudflare for SaaS custom hostname certificates last 90 days, can
be renewed from 30 days before they expire, and are renewed automatically by HTTP validation
([Cloudflare for SaaS: Renew](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/security/certificate-management/issue-and-validate/renew-certificates/)).
Debugging Pages says HTTP validation cannot be completed when Access is in the way
([Blocked HTTP validation](https://developers.cloudflare.com/pages/configuration/debugging-pages/#blocked-http-validation)),
and the docs do not say whether a renewal is exempt. So the domain's certificate may fail to
renew, about every 60 days. That fails closed: browsers show a certificate error for the domain,
and nothing is exposed. Cloudflare's fix is to disable Access over the domain until it verifies.
Never do that while the office is in production, because it publishes `config.js` on the domain.
Instead, take the office out of production first and repeat the custom domain steps with the
domain already added: steps 1 and 2 (pause automatic deployments, roll back to the placeholder),
then delete only the domain's own Access application (not the two `pages.dev` ones), wait until
Custom domains shows the domain as active again, and then steps 4 to 7. This has not been run on a
live account.

**Is my office public right now?** Open a private window, so no Access session is reused, and go
to `https://<project>.pages.dev/instance/config.js`, then to the same path on each custom domain
and on the latest deployment's own `<hash>.<project>.pages.dev` address (Deployments → the latest
deployment). The Access sign-in means that address is protected. The text of `config.js`, with
your repo names in it, means anyone can read it. If so:
1. Take the office off the production addresses.
   - If the project has the placeholder deployment: Deployments → the placeholder deployment → ⋯ →
     **Rollback to this deployment**. It is instant, and undone the same way. Then untick
     automatic production deployments, as in custom domain step 1, so the next push does not
     bring the office back.
   - If it has no placeholder deployment: set the build command and output directory as in
     "Pages, with a placeholder first" step 2, and push to `main` while automatic production
     deployments are still on (an empty commit is enough), because with them off the push does
     not deploy. Wait for that deployment to finish, and check in a private window that each address where
     you saw the file no longer shows it. Only then untick automatic production deployments.

   Neither touches older deployments' own addresses, which still serve the office.
2. Add Access as above, covering `<project>.pages.dev`, `*.<project>.pages.dev` and each custom
   domain, and check every address again. If step 1 changed the build configuration, set it back
   now, as in "Then deploy the office" step 1 (clear the build command, build output directory
   `app`), or the next push replaces the office with the placeholder. Then roll forward
   (Deployments → the latest office deployment → ⋯ → **Rollback to this deployment**) and tick
   automatic production deployments back on.
3. Only as a last resort, delete the project: Settings → Delete project. It cannot be undone.
   Remove its custom domains first, CNAME record and then **Remove domain**, as above. Cloudflare
   notes that a project with over 100 deployments may not delete from the dashboard; delete
   deployments first with
   `npx wrangler pages deployment delete <DEPLOYMENT_ID> --project-name <PROJECT_NAME>`
   ([Known issues](https://developers.cloudflare.com/pages/platform/known-issues/#delete-a-project-with-a-high-number-of-deployments)).
   A deployment that still has an alias needs `--force`, and the latest deployment of a branch
   cannot be deleted
   ([Preview deployments: Delete preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/#delete-preview-deployments)).
   Then set it up again in the order above.

Turning off builds alone leaves the last deployment online.

A Docker or local office bound to `127.0.0.1` needs no Access: only your own machine can reach it.
See "Run it on your own machine with Docker" below.

Nothing else runs on Cloudflare. The page is static, and your browser calls GitHub directly.

## Run it on your own machine with Docker

The other option to step 2, when the office only has to open on the machine it runs on. It needs
Docker with Compose v2, and nothing on Cloudflare. In your clone:

```sh
docker compose up -d
```

then open <http://127.0.0.1:8080>. `compose.yaml` starts one nginx container that serves `app/`
read-only, with the same headers `app/_headers` gives Pages, so the Content-Security-Policy still
only lets the page talk to `api.github.com`. `docker compose ps` shows it as `healthy` once it
answers.

- **Tokens are per browser origin.** The browser keeps tokens for the address it loaded the page
  from, so `http://127.0.0.1:8080` does not see tokens saved on your Pages domain, on
  `localhost:8080`, or on another port. Paste them again in ⚙ Settings (step 3), and tick "Remember
  tokens on this device" if you want them kept.
- **Loopback only.** The port is published on `127.0.0.1`, never `0.0.0.0`. Nothing like
  Cloudflare Access sits in front of it, so on `0.0.0.0` anyone on the same network could open
  the office and read your fleet's names, repos and runbook links from `config.js`, and on Linux
  Docker's published ports bypass a host firewall such as ufw. To use another port, set
  `GATHERLANE_HTTP_PORT`, for example `GATHERLANE_HTTP_PORT=9090 docker compose up -d`; the address
  stays `127.0.0.1`. To reach it from another device, use Pages and Access instead. Compose also
  reads a `compose.override.yaml` next to `compose.yaml` on its own and adds its `ports` to this
  one, so an override with `"0.0.0.0:9090:8080"` would publish the office on your network as
  well. Do not keep one in the clone. `COMPOSE_FILE`, when set, replaces that default list
  instead: the files it names are the only ones read, and a file listed after `compose.yaml`
  adds its `ports` the same way. `docker compose config` shows the ports that will really be
  published.
- **Limits.** The container is capped at 0.25 CPU, 64 MiB of memory and 32 processes, with the
  `docker stats` figures behind them in the comment at the top of `compose.yaml`. To change them,
  edit `x-limits` there and run `docker compose up -d`.
- **Logs and usage.** `docker compose logs -f` shows the access log (the healthcheck is left out)
  and nginx errors, capped at 3 files of 10 MB. `docker stats` shows CPU, memory and processes
  against the limits.
- **Updating.** `git pull` is enough: `app/` is mounted, not copied, so reload the page and the
  new version is there, with no rebuild. If the pull changed `compose.yaml` or
  `deploy/nginx.conf`, run `docker compose up -d --force-recreate` as well.
- **Stopping.** `docker compose down`. Until then it restarts with Docker.
- **On Linux, `app/` must be readable by uid 101**, the user nginx runs as in the container. With a
  restrictive umask (027 or 077) a fresh clone is not, and every page is a 404. Fix it with
  `chmod -R a+rX app` in the clone. Docker Desktop on a Mac does not need this.

The container runs as an unprivileged user with a read-only filesystem, no Linux capabilities
and `no-new-privileges`. It does not serve `_headers` itself, dotfiles, directory listings, or any
path with a character outside ASCII. The bind mount on a Mac ignores case, Unicode case folds
included, so `/_HEADERS` and `/_header%C5%BF` (a long s) open `_headers` there: the first is
refused by a case-insensitive rule, the second by the non-ASCII one, and no file in `app/` has a
non-ASCII name.

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
error code. A repo whose owner has no token is not read at all, even when it is public: its row
says `no token for <owner>`, and a room panel lists it under "Could not read". Settings also lists
agents whose status files the app read but that are on no floor (add them to `agents` in
`config.js`, or to `building.js` if you draw the building by hand), and agents on a floor with no
status file yet (register one with `gatherlane report --agent <id> --new --status not_deployed`,
or wait for its first run).

A token stored under the owner `*` in the `gl.tokens` entry of the browser's storage is used for
any owner without its own token. Settings has no field for it, and Save rewrites `gl.tokens` from
the fields it shows, so a `*` token set by hand is gone after the next Save.

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
- **Docker, if you run it on your own machine.** The office is only there while Docker and the
  container are running. On a Mac that means Docker Desktop, which starts at login only when
  "Start Docker Desktop when you sign in" is on in its settings; the container then comes back
  with Docker on its own (`restart: unless-stopped`). `docker compose ps` shows whether it is up
  and `healthy`.
- **Nothing else.** Beyond that container, if you chose it, Gatherlane has no server, database or
  poller. While the page is open it refreshes status and PR labels every 2 minutes and workflow
  runs every 5. Unchanged responses return 304 and do not count against GitHub's 5,000 requests
  per hour.

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

`tests/test_docker.py` (part of `test:py`) fails if `deploy/nginx.conf` and `app/_headers` send
different headers, and checks the resolved `compose.yaml` where Docker is installed. With the
container running, `GATHERLANE_DOCKER_URL=http://127.0.0.1:8080 python3 -m unittest
tests.test_docker` also checks what it actually serves; CI does this in its `docker` job.

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
