# SPDX-License-Identifier: Apache-2.0
# Tests for tools/gatherlane.py: python3 -m unittest discover -s tests
# Standard library only. The CLI tests run the reporter against tests/fake_github.py.
import datetime as dt, importlib.util, json, os, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "gatherlane.py")
spec = importlib.util.spec_from_file_location("gatherlane", TOOL)
gl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gl)


class EnvCase(unittest.TestCase):
    """Runs each test with only the GATHERLANE_* variables it sets."""
    def setUp(self):
        self.saved = {k: v for k, v in os.environ.items() if k.startswith("GATHERLANE_")}
        for k in self.saved:
            del os.environ[k]
        os.environ["GATHERLANE_ENV"] = os.path.join(tempfile.gettempdir(), "gatherlane-no-such-env-file")

    def tearDown(self):
        for k in [k for k in os.environ if k.startswith("GATHERLANE_")]:
            del os.environ[k]
        os.environ.update(self.saved)


class OperationMapping(EnvCase):
    def test_first_part_is_the_operation(self):
        self.assertEqual(gl.operation_of("acme/support"), "acme")
        self.assertEqual(gl.path_of("acme/support"), "status/acme/support.json")

    def test_id_without_slash_goes_to_shared(self):
        self.assertEqual(gl.operation_of("orchestrator-1"), "shared")
        self.assertEqual(gl.path_of("orchestrator-1"), "status/shared/orchestrator-1.json")

    def test_ops_map_groups_prefixes(self):
        os.environ["GATHERLANE_OPS"] = "web=oss, api=oss,orchestrator=shared,broken,=x"
        self.assertEqual(gl.ops_map(), {"web": "oss", "api": "oss", "orchestrator": "shared"})
        self.assertEqual(gl.path_of("web/implementer"), "status/oss/web-implementer.json")
        self.assertEqual(gl.path_of("orchestrator-9"), "status/shared/orchestrator-9.json")

    def test_explicit_operation_part_keeps_short_name(self):
        os.environ["GATHERLANE_OPS"] = "acme=acme"
        self.assertEqual(gl.path_of("acme/support"), "status/acme/support.json")


