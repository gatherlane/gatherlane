# SPDX-License-Identifier: Apache-2.0
# Running the office in Docker (compose.yaml, deploy/nginx.conf) must send the same headers that
# app/_headers gives Cloudflare Pages, and must stay on loopback with its hardening in place.
#
# - NginxHeaders reads both files and fails when they drift apart. Standard library only.
# - ComposeConfig asks `docker compose config` for the resolved service. It runs wherever docker
#   is installed and skips where it is not, unless GATHERLANE_DOCKER_URL is set.
# - Served fetches from a running container at GATHERLANE_DOCKER_URL (for example
#   http://127.0.0.1:8080 after `docker compose up -d --wait`) and skips when that is unset.
# Run: python3 -m unittest discover -s tests
import itertools, json, os, re, shutil, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADERS_FILE = os.path.join(ROOT, "app", "_headers")
NGINX_CONF = os.path.join(ROOT, "deploy", "nginx.conf")
URL = os.environ.get("GATHERLANE_DOCKER_URL", "").rstrip("/")
# The location in deploy/nginx.conf that refuses any path with a byte outside ASCII, as the
# tokenizer below reads it (quotes dropped, backslashes kept for PCRE).
NON_ASCII_LOCATION = "location ~ [\\x80-\\xFF]"
# The live tests below write probe files into this checkout's app/, the directory the container
# serves, and delete them afterwards. .gitignore lists the names, because a run killed mid-test
# leaves them behind (tests/test_gitignore.py checks every name probe_names can make).
PROBE_PREFIX = "gatherlane-probe"
_probe_count = itertools.count()


def probe_tag():
    """A probe name new on every call: the process id keeps two runs at once against one checkout
    from writing, serving or deleting each other's files, the time in milliseconds keeps a run
    from reusing a name Docker Desktop may still answer "no such file" for, a moment after the
    previous run deleted it, and the count keeps two tests in one run apart."""
    return "%s-%d-%d-%d" % (PROBE_PREFIX, os.getpid(), int(time.time() * 1000), next(_probe_count))


def write_probe(path):
    """Create one probe file. Mode x makes a name collision a loud FileExistsError, before the
    caller records the path for cleanup, so a run never overwrites or deletes another run's file."""
    with open(path, "x", encoding="utf-8") as f:
        f.write("probe\n")


# Appended to a probe's entry in the non-ASCII walk, so a leftover is not mistaken for a real file.
PROBE_NOTE = (" (a Docker test probe: a live run of Served was killed, or is running now against this"
              " checkout; delete it once no run is)")


def non_ascii(name):
    return any(ord(c) > 0x7F for c in name)


def non_ascii_paths(top_dir):
    """How many names are under top_dir, and every one of them with a non-ASCII byte, relative to
    top_dir. Nothing is skipped: a probe is reported like any other file, with PROBE_NOTE."""
    seen, bad = 0, []
    for top, dirs, files in os.walk(top_dir):
        for name in dirs + files:
            seen += 1
            if non_ascii(name):
                rel = os.path.relpath(os.path.join(top, name), top_dir)
                bad.append(rel + (PROBE_NOTE if re.match(r"\.?" + PROBE_PREFIX + "-[0-9]", name) else ""))
    return seen, bad


def probe_names(tag):
    """Every file under app/ the live tests write for one tag, relative to app/."""
    return {"plain": tag + ".txt", "non_ascii": tag + "-\u00e9.txt",
            "dotfile": "." + tag, "nested_dotfile": "js/." + tag}


def parse_headers_file(text):
    """Cloudflare Pages _headers: a path rule on its own line, then indented "Name: value" lines.
    Returns {rule: [(name, value), ...]} in file order."""
    rules, rule = {}, None
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            rule = line.strip()
            rules[rule] = []
            continue
        if rule is None or ":" not in line:
            raise ValueError("_headers line %d is not a header under a rule: %r" % (n, line))
        name, value = line.split(":", 1)
        rules[rule].append((name.strip(), value.strip()))
    return rules


