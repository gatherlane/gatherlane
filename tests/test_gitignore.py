# SPDX-License-Identifier: Apache-2.0
# .gitignore: agent worktrees are never committed, and agent files stay trackable.
import os, subprocess, tempfile, unittest

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