class EnvFile(EnvCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        f.write(text); f.close()
        self.addCleanup(os.unlink, f.name)
        os.environ["GATHERLANE_ENV"] = f.name

    def test_reads_export_lines_quotes_and_comments(self):
        self.write("# comment\nexport GATHERLANE_TOKEN='t 1'\nGATHERLANE_REPO=o/r  # trailing\n"
                   "export OTHER=x\nnot a line\nexport GATHERLANE_TZ=\"Asia/Jakarta\"\n")
        gl.load_env_file()
        self.assertEqual(os.environ["GATHERLANE_TOKEN"], "t 1")
        self.assertEqual(os.environ["GATHERLANE_REPO"], "o/r")
        self.assertEqual(os.environ["GATHERLANE_TZ"], "Asia/Jakarta")
        self.assertNotIn("OTHER", os.environ)

    def test_does_not_override_the_environment(self):
        os.environ["GATHERLANE_REPO"] = "env/wins"
        self.write("export GATHERLANE_REPO=file/loses\n")
        gl.load_env_file()
        self.assertEqual(os.environ["GATHERLANE_REPO"], "env/wins")

    def test_missing_file_is_fine(self):
        gl.load_env_file()
        self.assertNotIn("GATHERLANE_REPO", os.environ)

    def test_bad_time_zone_exits(self):
        os.environ["GATHERLANE_TZ"] = "Mars/Base"
        with self.assertRaises(SystemExit):
            gl.tz()


class Cron(unittest.TestCase):
    Z = ZoneInfo("Asia/Jakarta")

    def at(self, *a):
        return dt.datetime(*a, tzinfo=self.Z)

    def test_every_fifteen_minutes(self):
        self.assertEqual(gl.next_run("*/15 * * * *", self.at(2026, 10, 27, 7, 16), self.Z), "2026-10-27T07:30:00+07:00")

    def test_weekly_monday(self):  # 2026-10-27 is a Tuesday
        self.assertEqual(gl.next_run("0 8 * * 1", self.at(2026, 10, 27, 9, 0), self.Z), "2026-11-02T08:00:00+07:00")

    def test_sunday_as_7(self):
        self.assertEqual(gl.next_run("0 6 * * 7", self.at(2026, 10, 27, 9, 0), self.Z), "2026-11-01T06:00:00+07:00")

    def test_ranges_and_lists(self):
        self.assertEqual(gl.next_run("30 8-10,20 * * *", self.at(2026, 10, 27, 10, 30), self.Z), "2026-10-27T20:30:00+07:00")

    def test_bad_expression(self):
        self.assertIsNone(gl.next_run("not a cron"))


class JavaScriptValues(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_any_string_round_trips(self):
        v = {"a": "back\\slash", "b": "it's", "c": "</script><b>x", "d": "line\nbreak", "e": "tab\there",
             "f": "\u2028sep", "g": 'say "hi"', "h-key": [1, None, True, {"x": "y"}],
             "i": 'slash then quote \\"', "j": "slash then apostrophe \\'", "k": "\\\\'\""}
        out = subprocess.run(["node", "-e", "console.log(JSON.stringify(" + gl.js(v) + "))"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), v)

    def test_single_quoted_like_the_example(self):
        self.assertEqual(gl.js({"statusRepo": "o/r"}), "{\n  statusRepo: 'o/r',\n}")


class Records(EnvCase):
    def test_valid_record(self):
        rec = gl.build_record(None, gl.ns(agent="acme/x", status="idle"))
        self.assertEqual(gl.validate_obj(rec), [])
        self.assertEqual(rec["operation"], "acme")
        self.assertFalse(rec["needs_human"])

    def test_waiting_needs_a_kind(self):
        with self.assertRaises(SystemExit):
            gl.build_record(None, gl.ns(agent="acme/x", status="waiting"))

    def test_waiting_with_kind(self):
        rec = gl.build_record(None, gl.ns(agent="acme/x", status="waiting", needs_human_kind="review", reason="r" * 300))
        self.assertEqual((rec["needs_human"], rec["needs_human_kind"], len(rec["needs_human_reason"])), (True, "review", 200))

    def test_empty_task_clears_and_links_merge(self):
        prev = {"current_task": {"title": "t", "url": None}, "links": {"pr": "https://x/1", "runbook": "https://x/r"}}
        rec = gl.build_record(prev, gl.ns(agent="acme/x", status="idle", task="", pr=""))
        self.assertIsNone(rec["current_task"])
        self.assertEqual(rec["links"], {"pr": None, "runbook": "https://x/r"})

    def test_only_the_current_schema_id(self):
        rec = gl.build_record(None, gl.ns(agent="acme/x", status="idle"))
        self.assertEqual(gl.validate_obj({**rec, "schema": "other.agent-status/v1"}), ["schema"])

    def test_validate_flags_bad_fields(self):
        self.assertEqual(sorted(gl.validate_obj({"status": "dancing", "needs_human": "no"})),
                         sorted(["schema", "agent", "status", "needs_human", "updated_at"]))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class FakeServer(unittest.TestCase):
    """Starts tests/fake_github.py for each test."""
    def setUp(self):
        self.port = free_port()
        self.srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "fake_github.py"), str(self.port)])
        self.addCleanup(self.srv.wait)
        self.addCleanup(self.srv.terminate)
        for _ in range(100):
            try:
                self.files(); break
            except OSError:
                time.sleep(.1)
        else:
            self.fail("fake GitHub server did not start within 10 s")

    def files(self):
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/dump").read())

    def cli(self, *args, extra=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GATHERLANE_")}
        env.update(GATHERLANE_API=f"http://127.0.0.1:{self.port}", GATHERLANE_TOKEN="t", GATHERLANE_REPO="o/r",
                   GATHERLANE_TZ="UTC", GATHERLANE_ENV=os.devnull)
        env.update(extra or {})
        return subprocess.run([sys.executable, TOOL, *args], env=env, capture_output=True, text=True)


class CLI(FakeServer):
    """The reporter as an agent runs it, against a fake GitHub contents API."""
    def test_check_pause(self):
        self.assertEqual(self.cli("check-pause", "--agent", "acme/social").returncode, 3)
        self.assertEqual(self.cli("check-pause", "--agent", "acme/other").returncode, 0)

    def test_unknown_id_is_refused_and_writes_nothing(self):
        r = self.cli("report", "--agent", "acme/supprot", "--status", "idle")
        self.assertEqual(r.returncode, 4)
        self.assertIn("pass --new", r.stderr)
        self.assertNotIn("status/acme/supprot.json", self.files())

    def test_new_then_known(self):
        self.assertEqual(self.cli("report", "--agent", "acme/support", "--status", "not_deployed", "--new").returncode, 0)
        r = self.cli("report", "--agent", "acme/support", "--status", "running", "--task", "#1 t", "--last-run-at", "now")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.files()["status/acme/support.json"]
        self.assertEqual((rec["status"], rec["current_task"]["title"]), ("running", "#1 t"))
        self.assertEqual(self.cli("validate", *self.local_copy(rec)).returncode, 0)

    def local_copy(self, rec):
        d = tempfile.mkdtemp(); f = os.path.join(d, "x.json")
        with open(f, "w") as fh:
            json.dump(rec, fh)
        return [f]

    def test_dry_run_writes_nothing(self):
        self.cli("report", "--agent", "acme/support", "--status", "idle", "--new")
        before = self.files()["status/acme/support.json"]
        r = self.cli("report", "--agent", "acme/support", "--status", "blocked", "--reason", "x", "--dry-run")
        self.assertEqual(r.returncode, 0)
        self.assertIn('"blocked"', r.stdout)
        self.assertEqual(self.files()["status/acme/support.json"], before)

    def test_run_unknown_id_still_runs_the_command(self):
        marker = os.path.join(tempfile.mkdtemp(), "ran")
        r = self.cli("run", "--agent", "acme/typo", "--", sys.executable, "-c", f"open({marker!r},'w');raise SystemExit(5)")
        self.assertEqual(r.returncode, 5)
        self.assertTrue(os.path.exists(marker))
        self.assertIn("without reporting", r.stderr)
        self.assertNotIn("status/acme/typo.json", self.files())

    def test_run_unknown_id_keeps_the_command_environment(self):
        ask = "import json,os;json.dump({'needs_human_kind':'review'},open(os.environ['GATHERLANE_OUT'],'w'));print(os.environ['GATHERLANE_AGENT'])"
        r = self.cli("run", "--agent", "acme/typo", "--", sys.executable, "-c", ask)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "acme/typo"), r.stderr)
        self.assertNotIn("status/acme/typo.json", self.files())

    def test_run_success_failure_and_ask(self):
        self.cli("report", "--agent", "acme/job", "--status", "not_deployed", "--new")
        self.assertEqual(self.cli("run", "--agent", "acme/job", "--", sys.executable, "-c", "pass").returncode, 0)
        self.assertEqual(self.files()["status/acme/job.json"]["status"], "idle")
        self.assertEqual(self.cli("run", "--agent", "acme/job", "--", sys.executable, "-c", "raise SystemExit(2)").returncode, 2)
        rec = self.files()["status/acme/job.json"]
        self.assertEqual((rec["status"], rec["needs_human_kind"], rec["needs_human_reason"]), ("failed", "failed_run", "exit code 2"))
        ask = "import json,os;json.dump({'needs_human_kind':'review','reason':'look'},open(os.environ['GATHERLANE_OUT'],'w'))"
        self.assertEqual(self.cli("run", "--agent", "acme/job", "--", sys.executable, "-c", ask).returncode, 0)
        rec = self.files()["status/acme/job.json"]
        self.assertEqual((rec["status"], rec["needs_human_kind"]), ("waiting", "review"))

    def test_paused_run_does_not_run(self):
        self.cli("report", "--agent", "acme/social", "--status", "idle", "--new")
        marker = os.path.join(tempfile.mkdtemp(), "ran")
        self.assertEqual(self.cli("run", "--agent", "acme/social", "--", sys.executable, "-c", f"open({marker!r},'w')").returncode, 0)
        self.assertFalse(os.path.exists(marker))


