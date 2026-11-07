# SPDX-License-Identifier: Apache-2.0
# tools/export_public.py: the public copy has the example instance, no private parts, and the
# scan catches a leaked name or a home path.
import importlib.util, io, os, subprocess, sys, tarfile, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "export_public.py")
spec = importlib.util.spec_from_file_location("export_public", TOOL)
ep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep)
# Set while the round-trip test runs an exported tree's own suite, so that suite does not do it again.
NESTED = "GATHERLANE_EXPORT_NESTED"
GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]


def repo_from_head(edit):
    """A throwaway git repository holding this tree's HEAD, changed by edit(path) and committed,
    so an export can run on a tree this repository does not have."""
    d = os.path.join(tempfile.mkdtemp(), "repo")
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(d, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    edit(d)
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], [*GIT_ID, "commit", "-q", "-m", "x"]):
        subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)
    return d


def run_export(repo, out, *args):
    return subprocess.run([sys.executable, os.path.join(repo, "tools", "export_public.py"), out, *args],
                          cwd=repo, capture_output=True, text=True)


class Export(unittest.TestCase):
    def test_public_tree(self):
        out = os.path.join(tempfile.mkdtemp(), "public")
        r = subprocess.run([sys.executable, TOOL, out, "--no-commit"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(out, "growth")))
        self.assertFalse(os.path.exists(os.path.join(out, ".git")))
        exported = sorted(os.listdir(os.path.join(out, "app", "instance")))
        committed = subprocess.run(["git", "ls-tree", "--name-only", "HEAD", "examples/instance/"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(exported, sorted(os.path.basename(f) for f in committed))
        for f in committed:  # the export is HEAD, so compare with HEAD, not the working tree
            head = subprocess.run(["git", "show", f"HEAD:{f}"], cwd=ROOT, capture_output=True, check=True).stdout
            with open(os.path.join(out, "app", "instance", os.path.basename(f)), "rb") as fh:
                self.assertEqual(fh.read(), head, f)
        for f in ("LICENSE", "NOTICE", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "app/js/app.js", "tools/gatherlane.py"):
            self.assertTrue(os.path.exists(os.path.join(out, f)), f)

    def test_claude_md_shipped_is_the_public_one(self):
        """The export ships examples/public-CLAUDE.md as CLAUDE.md, so this repository's own one,
        which describes a private workflow, never reaches the public tree. The public tree has
        exactly one CLAUDE.md, at the root: the source is moved there, not copied, so it does not
        also ship under examples/."""
        out = os.path.join(tempfile.mkdtemp(), "public")
        r = subprocess.run([sys.executable, TOOL, out, "--no-commit"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        # In this repository the source is PUBLIC_CLAUDE. In the public tree, which has no such
        # file, the root CLAUDE.md is already the public one and ships as it is.
        private_tree = os.path.exists(os.path.join(ROOT, ep.PUBLIC_CLAUDE))
        source = ep.PUBLIC_CLAUDE if private_tree else "CLAUDE.md"
        head = subprocess.run(["git", "show", "HEAD:" + source], cwd=ROOT, capture_output=True, check=True).stdout
        self.assertTrue(head, source + " must be committed for the export to have one to ship")
        with open(os.path.join(out, "CLAUDE.md"), "rb") as fh:
            self.assertEqual(fh.read(), head)
        claude_like = sorted(os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(out) for f in fs
                             if "claude" in f.lower() and f.lower().endswith(".md"))
        self.assertEqual(claude_like, ["CLAUDE.md"])
        if private_tree:  # only this repository has two files to compare
            private = subprocess.run(["git", "show", "HEAD:CLAUDE.md"], cwd=ROOT, capture_output=True, check=True)
            self.assertNotEqual(private.stdout, head, "the private and public files must differ")

    def test_export_of_the_export(self):
        """The public tree runs its own export and its own tests in its CI. Exporting it again
        must succeed and ship the same CLAUDE.md, and its suite must pass there."""
        first = os.path.join(tempfile.mkdtemp(), "public")
        r = run_export(ROOT, first, "--identity", "Robin <1+robin@users.noreply.github.com>")
        self.assertEqual(r.returncode, 0, r.stderr)
        second = os.path.join(tempfile.mkdtemp(), "public")
        r = run_export(first, second, "--no-commit")
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in ("CLAUDE.md", "app/instance/config.js"):
            with open(os.path.join(first, f), "rb") as a, open(os.path.join(second, f), "rb") as b:
                self.assertEqual(a.read(), b.read(), f)
        if os.environ.get(NESTED):
            return
        # Without GATHERLANE_DOCKER_URL: a running container serves this checkout's app/, not the
        # exported tree's, so test_docker there would probe the wrong mount.
        env = {k: v for k, v in os.environ.items() if k != "GATHERLANE_DOCKER_URL"}
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=first,
                           capture_output=True, text=True, env=dict(env, **{NESTED: "1"}))
        self.assertEqual(r.returncode, 0, "the exported tree's own suite fails:\n" + r.stderr[-3000:])

    def test_no_public_source_with_a_private_instance_ships_nothing(self):
        """Without PUBLIC_CLAUDE the export keeps the root CLAUDE.md, which is right only in the
        public tree. A tree that still has a private instance and has lost PUBLIC_CLAUDE would ship
        the private rules, so the export refuses it and writes nothing."""
        def drop_source(d):
            if os.path.exists(os.path.join(d, ep.PUBLIC_CLAUDE)):
                os.remove(os.path.join(d, ep.PUBLIC_CLAUDE))

        def drop_source_and_plant(d):
            drop_source(d)
            with open(os.path.join(d, "app", "instance", "config.js"), "a") as f:
                f.write("\n// maintainer: 'standinword'\n")
        edits = [drop_source_and_plant]
        if ep.private_terms():  # in this repository, deleting the source alone must be enough
            edits.append(drop_source)
        for edit in edits:
            with self.subTest(edit.__name__):
                out = os.path.join(tempfile.mkdtemp(), "public")
                r = run_export(repo_from_head(edit), out)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(ep.PUBLIC_CLAUDE, r.stderr)
                self.assertFalse(os.path.exists(out))

    def test_public_claude_md_does_not_load_here(self):
        """Claude Code loads any CLAUDE.md or CLAUDE.local.md in a subdirectory as instructions once
        an agent touches a file there. The public text describes the public tree and is false here,
        so its source must not carry a name that loads: the only one tracked is the root file."""
        self.assertNotIn(os.path.basename(ep.PUBLIC_CLAUDE), ("CLAUDE.md", "CLAUDE.local.md"))
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        loads = [f for f in tracked if os.path.basename(f) in ("CLAUDE.md", "CLAUDE.local.md")]
        self.assertEqual(loads, ["CLAUDE.md"])
        self.assertFalse(os.path.exists(os.path.join(ROOT, "examples", "CLAUDE.md")))

    def test_claude_paths_are_on_the_private_list(self):
        """Asserted on the list rather than on the output, because neither is observable there
        today: the move above overwrites an extracted CLAUDE.md whether or not it was excluded,
        and .claude/ is not committed yet, so looking for its absence would pass either way.
        Both entries are what keeps the next agent file, and a committed CLAUDE.md, out of a
        tree that is published."""
        self.assertIn("CLAUDE.md", ep.PRIVATE)
        self.assertIn(".claude/", ep.PRIVATE)
        for name in ("CLAUDE.md", ".claude/agents/reviewer.md"):  # how export() tests a tar member
            self.assertTrue((name + "/").startswith(ep.PRIVATE), name)
        self.assertFalse((ep.PUBLIC_CLAUDE + "/").startswith(ep.PRIVATE))  # the public one still ships

    def test_private_names_file_adds_terms(self):
        """Names that appear in no config.js, such as the maintainer's surname, live in
        PRIVATE_NAMES, which the export reads and never ships. A stand-in word proves a term
        there is scanned for as a whole word in any letter case."""
        d = tempfile.mkdtemp()
        for inst in ("app/instance", "examples/instance"):
            os.makedirs(os.path.join(d, inst))
            with open(os.path.join(d, inst, "config.js"), "w") as f:
                f.write("  G.GATHERLANE_CONFIG = { maintainer: 'robin' };\n")
        self.assertEqual(ep.private_terms(d), set(), "control: the same config on both sides names nothing")
        os.makedirs(os.path.dirname(os.path.join(d, ep.PRIVATE_NAMES)), exist_ok=True)
        with open(os.path.join(d, ep.PRIVATE_NAMES), "w") as f:
            f.write("# a comment line\n\n  Standinword  \n")
        self.assertEqual(ep.private_terms(d), {"standinword"})
        with open(os.path.join(d, "a.md"), "w") as f:
            f.write("by STANDINWORD.\nstandinwords and xstandinword are other words\n")
        self.assertEqual(ep.scan(["a.md"], d, ep.private_terms(d), paths=False), ["a.md:1: STANDINWORD"])

    def test_private_names_file_never_ships(self):
        self.assertTrue((ep.PRIVATE_NAMES + "/").startswith(ep.PRIVATE))
        self.assertFalse(ep.PRIVATE_NAMES.startswith("app/"), "Pages serves app/, so the list must not be there")

    def test_export_stops_on_a_private_names_term(self):
        if not os.path.exists(os.path.join(ROOT, ep.PUBLIC_CLAUDE)):
            self.skipTest("in the public tree any private name stops the export earlier, as a private instance")
        def plant(d):
            with open(os.path.join(d, ep.PRIVATE_NAMES), "a") as f:
                f.write("\nstandinword\n")
            with open(os.path.join(d, "docs", "SETUP.md"), "a") as f:
                f.write("\nThanks to Standinword.\n")
        out = os.path.join(tempfile.mkdtemp(), "public")
        r = run_export(repo_from_head(plant), out)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("docs/SETUP.md", r.stderr)
        self.assertIn("Standinword", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(out, ".git")))

    def test_private_tree_needs_its_private_names(self):
        """In this repository a missing or empty PRIVATE_NAMES would quietly drop those terms from
        the scan, so the export refuses to run without them."""
        if not os.path.exists(os.path.join(ROOT, ep.PUBLIC_CLAUDE)):
            self.skipTest("the public tree has no private names")
        def empty(d):
            with open(os.path.join(d, ep.PRIVATE_NAMES), "w") as f:
                f.write("# nothing\n")
        def missing(d):
            os.remove(os.path.join(d, ep.PRIVATE_NAMES))
        for edit in (empty, missing):
            with self.subTest(edit.__name__):
                out = os.path.join(tempfile.mkdtemp(), "public")
                r = run_export(repo_from_head(edit), out)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(ep.PRIVATE_NAMES, r.stderr)
                self.assertFalse(os.path.exists(out))

    def test_instruction_files_are_listed(self):
        """Claude Code loads CLAUDE.md, CLAUDE.local.md and .claude/ as instructions. The public
        tree may carry only the root CLAUDE.md."""
        files = ["CLAUDE.md", "README.md", "tools/CLAUDE.md", "CLAUDE.local.md", "examples/CLAUDE.local.md",
                 "docs/.claude/settings.json", "app/claude.md", "notes/CLAUDE.md.txt", "x.claude/y", "docs/claude-notes.md",
                 ".Claude/settings.json", "docs/.CLAUDE/x"]
        self.assertEqual(ep.instruction_files(files),
                         ["tools/CLAUDE.md", "CLAUDE.local.md", "examples/CLAUDE.local.md",
                          "docs/.claude/settings.json", "app/claude.md", ".Claude/settings.json", "docs/.CLAUDE/x"])

    def test_export_refuses_instruction_files(self):
        def plant(d):
            for f in ("tools/CLAUDE.md", "CLAUDE.local.md", "examples/.claude/settings.json"):
                os.makedirs(os.path.dirname(os.path.join(d, f)) or d, exist_ok=True)
                with open(os.path.join(d, f), "w") as fh:
                    fh.write("{}\n")
        out = os.path.join(tempfile.mkdtemp(), "public")
        r = run_export(repo_from_head(plant), out)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for f in ("tools/CLAUDE.md", "CLAUDE.local.md", "examples/.claude/settings.json"):
            self.assertIn(f, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(out, ".git")))

    def test_identity_sets_author_and_committer(self):
        out = os.path.join(tempfile.mkdtemp(), "public")
        r = subprocess.run([sys.executable, TOOL, out, "--identity", "Robin <1+robin@users.noreply.github.com>"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        log = subprocess.run(["git", "log", "-1", "--format=%an <%ae>|%cn <%ce>"], cwd=out, capture_output=True, text=True).stdout.strip()
        self.assertEqual(log, "Robin <1+robin@users.noreply.github.com>|Robin <1+robin@users.noreply.github.com>")

    def test_bad_identity_commits_nothing(self):
        out = os.path.join(tempfile.mkdtemp(), "public")
        r = subprocess.run([sys.executable, TOOL, out, "--identity", "no email here"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(out, ".git", "HEAD")))

    def test_refuses_a_non_empty_directory(self):
        out = tempfile.mkdtemp()
        open(os.path.join(out, "x"), "w").close()
        r = subprocess.run([sys.executable, TOOL, out, "--no-commit"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)

    def test_scan_finds_names_and_paths(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "a.md"), "w") as f:
            f.write("fine line\nsee secretorg/thing\nstocks are fine\nrun /" + "Users/me/x\n")
        self.assertEqual(ep.scan(["a.md"], d, {"secretorg", "tock"}),
                         ["a.md:2: secretorg", "a.md:4: /" + "Users/"])

    def test_scan_finds_home_relative_paths(self):
        """A home-relative path to a private place fails the scan, written with a tilde, HOME or
        braced HOME; so does a tilde followed by another user's name, an absolute Linux home path,
        a Windows Users path with backslashes and the USERPROFILE variable. The few paths the public docs use on purpose (the reporter's env
        file and clone, a log directory, the Playwright cache) do not, unless a /.. segment leads
        back out of them. Strings are built at runtime so this file does not trip the scan itself."""
        h, dh, bh = "~" + "/", "$" + "HOME/", "${" + "HOME}/"
        win, up = "C:" + "\\" + "Users" + "\\", "%" + "USERPROFILE%"
        d = tempfile.mkdtemp()
        lines = [h + "napkin/notes/review.md",                             # 1: private notes
                 h + ".claude/agents/scout.md",                            # 2: a private agent file
                 "see " + h + "Projects/x/PLAN.md",                         # 3: as before
                 h + "gatherlane-private/x",                               # 4: an allowed name is a whole name only
                 'exec python3 "' + dh + 'Projects/gatherlane/private/tools/gatherlane.py"',  # 5: the wrapper
                 bh + "napkin/notes.md",                                   # 6
                 "cat " + dh + "gatherlane/../napkin/cycle.md",             # 7: allowed, then back out
                 h + "logs/x/../../napkin",                                # 8: same, deeper
                 "cd ~" + "robin/notes",                                   # 9: another user's home
                 "/" + "home/robin/x",                                     # 10
                 "dir " + win + "bob\\napkin",                              # 11
                 up + "\\napkin",                                           # 12
                 h + ".config/gatherlane/env",                             # 13..20: allowed on purpose
                 h + "gatherlane/tools/gatherlane.py",
                 h + "logs/agent.log",
                 h + "Library/Caches/ms-playwright/x",
                 dh + ".config/gatherlane/env",
                 bh + "gatherlane/tools",
                 h + "gatherlane/..x/y",                                   # a name starting with .., not a .. segment
                 "(" + h + "gatherlane/) and (" + h + "logs)",
                 "~ alone, a/~/b, x~y/z, $" + "HOME alone and " + h + " end"]  # 21: not a home path
        with open(os.path.join(d, "a.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        self.assertEqual(ep.scan(["a.md"], d, set()),
                         ["a.md:1: " + h + "napkin", "a.md:2: " + h + ".claude",
                          "a.md:3: " + h + "Projects", "a.md:4: " + h + "gatherlane-private",
                          "a.md:5: " + dh + "Projects", "a.md:6: " + bh + "napkin",
                          "a.md:7: " + dh + "gatherlane", "a.md:8: " + h + "logs",
                          "a.md:9: ~" + "robin/", "a.md:10: /" + "home/r",
                          "a.md:11: " + win, "a.md:12: " + up])

    def test_scan_finds_more_home_forms(self):
        """PowerShell's USERPROFILE, HOME in double quotes, root's home and a Users directory in
        lower case. A Users or root segment inside a longer path or a URL, or after a dot or a
        hyphen, is not a home path."""
        q, qb = '"$' + 'HOME"/', '"${' + 'HOME}"/'
        ps, psb = "$" + "env:" + "USERPROFILE", "${" + "env:" + "USERPROFILE}"
        r, u, U = "/" + "root/", "/" + "users/", "/" + "USERS/"
        d = tempfile.mkdtemp()
        lines = ["cd " + ps + "\\napkin",                                  # 1
                 psb + "\\napkin",                                         # 2
                 "$" + "ENV:" + "userprofile",                             # 3: PowerShell ignores case
                 "cat " + q + "napkin/notes.md",                           # 4
                 qb + "napkin",                                            # 5
                 "ls " + r + ".ssh",                                       # 6
                 "open " + u + "bob/x",                                    # 7
                 "(" + U + "bob)",                                         # 8
                 q + "gatherlane/tools/gatherlane.py",                     # 9..: allowed or not a home path
                 qb + ".config/gatherlane/env",
                 "https://api.github.com" + u + "robin and src" + r + "x and a.b" + u + "c",
                 "$" + "env:" + "PATH and %" + "PATH% and " + '"$' + 'HOME" alone',
                 "." + u + "x",                                            # after a dot or a hyphen: not a path start
                 "x-" + u + "y",
                 "." + r + "x",
                 "x-" + r + "y"]
        with open(os.path.join(d, "a.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        self.assertEqual(ep.scan(["a.md"], d, set()),
                         ["a.md:1: " + ps, "a.md:2: " + psb[:-1], "a.md:3: $" + "ENV:" + "userprofile",
                          "a.md:4: " + q + "napkin", "a.md:5: " + qb + "napkin",
                          "a.md:6: " + r, "a.md:7: " + u, "a.md:8: " + U])

    def test_scan_dotdot_ends_at_any_segment_end(self):
        """A .. segment leads out of an allowed path wherever the segment ends: at a slash, at the
        end of the line, at whitespace, or at a quote, backtick, parenthesis or angle bracket."""
        a = "~" + "/gatherlane"
        ends = ["", "/x", " x", "'", '"', "`", "(x", ")", "<x", ">", "\tx"]
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "a.md"), "w") as f:
            f.write("\n".join(a + "/.." + e for e in ends) + "\n" + a + "/..x\n")
        self.assertEqual(ep.scan(["a.md"], d, set()), [f"a.md:{n}: {a}" for n in range(1, len(ends) + 1)])

    def test_scan_backslash_and_other_separators(self):
        """Windows takes a backslash where a slash goes, so a backslash is a separator too: after
        the home prefix, after another user's name, around Users, and on either side of a ..
        segment that leads out of an allowed path. A .. segment also ends at a brace (shell brace
        expansion turns ..{/x,} into ../x). Line 1 is the known-positive control in the form the
        scan already caught; the rest were all missed before. Lines 15 to 20 repeat the separator
        after the home prefix, as JSON and JS escaping does to a backslash. Lines 21 and 22 are
        flagged on purpose: the slashes inside a PUBLIC_HOME entry are literal (see PUBLIC_HOME),
        and those are the two entries with a slash inside. Built at runtime so this file does not
        trip the scan itself."""
        t, b = "~", "\\"
        dh, bh, qh = "$" + "HOME", "${" + "HOME}", '"$' + 'HOME"'
        d = tempfile.mkdtemp()
        lines = [t + "/logs/../napkin",                                    # 1: control, caught before
                 t + "/logs/.." + b + "napkin",                            # 2: the case in the issue
                 t + "/logs" + b + ".." + b + "napkin",                    # 3
                 t + "/gatherlane" + b + "../napkin",                      # 4
                 t + "/logs/.." + b,                                       # 5: .. then a backslash at the end
                 t + "/gatherlane/..{/napkin,}",                           # 6: brace expansion
                 t + b + "napkin" + b + "notes.md",                        # 7: PowerShell home forms
                 dh + b + "napkin",                                        # 8
                 bh + b + "napkin",                                        # 9
                 qh + b + "napkin",                                        # 10
                 t + b + "logs" + b + ".." + b + "napkin",                 # 11
                 "cd " + t + "robin" + b + "notes",                        # 12: another user's home
                 "C:" + b + "Users/bob",                                   # 13: mixed separators
                 "c:/" + "users" + b + "bob",                              # 14
                 '"' + t + b + b + "napkin" + b + b + 'notes.md"',         # 15: JSON or JS escaped
                 '"' + dh + b + b + 'napkin"',                             # 16
                 dh + "//napkin",                                          # 17: repeated separators
                 t + "//napkin",                                           # 18
                 t + "///napkin",                                          # 19
                 t + "//logs//../napkin",                                  # 20
                 t + b + ".config" + b + "gatherlane" + b + "env",         # 21: flagged on purpose
                 t + b + "Library" + b + "Caches" + b + "ms-playwright" + b + "x",  # 22: likewise
                 t + "/logs" + b + "agent.log",                            # 23..: allowed, or a name
                 t + b + "logs" + b + "agent.log",
                 t + "//logs/agent.log",
                 t + "//gatherlane/env",
                 t + b + b + "gatherlane" + b + b + "env",
                 t + "//.config/gatherlane/env",
                 t + "/gatherlane/..x" + b + "y",
                 t + "/gatherlane" + b + "..x/y",
                 "a" + b + t + "x and " + dh + " alone"]
        with open(os.path.join(d, "a.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        self.assertEqual(ep.scan(["a.md"], d, set()),
                         ["a.md:1: " + t + "/logs", "a.md:2: " + t + "/logs", "a.md:3: " + t + "/logs",
                          "a.md:4: " + t + "/gatherlane", "a.md:5: " + t + "/logs",
                          "a.md:6: " + t + "/gatherlane", "a.md:7: " + t + b + "napkin",
                          "a.md:8: " + dh + b + "napkin", "a.md:9: " + bh + b + "napkin",
                          "a.md:10: " + qh + b + "napkin", "a.md:11: " + t + b + "logs",
                          "a.md:12: " + t + "robin" + b, "a.md:13: C:" + b + "Users/",
                          "a.md:14: c:/" + "users" + b, "a.md:15: " + t + b + b + "napkin",
                          "a.md:16: " + dh + b + b + "napkin", "a.md:17: " + dh + "//napkin",
                          "a.md:18: " + t + "//napkin", "a.md:19: " + t + "///napkin",
                          "a.md:20: " + t + "//logs", "a.md:21: " + t + b + ".config",
                          "a.md:22: " + t + b + "Library"])

    def test_names_reads_config(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "c"))
        with open(os.path.join(d, "c", "config.js"), "w") as f:
            f.write("""  G.GATHERLANE_CONFIG = {
    statusRepo: 'myorg/gatherlane',
    maintainer: 'robin',
    operations: {
      shop: { name: 'Shop', level: 'shop', repos: ['myorg/storefront'], agentPrefixes: ['till'] },
    },
    agents: {
      'shop/cashier': { role: 'x', runbook: null, repo: 'myorg/storefront', note: 'Prompt: """ + "~" + """/x (local)' },
    },
  };""")
        self.assertEqual(ep.names("c/config.js", d), {"myorg", "gatherlane", "robin", "shop", "storefront", "till"})


if __name__ == "__main__":
    unittest.main()
