# SPDX-License-Identifier: Apache-2.0
# The engine, docs and examples must not name anything that belongs to one instance.
# Takes the names app/instance/config.js uses (repo owners, repo names, operations, agent id
# prefixes, the maintainer), drops any the example instance also uses, and looks for the rest in
# every other tracked file, along with the names tools/private-names.txt lists (that list itself is
# not scanned). tools/export_public.py runs the same scan on the public copy.
# Run: python3 -m unittest discover -s tests
import importlib.util, os, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("export_public", os.path.join(ROOT, "tools", "export_public.py"))
ep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep)


class EngineIsGeneric(unittest.TestCase):
    def test_no_instance_names_outside_the_instance(self):
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        files = [f for f in files if not f.startswith("app/instance/") and f != ep.PRIVATE_NAMES and not f.endswith((".png", ".jpg"))]
        hits = ep.scan(files, ROOT, ep.private_terms(), paths=False)
        self.assertEqual(hits, [], "instance names outside app/instance/:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
