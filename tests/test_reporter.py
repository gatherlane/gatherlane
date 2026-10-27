# SPDX-License-Identifier: Apache-2.0
# Tests for tools/gatherlane.py: python3 -m unittest discover -s tests
# Standard library only. The CLI tests run the reporter against tests/fake_github.py.
import datetime as dt, importlib.util, json, os, socket, subprocess, sys, tempfile, time, unittest, urllib.request
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


class CLI(unittest.TestCase):
    """The reporter as an agent runs it, against a fake GitHub contents API."""
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

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GATHERLANE_")}
        env.update(GATHERLANE_API=f"http://127.0.0.1:{self.port}", GATHERLANE_TOKEN="t", GATHERLANE_REPO="o/r",
                   GATHERLANE_TZ="UTC", GATHERLANE_ENV=os.devnull)
        return subprocess.run([sys.executable, TOOL, *args], env=env, capture_output=True, text=True)

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


if __name__ == "__main__":
    unittest.main()
