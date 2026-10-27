#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""gatherlane.py — write agent status files for the Gatherlane office, and honour the pause flag.

Standard library only. Works in GitHub Actions, cron on any machine, n8n "Execute Command", or by hand.

Environment (each may also be set as `export NAME=value` in the env file, see GATHERLANE_ENV)
  GATHERLANE_TOKEN   fine-grained token for the Gatherlane repo only, Contents: read and write
  GATHERLANE_REPO    owner/repo that holds the status branch (required)
  GATHERLANE_BRANCH  default status
  GATHERLANE_TZ      IANA time zone for timestamps and --cron, default UTC
  GATHERLANE_OPS     id prefixes that share an operation, e.g. "web=acme,orchestrator=shared".
                     Otherwise an id's first part is its operation ("acme/support" -> acme), and an
                     id without a slash goes to "shared".
  GATHERLANE_ENV     file read for any of the above not already set, default ~/.config/gatherlane/env

Commands
  run          --agent ID [--cron EXPR] [--runbook URL] [--workflow URL] -- COMMAND ...
               check pause → report running → run COMMAND → report idle/sleeping/failed/waiting.
               COMMAND may write JSON to the file named in $GATHERLANE_OUT to ask for a human:
                 {"needs_human_kind": "escalation", "reason": "...", "issue": "https://..."}
  report       --agent ID --status STATUS [fields...]   write/merge one status file; an id with no
                                                        file yet needs --new (catches mistyped ids)
  check-pause  --agent ID                               exit 3 if paused, 0 otherwise
  validate     FILE ...                                 check local status files against the contract
  init-branch                                           create the status branch with control/pause.json
