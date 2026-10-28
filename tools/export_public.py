#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the public copy of Gatherlane from this repository, with a fresh history.

  python3 tools/export_public.py OUTDIR [--identity "Name <email>"] [--no-commit]

Takes the committed tree (git archive HEAD), drops the private parts (app/instance/, growth/,
CLAUDE.md, .claude/ and tools/private-names.txt), puts examples/instance/ in app/instance/, moves
examples/public-CLAUDE.md to CLAUDE.md (so the public tree has one CLAUDE.md, at the root), and
scans every file for the names the private instance uses (repo owners and names, operations, agent
id prefixes, the maintainer, and every name listed in tools/private-names.txt, which must exist and
list one whenever examples/public-CLAUDE.md is present) as whole words in any letter case, and for
these home-directory paths (PATHS):

  - macOS: Users between slashes, anywhere; and that segment in any letter case where it starts a
    path (not after a letter, digit, underscore, dot or hyphen, so a URL path does not count).
  - Linux: home between slashes followed by a name, anywhere; and root between slashes where it
    starts a path, as above.
  - Windows: a drive letter, a colon and Users with backslashes, in any letter case; and
    USERPROFILE in cmd's percent form or PowerShell's env: form, braced or not, in any letter case.
  - A tilde followed by a user name and a slash: another user's home.
  - A path under the home directory: a tilde, HOME or braced HOME, bare or in double quotes, then
    a slash and a name, unless it is one of the few PUBLIC_HOME allows with no /.. segment after it.

It also refuses every file Claude Code would
load as instructions except the root CLAUDE.md: a CLAUDE.md below the root, a CLAUDE.local.md
anywhere, and anything in a .claude/ directory below the root (names in any letter case). If
anything is found it stops and lists it.
Otherwise it makes OUTDIR a git repository with one commit, made as --identity when given (for
example a GitHub noreply address, so a personal email does not become public) and as your git
identity otherwise. It never pushes.

