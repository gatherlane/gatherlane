#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Inline app/ into one self-contained preview page (SAMPLE data only, no settings)."""
import re, sys, pathlib
root = pathlib.Path(__file__).resolve().parent.parent / "app"
html = (root / "index.html").read_text()
body = html.split("<body>", 1)[1].split("</body>", 1)[0]
scripts = re.findall(r'<script src="([^"]+)"></script>', body)
body = re.sub(r'<script src="[^"]+"></script>\s*', "", body)
js = "\n".join((root / s).read_text() for s in scripts)
css = (root / "styles.css").read_text()
out = f"""<title>Gatherlane</title>
<style>{css}</style>
{body}
<script>window.GL_PREVIEW = true;</script>
<script>{js}</script>
"""
dest = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "gatherlane-preview.html")
dest.write_text(out)
print(dest, len(out))
