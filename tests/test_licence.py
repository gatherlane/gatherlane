# SPDX-License-Identifier: Apache-2.0
# Every source file outside app/instance/ carries the SPDX licence line near the top.
import os, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = "SPDX-License-Identifier: Apache-2.0"


class LicenceHeaders(unittest.TestCase):
    def test_source_files_carry_spdx(self):
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        missing = []
        for f in files:
            if f.startswith("app/instance/") or not f.endswith((".js", ".py", ".css", ".html")):
                continue
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                head = "".join(fh.readline() for _ in range(3))
            if TAG not in head:
                missing.append(f)
        self.assertEqual(missing, [], "add the SPDX line to: " + ", ".join(missing))

    def test_licence_file(self):
        with open(os.path.join(ROOT, "LICENSE"), encoding="utf-8") as fh:
            self.assertIn("Apache License", fh.read(200))


if __name__ == "__main__":
    unittest.main()