FAKE_PUNK = """#!{python}
# A stand-in for punk: records its argv, whether it saw the writer token and every status on the
# fake server at that moment, then exits with FAKE_PUNK_START or FAKE_PUNK_END (default 0).
import json, os, sys, urllib.request
dump = json.loads(urllib.request.urlopen(os.environ["FAKE_PUNK_DUMP"]).read())
with open(os.environ["FAKE_PUNK_LOG"], "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "token": "GATHERLANE_TOKEN" in os.environ,
                        "statuses": {{k: v.get("status") for k, v in dump.items()}}}}) + "\\n")
step = sys.argv[4] if len(sys.argv) > 4 else ""
sys.exit(int(os.environ.get("FAKE_PUNK_" + step.upper(), "0")))
"""


class RunMemoryPunk(FakeServer):
    """run --memory punk, with a fake punk on PATH that records each call."""
    def setUp(self):
        super().setUp()
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.bin, self.nobin, self.log = os.path.join(d, "bin"), os.path.join(d, "nobin"), os.path.join(d, "calls.jsonl")
        self.project = os.path.join(d, "project")
        for p in (self.bin, self.nobin, self.project):
            os.mkdir(p)
        punk = os.path.join(self.bin, "punk")
        with open(punk, "w") as f:
            f.write(FAKE_PUNK.format(python=sys.executable))
        os.chmod(punk, 0o755)
        self.cli("report", "--agent", "acme/job", "--status", "not_deployed", "--new")

    def run_agent(self, *args, agent="acme/job", code="pass", memory=True, path=None, **settings):
        """`run` with a command that logs itself to the same file as punk, then runs `code`."""
        extra = {"PATH": path or self.bin, "FAKE_PUNK_LOG": self.log, "FAKE_PUNK_DUMP": f"http://127.0.0.1:{self.port}/dump",
                 "GATHERLANE_PUNK_PROJECTS": f"{agent}={self.project}"}
        extra.update(settings)
        extra = {k: v for k, v in extra.items() if v is not None}
        cmd = f"open({self.log!r},'a').write('{{\"agent\": true}}\\n');{code}"
        return self.cli("run", "--agent", agent, *(["--memory", "punk"] if memory else []), *args,
                        "--", sys.executable, "-c", cmd, extra=extra)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return [json.loads(line) for line in f]

    def steps(self):
        return [c["argv"][3] if "argv" in c else "agent" for c in self.calls()]

    def status(self, agent="acme/job"):
        return self.files()[gl.path_of(agent)]

    def punk_lines(self, r):
        return [l for l in r.stderr.splitlines() if l.startswith("gatherlane:")]

    def test_start_then_agent_then_end_with_agent_and_project(self):
        r = self.run_agent()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.steps(), ["start", "agent", "end"])
        start, _, end = self.calls()
        self.assertEqual(start["argv"], ["--agent", "acme/job", "session", "start", "--project", self.project])
        self.assertEqual(end["argv"], ["--agent", "acme/job", "session", "end", "--project", self.project])
        # punk starts only after `run` passed the pause check and reported running, and never sees the token
        self.assertEqual((start["statuses"]["status/acme/job.json"], end["statuses"]["status/acme/job.json"]), ("running", "running"))
        self.assertEqual((start["token"], end["token"]), (False, False))
        self.assertEqual(self.status()["status"], "idle")
        self.assertEqual(self.punk_lines(r), [])  # exit 0 is quiet: punk prints its own warnings

    def test_paused_agent_gets_no_punk(self):
        self.cli("report", "--agent", "acme/social", "--status", "idle", "--new")
        r = self.run_agent(agent="acme/social")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("paused: holiday; not running", r.stdout)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.punk_lines(r), [])
        self.assertEqual(self.status("acme/social")["status"], "idle")

    def test_end_runs_when_the_agent_fails(self):
        r = self.run_agent(code="raise SystemExit(7)")
        self.assertEqual(r.returncode, 7)
        self.assertEqual(self.steps(), ["start", "agent", "end"])
        rec = self.status()
        self.assertEqual((rec["status"], rec["needs_human_reason"]), ("failed", "exit code 7"))

    def test_end_runs_when_the_command_cannot_start(self):
        extra = {"PATH": self.bin, "FAKE_PUNK_LOG": self.log, "FAKE_PUNK_DUMP": f"http://127.0.0.1:{self.port}/dump",
                 "GATHERLANE_PUNK_PROJECTS": f"acme/job={self.project}"}
        r = self.cli("run", "--agent", "acme/job", "--memory", "punk", "--", os.path.join(self.nobin, "missing"), extra=extra)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.steps(), ["start", "end"])

    def test_punk_failures_leave_exit_code_and_status_alone(self):
        for punk_rc, line in (("1", "failed (exit 1), ignored"), ("2", "needs a person (exit 2): run `punk status`")):
            for code, want_rc, want_status in (("pass", 0, "idle"), ("raise SystemExit(3)", 3, "failed")):
                with self.subTest(punk=punk_rc, agent=want_rc):
                    os.path.exists(self.log) and os.unlink(self.log)
                    r = self.run_agent(code=code, FAKE_PUNK_START=punk_rc, FAKE_PUNK_END=punk_rc)
                    self.assertEqual(r.returncode, want_rc, r.stderr)
                    self.assertEqual(self.steps(), ["start", "agent", "end"])
                    self.assertEqual(self.status()["status"], want_status)
                    lines = self.punk_lines(r)
                    self.assertEqual(len(lines), 2, lines)
                    self.assertIn("punk session start " + line, lines[0])
                    self.assertIn("punk session end " + line, lines[1])

    def test_punk_missing_runs_anyway(self):
        r = self.run_agent(path=self.nobin, code="raise SystemExit(4)")
        self.assertEqual(r.returncode, 4)
        self.assertEqual(self.steps(), ["agent"])
        self.assertEqual(self.punk_lines(r), ["gatherlane: --memory punk: punk is not on PATH; running without punk"])
        self.assertEqual(self.status()["status"], "failed")

    def test_bad_id_skips_punk(self):
        for bad in ("acme/job!", "acme/" + "x" * 124):  # 128 characters fits punk's pattern, 129 does not
            with self.subTest(bad=bad):
                os.path.exists(self.log) and os.unlink(self.log)
                self.cli("report", "--agent", bad, "--status", "not_deployed", "--new")
                r = self.run_agent(agent=bad)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.steps(), ["agent"])
                lines = self.punk_lines(r)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn("is not a punk agent id", lines[0])
                self.assertEqual(self.status(bad)["status"], "idle")
        ok = "acme/" + "x" * 123
        self.cli("report", "--agent", ok, "--status", "not_deployed", "--new")
        os.unlink(self.log)
        self.assertEqual(self.run_agent(agent=ok).returncode, 0)
        self.assertEqual(self.steps(), ["start", "agent", "end"])

    def test_missing_project_setting_runs_anyway(self):
        for setting in (None, "", "acme/other=/srv/x", f"acme/job={self.project},acme/job=/srv/elsewhere"):
            with self.subTest(setting=setting):
                os.path.exists(self.log) and os.unlink(self.log)
                r = self.run_agent(code="raise SystemExit(6)", GATHERLANE_PUNK_PROJECTS=setting)
                self.assertEqual(r.returncode, 6)
                self.assertEqual(self.steps(), ["agent"])
                lines = self.punk_lines(r)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn("listed twice" if setting and "elsewhere" in setting else "no project directory", lines[0])
                self.assertEqual(self.status()["status"], "failed")

    def test_project_setting_from_the_env_file(self):
        envf = os.path.join(self.project, "env")
        with open(envf, "w") as f:
            f.write(f"export GATHERLANE_PUNK_PROJECTS='acme/other=/srv/other, acme/job={self.project}'\n")
        r = self.run_agent(GATHERLANE_PUNK_PROJECTS=None, GATHERLANE_ENV=envf)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls()[0]["argv"][-1], self.project)

    def test_skip_on_start_failure(self):
        r = self.run_agent(FAKE_PUNK_START="2", GATHERLANE_PUNK_SKIP_ON_START_FAILURE="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.steps(), ["start"])  # neither the agent nor session end
        rec = self.status()
        self.assertEqual((rec["status"], rec["last_result"], rec["needs_human"]), ("blocked", "skipped", False))
        self.assertEqual(rec["needs_human_reason"],
                         "punk session start failed (exit 2); run skipped (GATHERLANE_PUNK_SKIP_ON_START_FAILURE=1)")
        self.assertIsNone(rec["current_task"])

    def test_skip_on_start_failure_only_when_set_and_start_failed(self):
        for settings, want in (({"FAKE_PUNK_START": "1"}, ["start", "agent", "end"]),
                               ({"FAKE_PUNK_START": "1", "GATHERLANE_PUNK_SKIP_ON_START_FAILURE": "0"}, ["start", "agent", "end"]),
                               ({"GATHERLANE_PUNK_SKIP_ON_START_FAILURE": "1"}, ["start", "agent", "end"]),
                               ({"GATHERLANE_PUNK_SKIP_ON_START_FAILURE": "1", "path": "nobin"}, ["agent"])):
            with self.subTest(settings=settings):
                os.path.exists(self.log) and os.unlink(self.log)
                if settings.get("path"):
                    settings = {**settings, "path": self.nobin}
                r = self.run_agent(**settings)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.steps(), want)
                self.assertEqual(self.status()["status"], "idle")

    def test_without_memory_nothing_changes(self):
        r = self.run_agent(memory=False, FAKE_PUNK_START="2", GATHERLANE_PUNK_SKIP_ON_START_FAILURE="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.steps(), ["agent"])
        self.assertEqual((r.stdout, r.stderr), ("status/acme/job.json: running\nstatus/acme/job.json: idle\n", ""))
        self.assertEqual(self.status()["status"], "idle")

    def test_unknown_id_runs_without_punk(self):
        r = self.run_agent(agent="acme/typo", code="raise SystemExit(5)")
        self.assertEqual(r.returncode, 5)
        self.assertEqual(self.steps(), ["agent"])
        self.assertIn("Running the command without reporting.", r.stderr)
        self.assertEqual(self.punk_lines(r), ["gatherlane: --memory punk: no punk session for an id without a status file; running without punk"])
        self.assertNotIn("status/acme/typo.json", self.files())


class PunkProjects(EnvCase):
    def test_pairs_spaces_home_and_duplicates(self):
        os.environ["GATHERLANE_PUNK_PROJECTS"] = " a/x = /srv/x ,b/y=~/gatherlane,broken,=z,c/z=/1,c/z=/2,d/w=/w,d/w=/w"
        self.assertEqual(gl.punk_projects(), {"a/x": "/srv/x", "b/y": os.path.expanduser("~/gatherlane"), "c/z": None, "d/w": "/w"})


class Init(FakeServer):
    """gatherlane init against the fake server, into a temporary instance and env file."""
    def init(self, *args, token=True, env_text=None):
        d = tempfile.mkdtemp()
        inst, envf = os.path.join(d, "instance"), os.path.join(d, "env")
        if env_text is not None:
            with open(envf, "w") as f:
                f.write(env_text)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GATHERLANE_")}
        env.update(GATHERLANE_API=f"http://127.0.0.1:{self.port}", GATHERLANE_ENV=envf)
        if token:
            env["GATHERLANE_TOKEN"] = "t"
        r = subprocess.run([sys.executable, TOOL, "init", "--instance", inst, "--env-file", envf, *args],
                           env=env, capture_output=True, text=True)
        return r, inst, envf

    def test_without_token_writes_nothing(self):
        r, inst, envf = self.init("--repo", "o/r", "--agent", "web/a", token=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("GATHERLANE_TOKEN is not set", r.stderr)
        self.assertIn("Contents: read and write", r.stderr)  # says how to make one
        self.assertFalse(os.path.exists(inst) or os.path.exists(envf))

    def test_new_office(self):
        r, inst, envf = self.init("--repo", "o/r", "--agent", "web/implementer", "--agent", "web/pr-reviewer",
                                  "--agent", "orchestrator-1", "--watch", "o/app", "--maintainer", "robin",
                                  "--tz", "Europe/Berlin", env_text="export GATHERLANE_TOKEN=t\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(inst)), ["building.js", "config.js", "sample.js"])
        files = self.files()
        for path in ("status/web/implementer.json", "status/web/pr-reviewer.json", "status/shared/orchestrator-1.json"):
            self.assertEqual(files[path]["status"], "not_deployed", path)
        with open(envf) as f:
            text = f.read()
        self.assertEqual(text, "export GATHERLANE_TOKEN=t\nexport GATHERLANE_REPO=o/r\nexport GATHERLANE_TZ=Europe/Berlin\n")
        self.assertIn("gh label create review:approved -R o/app", r.stdout)
        if shutil.which("node"):  # the written config loads, and the generated building places every agent
            js = ("require(process.argv[1]); require(process.argv[2]); const C = GATHERLANE_CONFIG, L = Layout.fromConfig(C).LEVELS;"
                  "console.log(JSON.stringify([C.statusRepo, C.timeZone, C.maintainer, C.operations.web.repos,"
                  " L.map(l => [l.id, l.agents.map(a => a.id)])]))")
            out = subprocess.run(["node", "-e", js, os.path.join(inst, "config.js"), os.path.join(ROOT, "app", "js", "layout.js")],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout), ["o/r", "Europe/Berlin", "robin", ["o/app"],
                             [["den", ["orchestrator-1"]], ["web", ["web/implementer", "web/pr-reviewer"]], ["supervisor", ["robin"]]]])

    def test_env_file_created_owner_only(self):
        r, inst, envf = self.init("--repo", "o/r", "--agent", "web/a")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.stat(envf).st_mode & 0o777, 0o600)
        with open(envf) as f:
            self.assertNotIn("TOKEN", f.read())

    def test_watch_default_skips_the_den(self):
        r, inst, _ = self.init("--repo", "o/r", "--agent", "orchestrator-1", "--agent", "web/a", "--watch", "o/app")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(inst, "config.js")) as f:
            text = f.read()
        self.assertIn("defaultLevel: 'web'", text)
        self.assertRegex(text, r"web: \{\n\s+name: 'Web',\n\s+level: 'web',\n\s+repos: \['o/app'\]")

    def test_creates_a_missing_status_branch(self):
        d = tempfile.mkdtemp()
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("GATHERLANE_")},
               "GATHERLANE_API": f"http://127.0.0.1:{self.port}", "GATHERLANE_TOKEN": "t", "GATHERLANE_BRANCH": "fresh"}
        r = subprocess.run([sys.executable, TOOL, "init", "--repo", "o/r", "--agent", "web/a", "--instance", os.path.join(d, "i"),
                            "--env-file", os.path.join(d, "env")], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("created branch fresh", r.stdout)
        refs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/refs").read())
        self.assertEqual(refs.get("fresh"), refs["main"])

    def test_existing_instance_needs_force(self):
        r, inst, _ = self.init("--repo", "o/r", "--agent", "web/a")
        with open(os.path.join(inst, "config.js")) as f:
            before = f.read()
        r2 = subprocess.run([sys.executable, TOOL, "init", "--repo", "o/r", "--agent", "web/b", "--instance", inst],
                            env={**os.environ, "GATHERLANE_API": f"http://127.0.0.1:{self.port}", "GATHERLANE_TOKEN": "t",
                                 "GATHERLANE_ENV": os.devnull}, capture_output=True, text=True)
        self.assertNotEqual(r2.returncode, 0)
        self.assertIn("--force", r2.stderr)
        with open(os.path.join(inst, "config.js")) as f:
            self.assertEqual(f.read(), before)

    def test_registered_agent_is_left_alone(self):
        self.cli("report", "--agent", "acme/social", "--status", "running", "--new")
        r, _, _ = self.init("--repo", "o/r", "--agent", "acme/social")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("already has a status file", r.stdout)
        self.assertEqual(self.files()["status/acme/social.json"]["status"], "running")

    def test_bad_input(self):
        for args in (["--repo", "o/r", "--agent", "Web/Bad Id"], ["--repo", "nope", "--agent", "web/a"],
                     ["--repo", "o/r", "--agent", "web/a", "--watch", "ops:o/x"], ["--repo", "o/r", "--agent", "web/a", "--tz", "Mars/Base"]):
            r, inst, _ = self.init(*args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertFalse(os.path.exists(inst), args)


if __name__ == "__main__":
    unittest.main()