def nginx_tokens(text):
    """nginx config as tokens, with comments dropped and quoted strings kept whole (unquoted)."""
    pat = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(#[^\n]*)|([{};])|([^\s{};"\'#]+)')
    out = []
    for m in pat.finditer(text):
        dq, sq, comment, punct, word = m.groups()
        if comment is not None:
            continue
        out.append(dq if dq is not None else sq if sq is not None else punct or word)
    return out


def nginx_directives(text):
    """Every simple directive as (enclosing blocks, name, args). Blocks are named by their opening
    directive and its arguments, for example ('http', 'server', 'location = /_headers')."""
    blocks, words, found = [], [], []
    for tok in nginx_tokens(text):
        if tok == "{":
            blocks.append(" ".join(words))
            words = []
        elif tok == "}":
            if words:
                raise ValueError("directive without ; before }: %r" % words)
            blocks.pop()
        elif tok == ";":
            found.append((tuple(blocks), words[0], words[1:]))
            words = []
        else:
            words.append(tok)
    if blocks or words:
        raise ValueError("unbalanced nginx config")
    return found


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def expected_headers():
    rules = parse_headers_file(read(HEADERS_FILE))
    return rules


class NginxHeaders(unittest.TestCase):
    def setUp(self):
        self.rules = expected_headers()
        self.directives = nginx_directives(read(NGINX_CONF))
        self.adds = [(b, args) for b, name, args in self.directives if name == "add_header"]

    def test_headers_file_has_one_rule_for_every_path(self):
        """deploy/nginx.conf maps the rule "/*" onto the whole server. A second rule, or a narrower
        one, needs its own location blocks there, so this fails until someone writes them."""
        self.assertEqual(list(self.rules), ["/*"])
        self.assertTrue(self.rules["/*"], "_headers sets no header")

    def test_nginx_sends_exactly_the_headers_file(self):
        want = self.rules["/*"]
        got = [(args[0], args[1]) for _, args in self.adds]
        self.assertEqual(sorted(got), sorted(want),
                         "deploy/nginx.conf add_header lines and app/_headers have drifted apart")

    def test_each_header_once_and_always(self):
        names = [args[0].lower() for _, args in self.adds]
        self.assertEqual(len(names), len(set(names)), "a header is added twice")
        for _, args in self.adds:
            self.assertEqual(args[2:], ["always"], "%s must be sent on error responses too" % args[0])

    def test_headers_are_set_on_the_server_only(self):
        """A location with any add_header of its own drops every inherited one, so the headers live
        on the server block and no location adds one."""
        for blocks, args in self.adds:
            self.assertEqual(blocks, ("http", "server"), "%s is set in %s" % (args[0], " > ".join(blocks)))

    def test_serves_app_only_without_listing(self):
        d = {(b, n): a for b, n, a in self.directives}
        server = ("http", "server")
        self.assertEqual(d[(server, "root")], ["/usr/share/nginx/html"])
        self.assertEqual(d[(server, "autoindex")], ["off"])
        self.assertNotIn("on", [a[0] for b, n, a in self.directives if n == "autoindex"])
        locations = {b[2]: a for b, n, a in self.directives if len(b) == 3 and n == "return"}
        # ~* folds ASCII letters, so /_HEADERS is refused (on a Mac the bind mount opens the file).
        self.assertEqual(locations.get("location ~* ^/_headers$"), ["404"])
        # Any non-ASCII byte: the Mac bind mount also folds Unicode (/_header%C5%BF), which ~* does not.
        self.assertEqual(locations.get(NON_ASCII_LOCATION), ["404"])
        self.assertEqual(locations.get("location ~ /\\."), ["404"])

    def test_app_has_no_non_ascii_path(self):
        """The non-ASCII location refuses every such path, so a file with such a name under app/
        would be silently unreachable. Fails on every one, probes included, so the rule cannot hide
        a real file; a probe is named as one, so the failure says what to do about it."""
        self.assertTrue(non_ascii("_header\u017f"), "control: the check sees a non-ASCII name")
        self.assertFalse(non_ascii("_headers"), "control: the check passes an ASCII name")
        seen, bad = non_ascii_paths(os.path.join(ROOT, "app"))
        self.assertGreater(seen, 0, "control: app/ was walked")
        self.assertEqual(bad, [], "deploy/nginx.conf refuses non-ASCII paths, so these are never served")

    def test_non_ascii_paths_names_a_probe(self):
        """A probe left by a killed live run (or one a live run is using right now) still fails the
        walk above, and its entry says so, while a real file with a probe-like name does not get the
        probe note (the rule is .gitignore's: the prefix, a hyphen, then a digit). Control: an ASCII
        probe is not reported at all."""
        d = tempfile.mkdtemp()
        try:
            tag = probe_tag()
            os.makedirs(os.path.join(d, "js"))
            for name in (probe_names(tag)["non_ascii"], "js/caf\u00e9.js", "gatherlane-prober-\u00e9.js",
                         "gatherlane-probe-notes-\u00e9.js", probe_names(tag)["plain"]):
                with open(os.path.join(d, name), "x", encoding="utf-8") as f:
                    f.write("x\n")
            seen, bad = non_ascii_paths(d)
            self.assertEqual(seen, 6)
            self.assertEqual(sorted(bad), sorted([
                probe_names(tag)["non_ascii"] + PROBE_NOTE, os.path.join("js", "caf\u00e9.js"),
                "gatherlane-prober-\u00e9.js", "gatherlane-probe-notes-\u00e9.js"]))
        finally:
            shutil.rmtree(d)

    def test_no_version_and_no_ranges(self):
        """server_tokens off keeps the nginx version out of Server and error pages. max_ranges 0
        answers a Range request with the whole file, so there is no 416, on which nginx would send
        every header twice."""
        d = {(b, n): a for b, n, a in self.directives}
        self.assertEqual(d.get((("http",), "server_tokens")), ["off"])
        self.assertEqual(d.get((("http", "server"), "max_ranges")), ["0"])
        for n in ("server_tokens", "max_ranges"):
            self.assertEqual(len([1 for b, name, a in self.directives if name == n]), 1, n)

    def test_parser_sees_a_drift(self):
        """Control: the comparison above fails when one value changes, so it is not vacuous."""
        text = read(NGINX_CONF).replace('"no-referrer"', '"same-origin"')
        self.assertNotEqual(text, read(NGINX_CONF), "control did not change the config")
        got = sorted((a[0], a[1]) for _, n, a in nginx_directives(text) if n == "add_header")
        self.assertNotEqual(got, sorted(self.rules["/*"]))


class ProbeNames(unittest.TestCase):
    """The live tests below write into the served app/, so their file names must differ between
    two runs at once against one checkout, and between two tests in one run. Standard library
    only, no container needed."""

    def test_tags_differ_within_a_run(self):
        tags = [probe_tag() for _ in range(3)]
        self.assertEqual(len(set(tags)), 3, tags)
        for tag in tags:
            self.assertTrue(tag.startswith(PROBE_PREFIX + "-%d-" % os.getpid()), tag)

    def test_tags_differ_between_runs_at_once(self):
        """Another process started in the same millisecond still gets another name."""
        code = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('t', sys.argv[1]); "
                "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "m.time.time = lambda: 1.0; print(m.probe_tag())")
        here = os.path.abspath(__file__)
        tags = [subprocess.run([sys.executable, "-I", "-c", code, here], capture_output=True, text=True,
                               check=True).stdout.strip() for _ in range(2)]
        self.assertTrue(all(t.startswith(PROBE_PREFIX + "-") for t in tags), tags)
        self.assertNotEqual(tags[0], tags[1])

    def test_a_collision_is_loud(self):
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, probe_tag() + ".txt")
            write_probe(path)
            with open(path, "w", encoding="utf-8") as f:
                f.write("another run\n")
            with self.assertRaises(FileExistsError):
                write_probe(path)
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "another run\n", "the other run's file is left as it was")
        finally:
            shutil.rmtree(d)

    def test_names_share_the_tag(self):
        tag = probe_tag()
        names = probe_names(tag)
        self.assertEqual(len(set(names.values())), len(names), names)
        for name in names.values():
            self.assertIn(tag, os.path.basename(name))