"""
import argparse, base64, datetime as dt, json, os, shlex, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request
from zoneinfo import ZoneInfo

SCHEMA = "gatherlane.agent-status/v1"
STATUSES = ["idle", "running", "waiting", "blocked", "failed", "sleeping", "not_deployed"]
KINDS = ["escalation", "approval", "review", "failed_run"]
FALLBACK_OP = "shared"
API = os.environ.get("GATHERLANE_API", "https://api.github.com")


def env(k, d=None):
    return os.environ.get(k) or d


def load_env_file():
    """Fill unset GATHERLANE_* variables from `export NAME=value` lines, so a session that never
    sourced the file can still report."""
    path = os.path.expanduser(env("GATHERLANE_ENV", "~/.config/gatherlane/env"))
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for line in lines:
        try:
            words = shlex.split(line, comments=True)
        except ValueError:
            continue
        if words[:1] == ["export"]:
            words = words[1:]
        if len(words) != 1 or "=" not in words[0]:
            continue
        k, v = words[0].split("=", 1)
        if k.startswith("GATHERLANE_") and not os.environ.get(k):
            os.environ[k] = v


def tz_name():
    return env("GATHERLANE_TZ", "UTC")


def tz():
    try:
        return ZoneInfo(tz_name())
    except Exception:
        sys.exit(f"GATHERLANE_TZ={tz_name()!r} is not an IANA time zone name, such as Asia/Jakarta or UTC")


def now_iso():
    return dt.datetime.now(tz()).replace(microsecond=0).isoformat()


def ops_map():
    out = {}
    for pair in (env("GATHERLANE_OPS", "") or "").split(","):
        if "=" in pair:
            k, v = (s.strip() for s in pair.split("=", 1))
            if k and v:
                out[k] = v
    return out


def operation_of(agent):
    head = agent.split("/")[0]
    ops = ops_map()
    if head in ops:
        return ops[head]
    if head.split("-")[0] in ops:
        return ops[head.split("-")[0]]
    return head if "/" in agent else FALLBACK_OP


def path_of(agent):
    op = operation_of(agent)
    parts = agent.split("/")
    name = parts[1] if len(parts) == 2 and parts[0] == op else agent.replace("/", "-")
    return f"status/{op}/{name}.json"


def reported_by():
    if env("GITHUB_ACTIONS"):
        return f"github-actions:{env('GITHUB_REPOSITORY')}/{env('GITHUB_WORKFLOW')}#{env('GITHUB_RUN_ID')}"
    return f"{env('USER', 'agent')}@{socket.gethostname()}"


def run_url():
    if env("GITHUB_ACTIONS"):
        return f"{env('GITHUB_SERVER_URL', 'https://github.com')}/{env('GITHUB_REPOSITORY')}/actions/runs/{env('GITHUB_RUN_ID')}"
    return None


# ---------- GitHub contents API ----------
def gh(method, path, body=None, token=None):
    token = token or env("GATHERLANE_TOKEN")
    if not token:
        sys.exit("GATHERLANE_TOKEN is not set")
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "gatherlane-reporter"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"message": raw.decode(errors="replace")}


def repo():
    r = env("GATHERLANE_REPO")
    if not r or r.count("/") != 1:
        sys.exit("GATHERLANE_REPO is not set: give the owner/repo that holds your status branch")
    return r


def branch():
    return env("GATHERLANE_BRANCH", "status")


def read_file(path):
    code, d = gh("GET", f"/repos/{repo()}/contents/{path}?ref={branch()}")
    if code == 404:
        return None, None
    if code != 200:
        sys.exit(f"read {path}: {code} {d.get('message')}")
    return json.loads(base64.b64decode(d["content"]).decode()), d["sha"]


def write_file(path, obj, message):
    for attempt in range(6):
        _, sha = read_file(path)
        body = {"message": message, "branch": branch(),
                "content": base64.b64encode((json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode()).decode()}
        if sha:
            body["sha"] = sha
        code, d = gh("PUT", f"/repos/{repo()}/contents/{path}", body)
        if code in (200, 201):
            return
        if code in (409, 422) and attempt < 5:  # someone else wrote this branch; retry with fresh sha
            time.sleep(1 + attempt * 2)
            continue
        sys.exit(f"write {path}: {code} {d.get('message')}")


# ---------- cron: next run (minute, hour, dom, month, dow; *, */n, a-b, a,b) ----------
def _field(spec, lo, hi):
    out = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/"); step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = map(int, part.split("-"))
        else:
            a = b = int(part)
        out.update(range(a, b + 1, step))
    return out


def next_run(cron, after=None, zone=None):
    try:
        m, h, dom, mon, dow = cron.split()
        M, H, DOM, MON = _field(m, 0, 59), _field(h, 0, 23), _field(dom, 1, 31), _field(mon, 1, 12)
        DOW = {d % 7 for d in _field(dow, 0, 7)}
    except Exception:
        return None
    t = (after or dt.datetime.now(zone or tz())).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    for _ in range(60 * 24 * 32):
        if t.minute in M and t.hour in H and t.month in MON and t.day in DOM and (t.isoweekday() % 7) in DOW:
            return t.isoformat()
        t += dt.timedelta(minutes=1)
    return None


# ---------- commands ----------
def build_record(prev, a):
    rec = dict(prev or {})
    rec.update({"schema": SCHEMA, "agent": a.agent, "operation": a.operation or rec.get("operation") or operation_of(a.agent)})
    if a.pod: rec["pod"] = a.pod
    rec["status"] = a.status
    if a.task is not None:
        rec["current_task"] = {"title": a.task, "url": a.task_url} if a.task else None
    if a.last_run_at: rec["last_run_at"] = now_iso() if a.last_run_at == "now" else a.last_run_at
    if a.last_result: rec["last_result"] = a.last_result
    if a.last_result_url: rec["last_result_url"] = a.last_result_url
    if a.cron:
        rec["schedule"] = {"cron": a.cron, "tz": tz_name()}
    sched = (rec.get("schedule") or {}).get("cron")
    if a.next_run_at:
        rec["next_run_at"] = a.next_run_at
    elif sched:
        rec["next_run_at"] = next_run(sched)
    if a.needs_human_kind:
        rec.update(needs_human=True, needs_human_kind=a.needs_human_kind, needs_human_reason=(a.reason or "")[:200])
    elif a.status != "waiting":
        rec.update(needs_human=False, needs_human_kind=None, needs_human_reason=a.reason[:200] if a.reason else None)
    if a.status == "waiting" and not rec.get("needs_human"):
        sys.exit("status waiting needs --needs-human-kind and --reason")
    links = dict(rec.get("links") or {})
    for k in ("runbook", "issue", "pr", "workflow"):
        v = getattr(a, k)
        if v is not None:
            links[k] = v or None
    rec["links"] = links
    rec["updated_at"] = now_iso()
    rec["reported_by"] = reported_by()
    rec.setdefault("needs_human", False)
    return rec


def unknown_agent(agent, path):
    return (f"{agent}: no status file at {path} on {repo()}@{branch()}. If the id is right and this is a "
            f"new agent, pass --new (for example with --status not_deployed); otherwise check the id.")


def cmd_report(a):
    path = path_of(a.agent)
    prev, _ = read_file(path)
    if prev is None and not a.new:
        print(unknown_agent(a.agent, path), file=sys.stderr)
        sys.exit(4)
    rec = build_record(prev, a)
    errs = validate_obj(rec)
    if errs:
        sys.exit(f"refusing to write invalid record: {errs}")
    if a.dry_run:
        print(path); print(json.dumps(rec, indent=2)); return
    write_file(path, rec, f"status: {a.agent} {a.status}")
    print(f"{path}: {a.status}")


def paused(agent):
    ctl, _ = read_file("control/pause.json")
    return ((ctl or {}).get("paused") or {}).get(agent)


def cmd_check_pause(a):
    p = paused(a.agent)
    if p:
        print(f"{a.agent} is paused since {p.get('since')} by {p.get('by')}: {p.get('reason') or ''}")
        sys.exit(3)
    print(f"{a.agent} is not paused")


def ns(**kw):
    base = dict(agent=None, operation=None, pod=None, status=None, task=None, task_url=None, last_run_at=None,
                last_result=None, last_result_url=None, next_run_at=None, cron=None, needs_human_kind=None,
                reason=None, runbook=None, issue=None, pr=None, workflow=None, dry_run=False, new=True)
    base.update(kw)
    return argparse.Namespace(**base)


def cmd_run(a):
    cmd = a.command[1:] if a.command and a.command[0] == "--" else a.command
    if not cmd:
        sys.exit("run: give the agent command after --")
    common = dict(agent=a.agent, cron=a.cron, runbook=a.runbook, workflow=a.workflow)
    out = tempfile.NamedTemporaryFile(prefix="gatherlane-", suffix=".json", delete=False).name
    open(out, "w").close()
    cmd_env = {**os.environ, "GATHERLANE_OUT": out, "GATHERLANE_AGENT": a.agent}
    if read_file(path_of(a.agent))[0] is None:  # a mistyped id must not stop the agent's own work
        print(unknown_agent(a.agent, path_of(a.agent)) + " Running the command without reporting.", file=sys.stderr)
        sys.exit(subprocess.call(cmd, env=cmd_env))
    p = paused(a.agent)
    if p:
        print(f"paused: {p.get('reason') or 'no reason'}; not running")
        prev, _ = read_file(path_of(a.agent))
        keep = (prev or {}).get("status") or "idle"
        keep = keep if keep in ("idle", "sleeping", "waiting", "blocked", "failed") else "idle"
        if keep == "waiting":  # keep the human item as it was
            return
        cmd_report(ns(status=keep, **common))
        return
    cmd_report(ns(status="running", last_run_at="now", task=a.task, **common))
    code = subprocess.call(cmd, env=cmd_env)
    ask = {}
    try:
        txt = open(out).read().strip()
        ask = json.loads(txt) if txt else {}
    except Exception as e:
        print(f"ignoring unreadable $GATHERLANE_OUT: {e}")
    url = run_url()
    if code != 0:
        cmd_report(ns(status="failed", last_result="failure", last_result_url=url, task="", needs_human_kind="failed_run",
                      reason=ask.get("reason") or f"exit code {code}", **common))
        sys.exit(code)
    if ask.get("needs_human_kind"):
        cmd_report(ns(status="waiting", last_result="success", last_result_url=url, task=ask.get("task", ""),
                      needs_human_kind=ask["needs_human_kind"], reason=ask.get("reason"), issue=ask.get("issue"),
                      pr=ask.get("pr"), **common))
        return
    status = "idle"
    if a.cron:
        nxt = next_run(a.cron)
        if nxt and (dt.datetime.fromisoformat(nxt) - dt.datetime.now(tz())).total_seconds() > 3600:
            status = "sleeping"
    cmd_report(ns(status=status, last_result="success", last_result_url=url, task="", **common))


def validate_obj(o):
    errs = []
    if o.get("schema") != SCHEMA: errs.append("schema")
    if not o.get("agent"): errs.append("agent")
    if o.get("status") not in STATUSES: errs.append("status")
    if not isinstance(o.get("needs_human"), bool): errs.append("needs_human")
    if o.get("needs_human_kind") not in KINDS + [None]: errs.append("needs_human_kind")
    try:
        dt.datetime.fromisoformat(o.get("updated_at", ""))
    except Exception:
        errs.append("updated_at")
    if o.get("needs_human_reason") and len(o["needs_human_reason"]) > 200: errs.append("needs_human_reason too long")
    return errs


def cmd_validate(a):
    bad = 0
    for f in a.files:
        try:
            o = json.load(open(f))
        except Exception as e:
            print(f"{f}: invalid JSON ({e})"); bad += 1; continue
        if f.endswith("control/pause.json"):
            if not isinstance(o.get("paused"), dict):
                print(f"{f}: 'paused' must be an object"); bad += 1
            continue
        errs = validate_obj(o)
        if errs:
            print(f"{f}: {', '.join(errs)}"); bad += 1
    print(f"{len(a.files) - bad}/{len(a.files)} ok")
    sys.exit(1 if bad else 0)


def cmd_init_branch(a):
    code, info = gh("GET", f"/repos/{repo()}")
    if code != 200:
        sys.exit(f"{repo()}: {code} {info.get('message')}")
    code, _ = gh("GET", f"/repos/{repo()}/git/ref/heads/{branch()}")
    if code == 404:
        code, ref = gh("GET", f"/repos/{repo()}/git/ref/heads/{info['default_branch']}")
        code, d = gh("POST", f"/repos/{repo()}/git/refs", {"ref": f"refs/heads/{branch()}", "sha": ref["object"]["sha"]})
        if code != 201:
            sys.exit(f"create branch: {code} {d.get('message')}")
        print(f"created branch {branch()}")
    if read_file("control/pause.json")[0] is None:
        write_file("control/pause.json", {"schema": "gatherlane.control/v1", "paused": {}}, "control: create pause.json")
        print("created control/pause.json")
    print("ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--agent", required=True); r.add_argument("--status", required=True, choices=STATUSES)
    r.add_argument("--operation", help="override the operation worked out from the id"); r.add_argument("--pod")
    r.add_argument("--task", help="current task title; empty string clears it"); r.add_argument("--task-url")
    r.add_argument("--last-run-at", help="ISO time or 'now'"); r.add_argument("--last-result", choices=["success", "failure", "cancelled", "skipped"])
    r.add_argument("--last-result-url"); r.add_argument("--next-run-at"); r.add_argument("--cron")
    r.add_argument("--needs-human-kind", choices=KINDS); r.add_argument("--reason")
    for k in ("runbook", "issue", "pr", "workflow"):
        r.add_argument(f"--{k}", help="URL; empty string clears it")
    r.add_argument("--new", action="store_true", help="allow an id that has no status file yet")
    r.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("check-pause"); c.add_argument("--agent", required=True)
    u = sub.add_parser("run")
    u.add_argument("--agent", required=True); u.add_argument("--cron"); u.add_argument("--task")
    u.add_argument("--runbook"); u.add_argument("--workflow"); u.add_argument("command", nargs=argparse.REMAINDER)
    v = sub.add_parser("validate"); v.add_argument("files", nargs="+")
    sub.add_parser("init-branch")
    a = ap.parse_args()
    load_env_file()
    {"report": cmd_report, "check-pause": cmd_check_pause, "run": cmd_run, "validate": cmd_validate,
     "init-branch": cmd_init_branch}[a.cmd](a)


if __name__ == "__main__":
    main()
