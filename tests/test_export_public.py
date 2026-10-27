# SPDX-License-Identifier: Apache-2.0
# tools/export_public.py: the public copy has the example instance, no private parts, and the
# scan catches a leaked name or a home path.
import importlib.util, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "export_public.py")
spec = importlib.util.spec_from_file_location("export_public", TOOL)
ep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep)


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
      'shop/cashier': { role: 'x', runbook: null, repo: 'myorg/storefront', note: 'Prompt: ~/x (local)' },
    },
  };""")
        self.assertEqual(ep.names("c/config.js", d), {"myorg", "gatherlane", "robin", "shop", "storefront", "till"})


if __name__ == "__main__":
    unittest.main()