def docker_compose_available():
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0


class ComposeConfig(unittest.TestCase):
    def setUp(self):
        if not docker_compose_available():
            if URL:
                self.fail("GATHERLANE_DOCKER_URL is set but docker compose is not available")
            self.skipTest("docker compose not installed")

    def config(self, **env):
        r = subprocess.run(["docker", "compose", "config", "--format", "json"], cwd=ROOT,
                           capture_output=True, text=True, env=dict(os.environ, **env))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["services"]["office"]

    def test_loopback_only(self):
        s = self.config(GATHERLANE_HTTP_PORT="8080")
        self.assertEqual([(p["host_ip"], str(p["published"]), p["target"]) for p in s["ports"]],
                         [("127.0.0.1", "8080", 8080)])

    def test_port_override_keeps_loopback(self):
        s = self.config(GATHERLANE_HTTP_PORT="18080")
        self.assertEqual([(p["host_ip"], str(p["published"])) for p in s["ports"]], [("127.0.0.1", "18080")])

    def test_no_host_network_or_privilege(self):
        """network_mode: host would publish nginx on every host address and ignore ports:, and
        privileged, cap_add or a root user would undo the hardening below."""
        s = self.config()
        for key in ("network_mode", "privileged", "cap_add", "pid", "ipc", "devices", "userns_mode"):
            self.assertNotIn(key, s, key)
        self.assertEqual(s.get("user"), "101:101")

    def test_healthcheck_proves_app_is_mounted(self):
        """The image ships its own index.html, so the check fetches a file only app/ has."""
        self.assertTrue(os.path.exists(os.path.join(ROOT, "app", "js", "app.js")))
        h = self.config().get("healthcheck") or {}
        self.assertFalse(h.get("disable"), h)
        self.assertEqual(h.get("test"), ["CMD", "wget", "-q", "-U", "gatherlane-healthcheck", "-O", "/dev/null",
                                         "http://127.0.0.1:8080/js/app.js"], h)

    def test_hardening_and_limits(self):
        s = self.config()
        self.assertIs(s.get("read_only"), True)
        self.assertEqual(s.get("cap_drop"), ["ALL"])
        # Exactly this list: an extra seccomp=unconfined or apparmor=unconfined would undo isolation.
        self.assertEqual(s.get("security_opt"), ["no-new-privileges:true"])
        self.assertEqual(s.get("restart"), "unless-stopped")
        limits = s["deploy"]["resources"]["limits"]
        self.assertTrue(0 < float(limits["cpus"]) <= 1, limits)
        self.assertTrue(0 < int(limits["memory"]) <= 256 * 1024 * 1024, limits)
        self.assertTrue(0 < int(limits["pids"]) <= 256, limits)
        self.assertEqual(s["logging"]["options"], {"max-size": "10m", "max-file": "3"})
        self.assertRegex(s["image"], r"^nginxinc/nginx-unprivileged:\d+\.\d+\.\d+-alpine")

    def test_mounts_are_read_only(self):
        s = self.config()
        mounts = {v["target"]: v for v in s["volumes"]}
        self.assertEqual(set(mounts), {"/usr/share/nginx/html", "/etc/nginx/nginx.conf"})
        for target, v in mounts.items():
            self.assertIs(v.get("read_only"), True, target)
        self.assertEqual(os.path.realpath(mounts["/usr/share/nginx/html"]["source"]), os.path.realpath(os.path.join(ROOT, "app")))
        self.assertEqual(os.path.realpath(mounts["/etc/nginx/nginx.conf"]["source"]), os.path.realpath(NGINX_CONF))


