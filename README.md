# Gatherlane

An isometric office for your agent fleets. One floor per operation, one character per agent.
Every badge comes from a status file or from GitHub, and the inbox shows everything that needs you.
It is a static single-page app with no backend of its own.

```
app/                 the site (deploy this folder)
  index.html, styles.css, _headers
  instance/          this office's own fleet                         ← edit these
    config.js        repos to watch, agent roles and runbook links
    building.js      floors, rooms, furniture, characters
    sample.js        SAMPLE data shown when no token is set
  js/                the engine, the same for every office
    render.js        isometric renderer and mascots
    office.js        floors → SVG, status interpretation (stale, paused)
    data.js          read-only GitHub client (status branch, PRs, runs, room panels)
    audio.js         procedural lo-fi and office sounds (off by default)
    app.js           views, controls, inbox, cards
tools/gatherlane.py  reporter: agents write their status with it and honour the pause flag
schema/              JSON Schemas for status files and control/pause.json
examples/instance/   a neutral example fleet to start your own instance from
examples/            GitHub Actions workflow, cron, n8n and Claude Code snippets
tests/               reporter unit tests, Playwright smoke tests, the engine-is-generic check
docs/SETUP.md        hosting, tokens, populating status, what must keep running
```

## Live or sample, and how you can tell

| What you see | Where it comes from |
|---|---|
| **LIVE** pill, LIVE tags | GitHub API with your read-only tokens, read from this browser |
| **SAMPLE** pill, SAMPLE tags | `instance/sample.js`. Shown when no token is set, or when you tick "Show SAMPLE data" |
| `?` badge, "no status file" | live mode, but `status/<operation>/<agent>.json` does not exist yet |
| **stale** | the status file is older than twice its schedule interval (24 h if unscheduled) |
| ❚❚ | the agent's id is listed in `control/pause.json` |

Live and sample data are never mixed. Bobbing characters, lamps and the walking "you" avatar are
decoration and say nothing about status.

## Run locally

Open `app/index.html` in a browser (sample mode), or serve the folder:

```sh
python3 -m http.server -d app 8080
```

To start your own office, replace `app/instance/` with a copy of `examples/instance/` and edit
the three files there; `docs/SETUP.md` has the rest. Nothing outside `app/instance/` should name
your fleet: `tests/test_engine_is_generic.py` fails if it does.

## Controls

1–5 floors · I inbox · F focus (dim everything that is not running or waiting) · R / Shift+R rotate ·
+ / − / 0 zoom and fit · scroll or right-drag to pan, Ctrl+scroll or pinch to zoom · WASD or
arrows walk inside a floor, Enter talks to the nearest agent · Esc closes a card, then backs out to
the building. On a phone it collapses to the inbox and one floor at a time.

See [docs/SETUP.md](docs/SETUP.md) for hosting and for wiring agents to report.

## Plans

[docs/roadmap.md](docs/roadmap.md) has the milestones toward an open-source release and a hosted
version.

## Licence

Apache-2.0, see [LICENSE](LICENSE). Contributions are welcome: [CONTRIBUTING.md](CONTRIBUTING.md).
Security issues: [SECURITY.md](SECURITY.md).
