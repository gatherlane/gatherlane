#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the public copy of Gatherlane from this repository, with a fresh history.

  python3 tools/export_public.py OUTDIR [--identity "Name <email>"] [--no-commit]

Takes the committed tree (git archive HEAD), drops the private parts (app/instance/ and growth/),
puts examples/instance/ in app/instance/, and scans every file for the names the private
instance uses (repo owners and names, operations, agent id prefixes, the maintainer) and for
home-directory paths. If anything is found it stops and lists it. Otherwise it makes OUTDIR a git
repository with one commit, made as --identity when given (for example a GitHub noreply address,
so a personal email does not become public) and as your git identity otherwise. It never pushes.
"""
import argparse, io, os, re, shutil, subprocess, sys, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE = ("app/instance/", "growth/")
PATHS = re.compile("|".join(["/" + "Users/", r"/home/\w", "~/" + "Projects"]))  # split so this line does not match itself
PAIR = r"'([\w.-]+)/([\w.-]+)'"


def read(path, root=ROOT):
    with open(os.path.join(root, path), encoding="utf-8") as f:
        return f.read()


def names(config_path, root=ROOT):
    """The names an instance's config.js uses, lower-cased, four characters or longer."""
    text = read(config_path, root)
    arrays = re.findall(r"\[([^\]]*)\]", text)                                # repos, roomRepos, agentPrefixes, dayParts
    repos = [m for a in arrays for m in re.findall(PAIR, a)]
    repos += re.findall(r"(?:repo|statusRepo):\s*" + PAIR, text)              # repo: 'o/r'
    repos += re.findall(r"\w+\(" + PAIR + r"\)", text)                        # RB('o/r')
    repos += [tuple(u.split("/")) for u in re.findall(r"github\.com/([\w.-]+/[\w.-]+)", text)]
    out = {part for pair in repos for part in pair}
    out.update(w for a in arrays for w in re.findall(r"'([\w.-]+)'", a))       # single words in arrays
    ops = re.search(r"operations:\s*{(.*?)\n    },", text, re.S)
    out.update(re.findall(r"^\s{6}([\w-]+):\s*{", ops.group(1), re.M) if ops else [])
    agents = text[text.find("agents: {"):]                                        # agent ids: keys of agents
    out.update(i.split("/")[0] for i in re.findall(r"^\s+'([\w./-]+)':\s*{", agents, re.M))
    out.update(re.findall(r"maintainer:\s*'([\w.-]+)'", text))
    return {n.lower() for n in out if len(n) >= 4}


def private_terms(root=ROOT):
    return names("app/instance/config.js", root) - names("examples/instance/config.js", root)


def scan(files, root, terms, paths=True):
    """Lines in files that name a term (as a whole word) or, with paths, a home directory."""
    pattern = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, sorted(terms))) + r")(?![\w-])", re.I) if terms else None
    hits = []
    for f in files:
        try:
            text = read(f, root)
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            m = (pattern and pattern.search(line)) or (paths and PATHS.search(line))
            if m:
                hits.append(f"{f}:{n}: {m.group(0)}")
    return hits


def export(out, commit=True, identity=None):
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"{out} exists and is not empty")
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        print("note: uncommitted changes are not exported; only HEAD is", file=sys.stderr)
    terms = private_terms()
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    os.makedirs(out, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        members = [m for m in t.getmembers() if not (m.name + "/").startswith(PRIVATE)]  # tarfile drops a dir's trailing /
        safe = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}  # 3.12+; older Pythons extract as before
        t.extractall(out, members=members, **safe)
    shutil.copytree(os.path.join(out, "examples", "instance"), os.path.join(out, "app", "instance"))
    files = [os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(out) for f in fs]
    hits = scan(files, out, terms)
    if hits:
        print("private names or paths in the export; nothing committed:", *hits, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    print(f"{out}: {len(files)} files, scanned for {len(terms)} private names and home paths, none found")
    if commit:
        env = dict(os.environ)
        if identity:
            m = re.fullmatch(r"\s*(.+?)\s*<([^<>\s]+@[^<>\s]+)>\s*", identity)
            if not m:
                sys.exit(f'--identity must look like "Name <email>", got {identity!r}')
            for who in ("AUTHOR", "COMMITTER"):
                env[f"GIT_{who}_NAME"], env[f"GIT_{who}_EMAIL"] = m.groups()
        git = lambda *a: subprocess.run(["git", *a], cwd=out, check=True, capture_output=True, env=env)
        git("init", "-b", "main")
        git("add", "-A")
        git("commit", "-m", "Gatherlane: first public commit")
        print(subprocess.run(["git", "log", "-1", "--format=%h %an <%ae> %s"], cwd=out, capture_output=True, text=True).stdout.strip())
        print("Review it, then add the public remote and push yourself.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--no-commit", action="store_true", help="build and scan only")
    ap.add_argument("--identity", help='author and committer of the first commit, "Name <email>"')
    a = ap.parse_args()
    export(a.out, commit=not a.no_commit, identity=a.identity)


if __name__ == "__main__":
    main()