class Served(unittest.TestCase):
    """Against a running container. In CI the docker job starts one and sets GATHERLANE_DOCKER_URL."""

    def setUp(self):
        if not URL:
            self.skipTest("GATHERLANE_DOCKER_URL not set")

    def get(self, path, **headers):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL + path, headers=headers), timeout=5) as r:
                return r.status, r.headers
        except urllib.error.HTTPError as e:
            e.close()
            return e.code, e.headers

    def assert_headers(self, headers, path):
        for name, value in expected_headers()["/*"]:
            self.assertEqual(headers.get_all(name), [value], "%s on %s" % (name, path))

    def test_page_and_script_carry_every_header(self):
        for path in ("/", "/js/app.js"):
            status, headers = self.get(path)
            self.assertEqual(status, 200, path)
            self.assert_headers(headers, path)
        self.assertIn("javascript", self.get("/js/app.js")[1].get("Content-Type", ""))

    def test_headers_file_not_served(self):
        """On a Mac the bind mount folds case, ASCII and Unicode alike, so /_HEADERS is the file and
        so is /_header%C5%BF (U+017F, long s, folds to s)."""
        self.assertTrue(os.path.exists(HEADERS_FILE))
        for path in ("/_headers", "/_HEADERS", "/_Headers", "/_header%C5%BF", "/_HEADER%C5%BF"):
            status, headers = self.get(path)
            self.assertEqual(status, 404, path)
            self.assert_headers(headers, path)

    def test_non_ascii_path_not_served(self):
        """A file with a non-ASCII name that exists in app/ is refused, while the same file with an
        ASCII name is served, so the 404 comes from the non-ASCII rule and not from a missing file.
        A URI that is not valid UTF-8 is a 404 as well, not a 500. Needs app/ mounted from this
        checkout, which compose.yaml does. The names are new on every run (probe_tag)."""
        made, tag = [], probe_tag()
        names = probe_names(tag)
        try:
            for name in (names["plain"], names["non_ascii"]):
                path = os.path.join(ROOT, "app", name)
                write_probe(path)
                made.append(path)
            self.assertEqual(self.get("/" + tag + ".txt")[0], 200, "control: the mount is live")
            for path in ("/" + tag + "-%C3%A9.txt", "/_header%FF", "/js/app%C5%BF.js"):
                status, headers = self.get(path)
                self.assertEqual(status, 404, path)
                self.assert_headers(headers, path)
        finally:
            for path in made:
                os.remove(path)

    def test_range_request_gets_the_whole_file_once(self):
        """max_ranges 0: no 416 for a range past the end, and each header exactly once."""
        status, headers = self.get("/index.html", Range="bytes=999999999-")
        self.assertEqual(status, 200)
        self.assert_headers(headers, "/index.html with Range")

    def test_no_directory_listing(self):
        status, headers = self.get("/js/")
        self.assertEqual(status, 403)
        self.assert_headers(headers, "/js/")

    def test_dotfiles_not_served(self):
        """A dotfile that exists in app/ is refused, while the same file without the dot is served,
        so the 404 comes from the dotfile rule and not from a missing file. Needs app/ mounted from
        this checkout, which compose.yaml does. The names are new on every run (probe_tag), so two
        runs at once against one checkout do not delete each other's files mid-test."""
        made, names = [], probe_names(probe_tag())
        try:
            for name in (names["plain"], names["dotfile"], names["nested_dotfile"]):
                path = os.path.join(ROOT, "app", name)
                write_probe(path)
                made.append(path)
            self.assertEqual(self.get("/" + names["plain"])[0], 200, "control: the mount is live")
            for path in ("/" + names["dotfile"], "/" + names["nested_dotfile"]):
                status, headers = self.get(path)
                self.assertEqual(status, 404, path)
                self.assert_headers(headers, path)
        finally:
            for path in made:
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
