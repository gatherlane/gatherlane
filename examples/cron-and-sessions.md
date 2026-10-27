# Reporting from cron, n8n and Claude Code sessions

All three use the same script, `tools/gatherlane.py`. Put the writer token where only that
machine can read it, and the reporter where the snippets below expect it (`<owner>` is the owner
of your Gatherlane repo):

```sh
mkdir -p ~/.config/gatherlane && chmod 700 ~/.config/gatherlane
printf 'export GATHERLANE_TOKEN=%s\n' 'github_pat_...' > ~/.config/gatherlane/env   # owner <owner>, repo gatherlane, Contents: read and write
printf 'export GATHERLANE_REPO=%s\nexport GATHERLANE_TZ=%s\n' '<owner>/gatherlane' 'UTC' >> ~/.config/gatherlane/env
chmod 600 ~/.config/gatherlane/env
git clone git@github.com:<owner>/gatherlane.git ~/gatherlane   # or copy tools/gatherlane.py
```

The reporter reads that file itself, so cron lines and agent sessions do not have to source it.

Agent ids are `<operation>/<agent>`, as in `app/instance/config.js`; the first part is the operation.
When several prefixes share an operation, add `export GATHERLANE_OPS=prefix=operation,...` to the
env file and the same prefixes to `agentPrefixes` in `config.js`.

## Cron on an agent host

`crontab -e` on the host. Cron fires in the system time zone and the reporter reads `--cron` in
`GATHERLANE_TZ`, so keep the two the same (`timedatectl` shows the system zone).

```cron
# finance-agent: daily 06:00
0 6 * * *    . ~/.config/gatherlane/env && python3 ~/gatherlane/tools/gatherlane.py run --agent <operation>/finance-agent --cron "0 6 * * *" -- /opt/agent-runner/run.sh finance-agent >> ~/logs/finance-agent.log 2>&1
# support-agent: every 15 minutes
*/15 * * * * . ~/.config/gatherlane/env && python3 ~/gatherlane/tools/gatherlane.py run --agent <operation>/support-agent --cron "*/15 * * * *" -- /opt/agent-runner/run.sh support-agent >> ~/logs/support-agent.log 2>&1
```

If the agent is started over HTTP (for example `POST /agents/{name}/run`), wrap the curl call
instead of the script. A runner's own kill switch still applies; `control/pause.json` is the
switch you can flip from your phone.

## n8n

Use an **Execute Command** node at the start and end of each workflow:

```sh
python3 /data/gatherlane.py report --agent <operation>/<agent> --status running --last-run-at now
python3 /data/gatherlane.py report --agent <operation>/<agent> --status idle --last-result success
python3 /data/gatherlane.py report --agent <operation>/<agent> --status waiting --needs-human-kind escalation --reason "Order complaint needs owner"
```

## Claude Code subagents and orchestrator sessions

These agents run when you start them, not on a schedule, so they report from inside the session.
Append this section to the end of each `.claude/agents/<agent>.md`, with that agent's id in place
of `<id>`. Leave the rest of the file as it is.

```md
## Gatherlane status
These reports are required on every run, including a run that stops early. Report only what
actually happened. If a report command fails (for example, the token file is missing), say so in
your final message and carry on; never retry it in a loop.

Before anything else, run:
`python3 ~/gatherlane/tools/gatherlane.py check-pause --agent <id>`
Exit code 3 means the maintainer paused you: stop, change nothing, and say so in your final message.

At the start, run:
`python3 ~/gatherlane/tools/gatherlane.py report --agent <id> --status running --last-run-at now --task "#NN <issue title>" --task-url <issue url>`
At the end, run one of:
`... report --agent <id> --status idle --last-result success --task "" --pr <pr url>`
`... report --agent <id> --status blocked --reason "<one line>"`
`... report --agent <id> --status waiting --needs-human-kind review --reason "<one line>" --pr <pr url>`
```

If the agent file has a Rules list, add one bullet to it so the agent treats reporting as a rule:

```md
- **Report to Gatherlane on every run**, as "Gatherlane status" below describes.
```

A line in the repo's `CLAUDE.md` saying what Gatherlane is, and where the reporter and its token
live, helps the main session as well.

An agent whose job ends in a file for you to read reports `waiting` at that point. For example,
an agent that writes a report to `reports/DATE.md` runs, after writing it:
`... report --agent <id> --status waiting --needs-human-kind review --reason "New report ready" --task "reports/DATE.md"`

PRs labelled `review:approved` or `review:needs-maintainer` reach the inbox directly from GitHub,
so a reviewer agent does not need to report its verdicts.

Orchestrator sessions report `running` at the start of a cycle and `idle` at the end, as
`orchestrator-1`, `orchestrator-<n>`.

## Marking agents that are not deployed yet

Nothing in the office assumes an agent's state. To show a drafted-but-not-running agent as
"not deployed" instead of "no data", say so once. This marks every agent in `app/instance/config.js`;
edit the list first if some are already running:

```sh
. ~/.config/gatherlane/env
node -e "require('./app/instance/config.js'); console.log(Object.keys(GATHERLANE_CONFIG.agents).join('\n'))" > /tmp/agents.txt
while read -r a; do
  python3 ~/gatherlane/tools/gatherlane.py report --agent "$a" --status not_deployed --new
done < /tmp/agents.txt
```

This is the one place where you, not a runner, state a status. An agent's own first report
replaces it.

`--new` is needed here because the reporter refuses an id that has no status file yet: that is
how a mistyped id in a runbook gets caught instead of writing a file the office never shows
(`report` exits 4; `run` warns and still runs the command, without reporting). So a new agent
is always registered this way, once, before its runbook reports.