Run in the public tree, which has neither examples/public-CLAUDE.md nor a private instance, it keeps
the root CLAUDE.md as it is, so the public tree can export itself. A tree with no
examples/public-CLAUDE.md that still has a private instance is refused, with nothing written.
"""
import argparse, io, os, re, shutil, subprocess, sys, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# This repository's own CLAUDE.md names no private term, by design, so the name scan below would
# let it through. It may happen to trip the home-path rule today, but that is incidental and one
# edit away from false. The "CLAUDE.md" entry here, and the tests that pin it, are the guard that
# keeps the private rules out of the public tree: do not drop it on the grounds that the scan
# would catch it.
# Private names that no config.js carries, such as the maintainer's surname: one per line, # for a
# comment. The export reads it and never ships it. It is outside app/, which is all that Pages
# serves, so the private deploy does not serve it either.
PRIVATE_NAMES = "tools/private-names.txt"
PRIVATE = ("app/instance/", "growth/", "CLAUDE.md", ".claude/", PRIVATE_NAMES)
# The public tree's CLAUDE.md. Its source is not named CLAUDE.md, because Claude Code loads a
# CLAUDE.md in any subdirectory as instructions once an agent touches a file there, and this text
# describes the public tree, not this one. The export moves it to the root.
PUBLIC_CLAUDE = "examples/public-CLAUDE.md"
# Home-relative paths the public docs use on purpose: the reporter's env file and its suggested
# clone, a log directory in a cron example, and the Playwright cache. Any other one is a leak,
# and so is an allowed one with a /.. segment after it, which leads back out of it.
PUBLIC_HOME = (r"\.config/gatherlane", "gatherlane", "logs", "Library/Caches/ms-playwright")
_END = r"""(?=/|[\s'"`()<>]|$)"""                                                 # end of a path segment
_ALLOWED = "(?:" + "|".join(PUBLIC_HOME) + r")(?![\w.-])(?![^\s'\"`()<>]*/\.\." + _END + ")"
_HOME = "(?:~|\\$" + "HOME|\\$\\{" + "HOME\\}|\"\\$" + "HOME\"|\"\\$\\{" + "HOME\\}\")/"  # ~/, HOME bare, braced or quoted
# Split so this file does not match itself.
PATHS = re.compile("|".join([
    "/" + "Users/", r"/home/\w",                                                   # macOS, Linux
    r"(?<![\w.-])(?i:/" + "users/)", r"(?<![\w.-])/" + "root/",                     # the same, any case, starting a path; root's home
    r"(?<![\w/])" + _HOME + "(?!" + _ALLOWED + r")[\w.-]+",                        # home-relative
    r"(?<![\w/~])~[A-Za-z_][\w.-]*/",                                              # a tilde and a user name: another user's home
    r"(?i:[a-z]:\\+" + r"users\\+)", "(?i:%" + "USERPROFILE%)",                      # Windows
    r"(?i:\$\{?env:" + "USERPROFILE)",                                              # PowerShell
]))
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


def listed_names(root=ROOT):
    """The names in PRIVATE_NAMES, lower-cased; none when the file is absent, as in the public tree."""
    try:
        text = read(PRIVATE_NAMES, root)
    except FileNotFoundError:
        return set()
    return {w.strip().lower() for w in text.splitlines() if w.strip() and not w.strip().startswith("#")}


def private_terms(root=ROOT):
    return (names("app/instance/config.js", root) - names("examples/instance/config.js", root)) | listed_names(root)


def instruction_files(files):
    """Files Claude Code would load as instructions, other than the root CLAUDE.md: a CLAUDE.md
    below the root, a CLAUDE.local.md anywhere, and anything in a .claude/ directory. Names are
    compared in any letter case, because a case-insensitive file system loads them that way."""
    out = []
    for f in files:
        parts = f.replace(os.sep, "/").split("/")
        name = parts[-1].lower()
        if (name == "claude.md" and f != "CLAUDE.md") or name == "claude.local.md" \
                or ".claude" in (p.lower() for p in parts[:-1]):
            out.append(f)
    return out


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
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        everything = t.getmembers()
        # This repository has PUBLIC_CLAUDE. The public tree does not: its root CLAUDE.md is
        # already the public one, so it ships as it is. That is safe only with no private instance,
        # because a private tree that lost PUBLIC_CLAUDE would otherwise ship its own rules.
        has_source = any(m.name == PUBLIC_CLAUDE for m in everything)
        if not has_source and terms:
            sys.exit(f"no {PUBLIC_CLAUDE} in HEAD, but this tree has a private instance, so its root "
                     "CLAUDE.md is not the public one; nothing written")
        if has_source and not listed_names():
            sys.exit(f"{PRIVATE_NAMES} is missing or empty, so the scan would miss the names in it; nothing written")
        private = PRIVATE if has_source else tuple(p for p in PRIVATE if p != "CLAUDE.md")
        members = [m for m in everything if not (m.name + "/").startswith(private)]  # tarfile drops a dir's trailing /
        safe = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}  # 3.12+; older Pythons extract as before
        os.makedirs(out, exist_ok=True)
        t.extractall(out, members=members, **safe)
    shutil.copytree(os.path.join(out, "examples", "instance"), os.path.join(out, "app", "instance"))
    if has_source:
        os.replace(os.path.join(out, PUBLIC_CLAUDE), os.path.join(out, "CLAUDE.md"))
    files = [os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(out) for f in fs]
    hits, loads = scan(files, out, terms), instruction_files(files)
    if loads:
        print("Claude Code instruction files other than the root CLAUDE.md; nothing committed:",
              *loads, sep="\n  ", file=sys.stderr)
    if hits:
        print("private names or paths in the export; nothing committed:", *hits, sep="\n  ", file=sys.stderr)
    if hits or loads:
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
