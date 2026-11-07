# SPDX-License-Identifier: Apache-2.0
# .gitignore: agent worktrees and Docker test probes are never committed, and agent files stay trackable.
import importlib.util, os, subprocess, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ignored(path, env=None):
    """Whether this repository's .gitignore ignores path. core.excludesFile is pointed at an empty
    file so the runner's global ignore cannot change the answer either way."""
    r = subprocess.run(["git", "-c", "core.excludesFile=" + os.devnull, "check-ignore", "-q", "--no-index", path],
                       cwd=ROOT, env=env)
    if r.returncode not in (0, 1):
        raise AssertionError(f"git check-ignore failed on {path}: exit {r.returncode}")
    return r.returncode == 0


class GitIgnore(unittest.TestCase):
    def test_agent_worktrees_are_ignored(self):
        self.assertTrue(ignored(".claude/worktrees/x"))
        self.assertTrue(ignored(".claude/worktrees/agent-1/app/js/app.js"))

    def test_agent_files_are_not_ignored(self):
        self.assertFalse(ignored(".claude/agents/x.md"))
        self.assertFalse(ignored(".claude/settings.json"))

    def test_docker_probe_files_are_ignored(self):
        """The live Docker test writes probe files into app/ and deletes them afterwards; a run
        killed in between leaves them, and they must not be committed by accident. Every name
        tests/test_docker.py can make is checked, so a new probe file needs its line here too.
        The site's own files, a probe-like name outside app/, and a real file whose name merely
        starts like a probe (no hyphen and digit straight after the prefix) stay trackable."""
        spec = importlib.util.spec_from_file_location("test_docker", os.path.join(ROOT, "tests", "test_docker.py"))
        td = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(td)
        names = td.probe_names(td.probe_tag())
        self.assertEqual(len(names), 4, "control: every probe kind is listed")
        for name in names.values():
            self.assertTrue(ignored("app/" + name), name)
        for path in ("app/index.html", "app/js/app.js", "app/instance/config.js", "app/_headers",
                     "tests/" + names["plain"], "app/js/probe.js", "app/js/gatherlane-prober.js",
                     "app/instance/gatherlane-probes.js", "app/gatherlane-probe/real.js",
                     "app/gatherlane-probe.js", "app/.gatherlane-probes", "app/gatherlane-probe-notes.js",
                     "app/.gatherlane-probe-notes"):
            self.assertFalse(ignored(path), path)

    def test_global_ignore_is_not_read(self):
        """A global ignore that lists .claude/ would hide a widened line, and one that lists
        .claude/worktrees/ would hide a deleted one. With such a file as the global ignore, the
        answers above stay the same."""
        d = tempfile.mkdtemp()
        excludes, config = os.path.join(d, "ignore"), os.path.join(d, "gitconfig")
        with open(excludes, "w") as f:
            f.write(".claude/\n")
        with open(config, "w") as f:
            f.write("[core]\n\texcludesFile = " + excludes + "\n")
        env = dict(os.environ, GIT_CONFIG_GLOBAL=config)
        probe = subprocess.run(["git", "check-ignore", "-q", "--no-index", ".claude/agents/x.md"], cwd=ROOT, env=env)
        self.assertEqual(probe.returncode, 0, "control: without the override the global ignore applies")
        self.assertFalse(ignored(".claude/agents/x.md", env))
        self.assertFalse(ignored(".claude/settings.json", env))


if __name__ == "__main__":
    unittest.main()
