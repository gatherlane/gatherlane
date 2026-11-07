# SPDX-License-Identifier: Apache-2.0
# docs/SETUP.md, step 2: the hosting order that keeps app/instance/ from being public.
#
# Pages serves app/instance/config.js (repo names, agents, runbook links) to anyone who reaches
# the site, at <project>.pages.dev, at every custom domain and at each deployment's own
# <hash>.<project>.pages.dev address. Step 2 is a set of flows (first deploy, custom domain, the
# stop path for a domain Access cannot cover, certificate renewal, and three ways to take the
# office offline), and every step in them closes with an HTML comment such as
#   <!-- step custom-domain 2: rollback placeholder -->
# which Markdown does not render. These tests read those comments, replay each flow on a small
# model of a Pages project, and fail when:
#   - a step makes a hostname serve the office while Access does not cover it, or before a
#     private-window check of that hostname has passed, or a flow ends with a hostname serving the
#     office when no check of it has passed while the office served there since its Access
#     application or policy last changed (a check while the placeholder serves does not show
#     that Access covers the office's files);
#   - a check is not followed by what to do when it fails, or a failed check leaves the office
#     public with nowhere to go, or the place it sends the reader is unsafe from there;
#   - Access is added while the office is still public on a production address (take it
#     offline first), or a flow does not reach its end state.
# A light prose check then holds each step's words to its comment (`required_words`: a
# `rollback placeholder` step must say roll back and placeholder, a stop must say stop and not
# "go on" or "you need not stop", a check must name a private window and the Access sign-in),
# and a few actions may be named only in a step whose comment allows them (`GUARDED`): turning
# Access off or removing it, rolling production (Rollback to this deployment, roll forward,
# promote), a push to `main`, ticking or unticking automatic deployments, an `app` output
# directory and adding a custom domain. Rolling forward and adding a domain may be named to
# forbid them ("do not roll forward"). Anywhere in step 2, an Access selector wider than the
# addresses you name (Everyone, Anyone, Bypass, an email domain, a login method) fails unless
# negated (`WEAK_POLICY`). Wording is otherwise free.
# Also: any `python -m http.server` command in a tracked text file binds 127.0.0.1.
# Standard library only. Run: python3 -m unittest discover -s tests
import copy, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(ROOT, "docs", "SETUP.md")

SECTION_HEADING = "## 2. Host it on Cloudflare Pages"

# Hostnames: <project>.pages.dev, *.<project>.pages.dev (every deployment's own address) and the
# custom domain.
HOSTS = ("pages.dev", "*.pages.dev", "domain")
PRODUCTION_HOSTS = ("pages.dev", "domain")
FLOWS = ("first-deploy", "custom-domain", "certificate", "stop-path",
         "offline-placeholder", "offline-rebuild", "offline-delete")
GOTO = {"stop-path": ("stop-path",),
        "take-offline": ("offline-placeholder", "offline-rebuild", "offline-delete")}
TAKES_PUBLIC = ("take-offline",)  # the only place a reader may be sent while the office is public


def _hosts(args):
    return bool(args) and all(a in HOSTS for a in args) and len(set(args)) == len(args)


ARGS = {
    "note": lambda a: not a, "quote": lambda a: not a, "forbid": lambda a: not a,
    "create-project": lambda a: not a, "deploy": lambda a: not a,
    "delete-project": lambda a: not a, "domain-add": lambda a: not a,
    "domain-remove": lambda a: not a,
    "set-build": lambda a: a in (["placeholder"], ["app"]),
    "rollback": lambda a: a in (["placeholder"], ["office"]),
    "auto": lambda a: a in (["on"], ["off"]),
    "access-protect": _hosts, "access-remove": _hosts, "policy": _hosts, "check": _hosts,
    "diagnose": _hosts, "stop-if-fails": _hosts,
    "access-move": lambda a: len(a) == 2 and _hosts(a),
    "repeat": lambda a: len(a) == 2 and a[0] in FLOWS and bool(re.match(r"^\d+-\d+$", a[1])),
}
REMEDY = ("rollback", "auto")

COMMENT = re.compile(r"<!--(.*?)-->", re.S)
STEP = re.compile(r"^step\s+([^:]+):\s*(.+)$", re.S)
LABEL = re.compile(r"^(?:[a-z]+-)?\d+$")  # "5", or "access-5" where a flow spans several lists
LIST_ITEM = re.compile(r"^\s*(?:\d+\.|[-*])\s")


def normalise(text):
    return re.sub(r"\s+", " ", text).strip()


def section(markdown):
    """Step 2 of SETUP.md, from its heading to the next level-two heading, as written.
    Raises ValueError when the heading is missing, so a renamed step fails loudly."""
    start = markdown.find(SECTION_HEADING)
    if start < 0:
        raise ValueError("no %r heading" % SECTION_HEADING)
    end = markdown.find("\n## ", start + len(SECTION_HEADING))
    return markdown[start:] if end < 0 else markdown[start:end]


def rendered(markdown):
    """Step 2 as a reader sees it: comments gone, whitespace collapsed."""
    return normalise(COMMENT.sub("", section(markdown)))


def blocks(text):
    """Paragraphs and list items: a blank line or a new list item starts a block."""
    out, cur = [], []
    for line in text.split("\n"):
        if not line.strip() or LIST_ITEM.match(line):
            if cur:
                out.append("\n".join(cur))
            cur = [line] if line.strip() else []
        else:
            cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


class Action(object):
    def __init__(self, verb, args, remedy=(), goto=None):
        self.verb, self.args, self.remedy, self.goto = verb, list(args), list(remedy), goto

    def __repr__(self):
        text = " ".join([self.verb] + self.args)
        if self.remedy or self.goto:
            text += " -> " + "; ".join([" ".join([a.verb] + a.args) for a in self.remedy]
                                       + (["goto " + self.goto] if self.goto else []))
        return text


class Tag(object):
    def __init__(self, flows, actions, span, block, raw):
        self.flows, self.actions, self.span, self.block, self.raw = flows, actions, span, block, raw

    def verbs(self):
        return set(a.verb for a in self.actions) | set(r.verb for a in self.actions for r in a.remedy)


def _action(text, problems, raw):
    words = text.split()
    if not words or words[0] not in ARGS or not ARGS[words[0]](words[1:]):
        problems.append("unreadable step %r in %r" % (text, raw))
        return None
    return Action(words[0], words[1:])


def parse_tag(body, problems, span, block):
    m = STEP.match(body)
    if not m:
        problems.append("a comment in step 2 is neither `step ...` nor `about: ...`: %r" % body[:60])
        return None
    flows = []
    for part in m.group(1).split(","):
        words = part.split()
        if not words or words[0] not in FLOWS or len(words) > 2 or (
                len(words) == 2 and not LABEL.match(words[1])):
            problems.append("unknown flow %r in %r" % (part.strip(), body))
            return None
        flows.append((words[0], words[1] if len(words) == 2 else ""))
    left, _, right = m.group(2).partition("->")
    actions = [_action(t.strip(), problems, body) for t in left.split(";")]
    if None in actions:
        return None
    if right:
        last = actions[-1]
        if last.verb != "stop-if-fails":
            problems.append("only stop-if-fails takes `->`: %r" % body)
            return None
        for t in right.split(";"):
            words = t.split()
            if words[:1] == ["goto"] and len(words) == 2 and words[1] in GOTO and last.goto is None:
                last.goto = words[1]
                continue
            a = _action(t.strip(), problems, body)
            if a is None or a.verb not in REMEDY or last.goto:
                problems.append("bad remedy %r in %r" % (t.strip(), body))
                return None
            last.remedy.append(a)
    return Tag(flows, actions, span, block, body)


def parse(markdown):
    """(tags in document order, segments, problems). A segment is (text, owning tag or None):
    the words a tag closes, or the untagged rest of a block."""
    problems, tags, segments = [], [], []
    for n, line in enumerate(markdown.split("\n"), 1):
        if re.match(r"\s*<!--\s*step\b", line):
            problems.append("line %d starts with a step comment, which Markdown renders as a raw "
                            "HTML block; end the words before it on the same line" % n)
    sec = section(markdown)
    if markdown.count("<!--") != markdown.count("-->"):
        problems.append("an HTML comment is not closed")
    outside = COMMENT.findall(markdown.replace(sec, ""))
    if any(re.match(r"\s*step\b", c) for c in outside):
        problems.append("a step comment sits outside step 2")
    for body in COMMENT.findall(sec):
        if "--" in body or body.endswith("-"):
            problems.append("a comment holds `--`, which some Markdown renderers show: %r" % body[:60])
    for b, block in enumerate(blocks(sec)):
        pos, has_tag = 0, False
        for m in COMMENT.finditer(block):
            body = normalise(m.group(1))
            span = normalise(block[pos:m.start()])
            pos = m.end()
            if body.startswith("about:"):
                if span:
                    segments.append((span, None))
                continue
            tag = parse_tag(body, problems, span, b)
            if tag is None:
                continue
            has_tag = True
            tags.append(tag)
            segments.append((span, tag))
        tail = normalise(block[pos:])
        if tail:
            segments.append((tail, None))
        if re.match(r"\s*\d+\.\s", block) and not has_tag:
            problems.append("a numbered step has no step comment: %r" % normalise(block)[:70])
    return tags, segments, problems


# ---- the prose a step's words must carry ------------------------------------------------------

PRIVATE = r"private\W{0,3}(?:\([^)]{0,20}\)\W{0,3})?window|incognito"
SIGN_IN = r"Access (?:sign-?in|sign in|log-?in)"
ROLLBACK_UI = r"Roll ?back to this deployment"
ADDRESS = {"pages.dev": r"https://<project>\.pages\.dev/", "*.pages.dev": r"<hash>\.<project>\.pages\.dev",
           "domain": r"office\.example\.com|\beach custom domain\b"}
NAME = {"pages.dev": r"`<project>\.pages\.dev`", "*.pages.dev": r"`\*\.<project>\.pages\.dev`",
        "domain": r"\bdomain\b"}
NEGATION = re.compile(r"\b(?:do not|don't|does not|doesn't|never|skip|instead of|no (?:need|reason) to"
                      r"|need not|needn't|not (?:necessary|needed|required)|optional\w*"
                      r"|if you (?:like|want|wish|have time))\b[^.:;]{0,25}$", re.I)
CARRY_ON = re.compile(r"(?<!not )(?<!n't )\b(?:go on|carry on|continue|proceed|move on)\b|\banyway\b"
                      r"|\b(?:do not|don't|never) (?:worry|panic|mind)\b|\bstop worrying\b"
                      r"|\b(?:is|are) (?:fine|expected|normal|harmless|safe)\b|\bignore\b|\bmay be cached\b",
                      re.I)
# "In a private window or your usual one": a signed-in window shows the office whether or not it is
# public, so a check offers no other window.
OTHER_WINDOW = r"(?:window|incognito)\W{0,3}or\b(?!\s+(?:an?\s+)?(?:incognito|private)\b)"
STOPS = r"\b(?:stop|follow|roll back|do not (?:deploy|go on|roll forward))\b"
FORBID = re.compile(r"^(?:Never|Do not|Don't)\s+do\s+(?:that|this)\b[^.]*\bproduction\b")
OTHER_APPS = re.compile(r"pages\.dev|\bapplications\b|\ball\b|\bboth\b|\bproject's\b|\bothers?\b|\bevery\b",
                        re.I)
REMEDY_WORDS = {("rollback", "placeholder"): [r"\broll\w* back\b", r"\bplaceholder\b"],
                ("auto", "off"): [r"\b(?:untick|clear|pause)\b"]}
GOTO_WORDS = {"stop-path": "If the domain cannot go behind Access",
              "take-offline": "Is my office public right now?"}
# "Even if Custom domains still lists it, roll forward": a roll forward must not be made conditional
# on nothing.
ROLL_ANYWAY = r"\b(?:even if|even though|whether or not|regardless|still lists?|still shows?|anyway)\b"
IMPERATIVE = ("set-build", "deploy", "access-protect", "access-move", "access-remove", "rollback",
              "auto", "domain-add", "domain-remove", "delete-project", "check", "create-project",
              "policy", "stop-if-fails")


def required_words(action):
    """Patterns (case-insensitive) the step's words must hold, and ones they must not."""
    v, a = action.verb, action.args
    need, never = [], []
    if v == "create-project":
        need = [r"\bcreat\w* the project\b"]
    elif v == "set-build":
        other = "app" if a[0] == "placeholder" else "placeholder"
        need, never = [r"\boutput\b", r"`?%s`?" % a[0]], [r"`%s`" % other]
        if a[0] == "placeholder":  # a build command that brings in app/ brings in app/instance/
            never.append(r"`[^`]*\bapp\b[^`]*`")
    elif v == "deploy":
        need = [r"\bpush\b"]
    elif v == "access-protect":
        need = [r"\bAccess\b|Enable access policy"] + [NAME[h] for h in a]
    elif v == "access-move":
        need = [r"\b(?:delet|remov)\w* the `\*`", r"\bSubdomain\b", NAME[a[1]]]
    elif v == "access-remove":
        need = [r"\bdomain's (?:own )?Access application\b" if h == "domain" else NAME[h] for h in a]
        if a == ["domain"]:
            never = [OTHER_APPS]
    elif v == "policy":
        # "as above" sends the reader back to a policy step these words hold; WEAK_POLICY holds
        # every step against a selector that lets in more than the addresses named.
        need = [r"\bAction\W{0,6}Allow\b|\bas above\b",
                r"\bInclude\W{0,6}Emails\b[^.]{0,12}?\byour (?:own )?(?:email )?address\b|\bas above\b"]
    elif v == "check":
        need = ["(?:%s)[^.]*(?:%s)" % (PRIVATE, "|".join(ADDRESS[h] for h in a)), SIGN_IN] \
            + [ADDRESS[h] for h in a]
        never = [OTHER_WINDOW]
    elif v == "diagnose":
        need = [PRIVATE] + [ADDRESS[h] for h in a]
        never = [OTHER_WINDOW]
    elif v == "stop-if-fails":
        need = [STOPS] + [p for r in action.remedy for p in REMEDY_WORDS.get((r.verb, r.args[0]), [])]
        if action.goto:
            need.append(re.escape(GOTO_WORDS[action.goto]))
        never = [CARRY_ON]
        if not action.goto:  # words that send the reader to another flow need its goto
            never += [re.escape(w) for w in GOTO_WORDS.values()]
    elif v == "rollback":
        if a == ["placeholder"]:
            need, never = [ROLLBACK_UI + r"|\broll\w* back\b", r"\bplaceholder\b"], [r"\boffice deployment\b"]
        else:
            need, never = [ROLLBACK_UI + r"|\broll\w* forward\b", r"\boffice\b|\broll\w* forward\b"], \
                [r"\bplaceholder\b", ROLL_ANYWAY]
    elif v == "auto":
        if a == ["off"]:
            need = [r"\b(?:untick|clear|pause|turn off|switch off)\b", r"\bautomatic\b"]
        else:
            need = [r"(?<!un)\btick\b|\bturn\w* (?:\w+ ){0,4}on\b|\bback on\b", r"\bautomatic\b"]
    elif v == "domain-add":
        need = [r"Set up a domain"]
    elif v == "domain-remove":
        need = [r"Remove domain"]
    elif v == "quote":
        need = [r"\bCloudflare\b"]
    elif v == "repeat":
        lo, hi = a[1].split("-")
        need = [r"\bsteps %s to %s\b" % (lo, hi)]
    elif v == "delete-project":
        need = [r"Delete project"]
    return need, never


def prose_problems(action, span):
    """Why span does not say what action does, as a list. Empty means the words match."""
    found = []
    need, never = required_words(action)
    every = re.search(r"\bcheck (?:every|each) address\b", span, re.I) if action.verb == "check" else None
    if every:
        need = [PRIVATE, SIGN_IN]  # the addresses are named by the step it repeats, not the window
        if NEGATION.search(span[:every.start()]):
            found.append("%s: its words negate it" % action)
    for p in need:
        m = re.search(p, span, re.I)
        if not m:
            found.append("%s: its words do not say %r" % (action, p))
        elif action.verb in IMPERATIVE and NEGATION.search(span[:m.start()]):
            found.append("%s: its words negate it" % action)
    for p in never:
        m = p.search(span) if hasattr(p, "search") else re.search(p, span, re.I)
        if m and not (p is OTHER_APPS and re.search(r"\(not [^)]*\)", span)
                      and not OTHER_APPS.search(re.sub(r"\(not [^)]*\)", "", span))):
            found.append("%s: its words also say %r" % (action, m.group(0)))
    if action.verb == "forbid" and not FORBID.search(span):
        found.append("forbid: its words do not start \"Never do that ... production\"")
    return found


# ---- words that may appear only in a step whose comment allows them ---------------------------

_ACCESS = r"(?:Access|polic(?:y|ies)|applications?)"
_OFF = r"(?:(?:disabl|deactivat|remov|delet|paus|detach|suspend|unprotect|drop|discard)\w*|get\s+rid\s+of)"
_IN = r"(?:[^.]|\.(?=\S))"  # within one sentence: a dot inside `<project>.pages.dev` does not end it
ACCESS_OFF = [
    re.compile(r"\b%s\b%s{0,40}?\b%s\b" % (_OFF, _IN, _ACCESS), re.I),
    re.compile(r"\b%s\s+(?:the\s+|one\s+of\s+(?:the|them)\s+)?(?:first|second|other|wildcard|both|either)\b"
               % _OFF, re.I),
    re.compile(r"\b%s\b[^.]{0,30}?\b(?:disabled|deactivated|removed|deleted|paused|detached|"
               r"suspended|off)\b" % _ACCESS, re.I),
    re.compile(r"\b(?:turn|switch|take|shut)\w*\s+off\b[^.]{0,40}?\b%s\b" % _ACCESS, re.I),
    re.compile(r"\bwithout\s+(?:the\s+)?Access\b", re.I),
    re.compile(r"\bAccess\b[^.]*\b(?:%s\s+(?:it|them)|(?:turn|switch|take)\w*\s+(?:it|them)\s+off)\b"
               % _OFF, re.I),
]
GUARDED = [  # (what, pattern, verbs whose steps may say it)
    ("turns Access off or removes it", ACCESS_OFF, ("quote", "access-remove")),
    ("rolls production", [re.compile(ROLLBACK_UI, re.I),
                          re.compile(r"\broll\w*\s+(?:production\s+|it\s+)?forward\b", re.I),
                          re.compile(r"\bpromot\w*\b", re.I),
                          re.compile(r"\broll\w*\s+(?:production\s+)?back\s+to\s+(?:the\s+)?(?:latest\s+|newest\s+)?"
                                     r"office\b", re.I)], ("rollback",)),
    ("pushes to main", [re.compile(r"\bpush(?:es)? to `?main`?|\bgit push\b", re.I)], ("deploy",)),
    ("ticks automatic deployments", [re.compile(r"(?<!un)\btick\w*\b[^.]{0,40}?\bautomatic\b|\bturn\w*\s+"
                                                r"(?:\w+\s+){0,3}?automatic\b[^.]{0,40}?\bon\b", re.I)],
     ("auto",)),
    ("unticks automatic deployments", [re.compile(r"\b(?:untick|clear|pause)\w*\b[^.]{0,40}?\bautomatic\b",
                                                  re.I)], ("auto",)),
    ("builds `app`", [re.compile(r"\boutput\b[^.`]{0,30}`app`", re.I)], ("set-build",)),
    ("adds a custom domain", [re.compile(r"Set up a domain", re.I),
                              re.compile(r"\badd\w*\s+`?(?:https?://)?office\.example\.com", re.I),
                              re.compile(r"\bCustom domains\b%s{0,20}?\badd\b" % _IN, re.I),
                              re.compile(r"\badd\w*\s+(?:a|the|your|its)\s+(?:own\s+)?(?:custom\s+)?domain\b", re.I)],
     ("domain-add",)),
]
# A guarded action may be named to forbid it ("do not roll forward", "cannot add a custom domain"),
# except where the list below says otherwise: turning Access off stays guarded even when negated,
# so the one place that names it is the quote of Cloudflare's fix and the step that forbids it.
NEGATABLE = ("rolls production", "adds a custom domain")
NOT_BEFORE = re.compile(r"\b(?:do not|don't|never|not|cannot|can't|no longer|without)\s+$", re.I)
WEAK_POLICY = [  # selectors that let in more than the addresses you name
    re.compile(r"\bEveryone\b"), re.compile(r"\bAnyone\b"), re.compile(r"\bBypass\b", re.I),
    re.compile(r"\bInclude\W{0,6}(?:any|every)(?:one|body)\b", re.I),
    re.compile(r"\bending in\b|\bEmails?\s+domains?\b|@\w+\.\w", re.I),
    re.compile(r"\bLogin Methods?\b", re.I)]
NEGATED = re.compile(r"\b(?:never|not|no)\s+(?:an?\s+)?(?:\*\*)?$", re.I)


def guarded_problems(segments):
    """Guarded words outside a step that may say them, across segment boundaries too."""
    flat, owners, at = "", [], 0
    for text, tag in segments:
        flat += text + " "
        owners.append((at, at + len(text), tag))
        at = len(flat)
    found = []

    def owning(start, end):
        return [t for s, e, t in owners if s < end and start < e]

    for what, patterns, verbs in GUARDED:
        for p in patterns:
            for m in p.finditer(flat):
                if what in NEGATABLE and NOT_BEFORE.search(flat[max(0, m.start() - 12):m.start()]):
                    continue
                tags = owning(m.start(), m.end())
                if not all(t is not None and t.verbs() & set(verbs) for t in tags):
                    found.append("%s outside a step that may: %r" % (what, flat[max(0, m.start() - 30):m.end() + 10]))
    for p in WEAK_POLICY:
        for m in p.finditer(flat):
            if not NEGATED.search(flat[max(0, m.start() - 12):m.start()]):
                found.append("an Access policy may let anyone in: %r" % flat[max(0, m.start() - 40):m.end() + 10])
    return found


# ---- replaying the flows ---------------------------------------------------------------------

class State(object):
    """A Pages project as the steps leave it. `apps` and `policies` are the hostnames with an
    Access application and an Allow/Include Emails policy; `verified` the ones whose private-window
    check has passed since. `office_checked` holds the hostnames checked while they served the
    office, since their Access application or policy last changed: any Access change to a hostname
    takes it out again, so a new application is checked against the office's files too.
    Known limit: `*.pages.dev` is one hostname here, so a check of any deployment's own address
    counts as a check of the office's once an office deployment exists."""

    def __init__(self, **kw):
        self.project, self.build, self.auto, self.production = False, None, False, None
        self.deployments, self.domain = set(), False
        self.apps, self.policies, self.verified, self.office_checked = set(), set(), set(), set()
        self.__dict__.update(kw)

    def access_changed(self, hosts):
        self.verified.difference_update(hosts)
        self.office_checked.difference_update(hosts)

    def covered(self, h):
        return h in self.apps and h in self.policies

    def serving(self, h, now=False):
        """Does h serve the office now, or (unless now) at the next push to main?"""
        if not self.project:
            return False
        nxt = not now and self.auto and self.build == "app"
        office = self.production == "app" or nxt
        if h == "pages.dev":
            return office
        if h == "domain":
            return self.domain and office
        # Every office deployment keeps its own address after newer ones replace it.
        return "app" in self.deployments or nxt

    def unchecked(self):
        """Hostnames serving the office with no check of them while they did, since their Access
        last changed."""
        return set(h for h in HOSTS if self.serving(h) and h not in self.office_checked)

    def exposed(self):
        return set(h for h in HOSTS if self.serving(h) and not self.covered(h))


def exposed_start(placeholder):
    return State(project=True, build="app", auto=True, production="app", domain=True,
                 deployments=set(["app", "placeholder"] if placeholder else ["app"]))


def apply(action, s):
    """Do action to s. Returns why it cannot be done, or None."""
    v, a = action.verb, action.args
    if v == "create-project":
        if s.project or s.build is None:
            return "creates the project twice, or before its build output is set"
        s.project, s.auto, s.production = True, True, s.build
        s.deployments.add(s.build)
    elif v == "set-build":
        s.build = a[0]
    elif v == "deploy":
        if not s.project:
            return "deploys with no project"
        if s.auto:
            s.production = s.build
            s.deployments.add(s.build)
    elif v == "rollback":
        target = "app" if a[0] == "office" else "placeholder"
        if target not in s.deployments:
            return "rolls back to a %s deployment that does not exist" % a[0]
        s.production = target
    elif v == "auto":
        s.auto = a[0] == "on"
    elif v == "access-protect":
        public = [h for h in PRODUCTION_HOSTS if h in s.exposed()]
        if public:
            return "adds Access while the office is still public on %s; take it offline first" % ", ".join(public)
        s.apps.update(a)
        s.access_changed(a)
    elif v == "access-move":
        if a[0] not in s.apps:
            return "moves an Access application that does not exist"
        s.apps.discard(a[0])
        s.apps.add(a[1])
        if a[0] in s.policies:
            s.policies.discard(a[0])
            s.policies.add(a[1])
        s.access_changed(a)
    elif v == "access-remove":
        s.apps.difference_update(a)
        s.policies.difference_update(a)
        s.access_changed(a)
    elif v == "policy":
        if not set(a) <= s.apps:
            return "sets a policy on an Access application that does not exist"
        s.policies.update(a)
        s.access_changed(a)
    elif v == "check":
        failing = [h for h in a if not s.covered(h)]
        if failing:
            return "the check of %s cannot pass: Access does not cover it yet" % ", ".join(failing)
        s.verified.update(a)
        s.office_checked.update(h for h in a if s.serving(h, now=True))
    elif v == "domain-add":
        if s.domain:
            return "adds the domain twice"
        if "domain" in s.apps:
            return ("adds the domain while an Access application covers it, which Cloudflare cannot "
                    "do (the certificate check is blocked)")
        s.domain = True
    elif v == "domain-remove":
        s.domain = False
    elif v == "delete-project":
        s.__init__()
    return None


GOALS = {
    "first-deploy": lambda s: s.production == "app" and s.auto and s.build == "app",
    "custom-domain": lambda s: s.domain and s.production == "app" and s.auto and s.build == "app",
    "certificate": lambda s: s.domain and s.production == "app" and s.auto and s.build == "app",
    "stop-path": lambda s: not s.domain and s.production == "app" and s.auto and s.build == "app",
    "offline-placeholder": lambda s: s.production == "app" and s.auto and s.build == "app",
    "offline-rebuild": lambda s: s.production == "app" and s.auto and s.build == "app",
    "offline-delete": lambda s: not s.project,
}


def flows(tags):
    """Each flow's steps in document order, as (label, action), with `repeat` expanded."""
    out = dict((f, []) for f in FLOWS)
    for tag in tags:
        for name, num in tag.flows:
            out[name].extend((num, a) for a in tag.actions)
    for name in FLOWS:
        expanded = []
        for num, a in out[name]:
            if a.verb == "repeat":
                lo, hi = [int(x) for x in a.args[1].split("-")]
                expanded.extend((n, b) for n, b in out[a.args[0]]
                                if n.isdigit() and lo <= int(n) <= hi and b.verb != "repeat")
            else:
                expanded.append((num, a))
        out[name] = expanded
    return out


class Replay(object):
    def __init__(self, steps):
        self.steps, self.found, self.replayed, self.finals = steps, [], set(), {}

    def step(self, where, action, s):
        """Apply one action with the safety rules. Returns False when the flow cannot go on."""
        before_exposed = s.exposed()
        before_serving = set(h for h in HOSTS if s.serving(h))
        why = apply(action, s)
        if why:
            self.found.append("%s (%s): %s" % (where, action, why))
            return False
        for h in sorted(s.exposed() - before_exposed):
            self.found.append("%s (%s): the office is public on %s" % (where, action, h))
        for h in sorted(h for h in HOSTS if s.serving(h) and h not in before_serving
                        and h not in s.verified and s.covered(h)):
            self.found.append("%s (%s): puts the office on %s before a check of it has passed"
                              % (where, action, h))
        return True

    def run(self, name, s, via="", depth=0):
        self.replayed.add(name)
        found_public = s.exposed()
        steps = self.steps[name]
        if not steps:
            self.found.append("flow %s has no steps" % name)
            return None
        for i, (label, action) in enumerate(steps):
            where = "%s%s step %s" % (via, name, label) if label else via + name
            if action.verb == "check":
                nxt = steps[i + 1][1] if i + 1 < len(steps) else None
                if nxt is None or nxt.verb != "stop-if-fails" or not set(action.args) <= set(nxt.args):
                    self.found.append("%s (%s): not followed by what to do if it fails" % (where, action))
            if action.verb == "stop-if-fails":
                self.fail_branch(where, action, s, depth, found_public)
                continue
            if not self.step(where, action, s):
                return None
        for h in sorted(s.exposed()):
            self.found.append("%s%s ends with the office public on %s" % (via, name, h))
        for h in sorted(s.unchecked()):
            self.found.append("%s%s ends with the office on %s and no check of it there since its "
                              "Access changed" % (via, name, h))
        if not GOALS[name](s):
            self.found.append("%s%s does not reach its end state" % (via, name))
        return s

    def fail_branch(self, where, action, s, depth, found_public):
        """The check failed: its hosts are not covered. Do the remedy, then go where it says.
        With nowhere to go, the reader fixes Access and checks again, which is safe only if the
        office is no more public than the flow found it, and not public on a production address."""
        f = copy.deepcopy(s)
        for h in action.args:
            f.apps.discard(h)
            f.policies.discard(h)
        f.access_changed(action.args)
        here = "%s, if it fails" % where
        for r in action.remedy:
            if not self.step(here, r, f):
                return
        if action.goto is None:
            for h in sorted((f.exposed() - found_public) | (f.exposed() & set(PRODUCTION_HOSTS))):
                self.found.append("%s: the office stays public on %s and the step says nowhere to go"
                                  % (here, h))
            return
        if action.goto not in TAKES_PUBLIC:
            for h in sorted(f.exposed() - found_public):
                self.found.append("%s: sends the reader to %s while the office is public on %s"
                                  % (here, action.goto, h))
        if depth > 3:
            self.found.append("%s: goto loops" % here)
            return
        for target in GOTO[action.goto]:
            if target == "offline-placeholder" and "placeholder" not in f.deployments:
                continue
            self.run(target, copy.deepcopy(f), via=here + " -> ", depth=depth + 1)


def order_problems(tags):
    steps = flows(tags)
    r = Replay(steps)
    r.finals["first-deploy"] = r.run("first-deploy", State())
    for name, after in (("custom-domain", "first-deploy"), ("certificate", "custom-domain")):
        start = r.finals.get(after)
        if start is None:
            r.found.append("flow %s cannot start: %s did not finish" % (name, after))
            continue
        r.finals[name] = r.run(name, copy.deepcopy(start))
    for name, placeholder in (("offline-placeholder", True), ("offline-rebuild", False),
                              ("offline-delete", True)):
        r.run(name, exposed_start(placeholder))
    for name in FLOWS:
        if name not in r.replayed:
            r.found.append("flow %s is never reached" % name)
    # The quote of Cloudflare's fix is forbidden by the very next step.
    for i, tag in enumerate(tags):
        if "quote" in tag.verbs() and not (i + 1 < len(tags) and "forbid" in tags[i + 1].verbs()):
            r.found.append("Cloudflare's fix is quoted without a `forbid` step right after it")
    return r.found


def problems(markdown):
    """Every way step 2 breaks the safe order, as a list of reasons. Empty means it holds."""
    tags, segments, found = parse(markdown)
    for tag in tags:
        for action in tag.actions:
            found.extend(prose_problems(action, tag.span))
    found.extend(guarded_problems(segments))
    found.extend(order_problems(tags))
    return found


def read_setup():
    with open(SETUP, encoding="utf-8") as f:
        return f.read()


def tag_index(tags, flow, verb, args=None, nth=0):
    """Position in tags of the nth tag in flow holding verb (with args, when given)."""
    hits = [i for i, t in enumerate(tags) if flow in [f for f, _ in t.flows]
            and any(a.verb == verb and (args is None or a.args == args) for a in t.actions)]
    if len(hits) <= nth:
        raise AssertionError("no %s %s %s tag to mutate" % (flow, verb, args or ""))
    return hits[nth]


class SetupPagesOrder(unittest.TestCase):
    def test_setup_md_keeps_the_safe_order(self):
        self.assertEqual(problems(read_setup()), [])

    def test_every_flow_is_tagged_and_replayed(self):
        """Known-positive control: the parser sees the steps, and every flow, the stop path
        included, is replayed, so a clean result is not an empty one."""
        tags, _, found = parse(read_setup())
        self.assertEqual(found, [])
        steps = flows(tags)
        for name in FLOWS:
            self.assertTrue(steps[name], name)
        r = Replay(steps)
        first = r.run("first-deploy", State())
        self.assertIsNotNone(first)
        self.assertEqual(first.production, "app")
        self.assertEqual(set(first.apps), set(["pages.dev", "*.pages.dev"]))
        self.assertNotIn("stop-path", r.replayed)
        r.run("custom-domain", copy.deepcopy(first))
        self.assertIn("stop-path", r.replayed)
        self.assertEqual(r.found, [])
        self.assertGreater(len(tags), 40)

    def test_setup_md_says_what_is_public_and_what_is_not(self):
        s = rendered(read_setup())
        for phrase in ("`config.js` names every repo you watch", "Live GitHub data is not exposed",
                       "bound to `127.0.0.1` needs no Access"):
            self.assertIn(phrase, s)

    def test_stop_path_names_every_step_that_sends_the_reader_there(self):
        text = read_setup()
        tags, _, _ = parse(text)
        senders = sorted(set(int(num) for t in tags for f, num in t.flows if f == "custom-domain"
                             for a in t.actions if a.goto == "stop-path"))
        self.assertEqual(senders, [4, 5, 7])
        self.assertIn("(custom domain step 4, 5 or 7 sent you here)", rendered(text))


class OrderControls(unittest.TestCase):
    """Each mutation of the real file's steps must fail, for its own reason. These change the
    comments (what the steps do), so they hold the replay rather than the wording."""

    def setUp(self):
        self.tags = parse(read_setup())[0]

    def assertFails(self, tags, reason):
        found = order_problems(tags)
        self.assertTrue([p for p in found if reason in p], "%r not in %r" % (reason, found))

    def without(self, flow, verb, args=None, nth=0):
        tags = list(self.tags)
        del tags[tag_index(tags, flow, verb, args, nth)]
        return tags

    def moved(self, flow, verb, args, before_verb, before_args=None):
        tags = list(self.tags)
        tag = tags.pop(tag_index(tags, flow, verb, args))
        tags.insert(tag_index(tags, flow, before_verb, before_args), tag)
        return tags

    def changed(self, flow, verb, args, new):
        tags = list(self.tags)
        i = tag_index(tags, flow, verb, args)
        old = tags[i]
        actions = []
        for a in old.actions:
            if a.verb == verb and (args is None or a.args == args):
                words = new.split()
                a = Action(words[0], words[1:], a.remedy, a.goto) if new else None
            if a is not None:
                actions.append(a)
        tags[i] = Tag(old.flows, actions, old.span, old.block, old.raw)
        return tags

    def test_the_real_steps_pass(self):
        self.assertEqual(order_problems(self.tags), [])

    def test_first_deploy_building_app_fails(self):
        self.assertFails(self.changed("first-deploy", "set-build", ["placeholder"], "set-build app"),
                         "the office is public on pages.dev")

    def test_wildcard_application_dropped_fails(self):
        self.assertFails(self.without("first-deploy", "access-protect", ["*.pages.dev"], nth=1),
                         "sets a policy on an Access application that does not exist")
        # With the policy step narrowed to match, the check of the deployment address is what fails.
        self.tags = self.without("first-deploy", "access-protect", ["*.pages.dev"], nth=1)
        self.assertFails(self.changed("first-deploy", "policy", None, "policy pages.dev"),
                         "check of *.pages.dev cannot pass")

    def test_narrowing_dropped_fails(self):
        self.assertFails(self.changed("first-deploy", "access-move", None, "note"),
                         "sets a policy on an Access application that does not exist")

    def test_check_before_the_office_dropped_fails(self):
        tags = self.changed("first-deploy", "check", ["pages.dev", "*.pages.dev"], "note")
        self.assertFails(tags, "before a check of it has passed")

    def test_no_check_once_the_office_serves_fails(self):
        """A check while the placeholder is up does not show that Access covers the office's files."""
        self.tags = self.without("first-deploy", "check", None, nth=1)
        self.assertFails(self.without("first-deploy", "stop-if-fails", None, nth=1),
                         "first-deploy ends with the office on pages.dev and no check of it there")
        self.tags = parse(read_setup())[0]
        self.tags = self.without("custom-domain", "check", None, nth=1)
        self.assertFails(self.without("custom-domain", "stop-if-fails", None, nth=2),
                         "custom-domain ends with the office on domain and no check of it there")

    def test_check_without_stop_fails(self):
        self.assertFails(self.without("first-deploy", "stop-if-fails", None, nth=0),
                         "not followed by what to do if it fails")
        self.assertFails(self.without("custom-domain", "stop-if-fails", None, nth=2),
                         "not followed by what to do if it fails")

    def test_post_deploy_failure_with_nowhere_to_go_fails(self):
        tags = list(self.tags)
        i = tag_index(tags, "first-deploy", "stop-if-fails", None, nth=1)
        old = tags[i]
        tags[i] = Tag(old.flows, [Action("stop-if-fails", old.actions[0].args)], old.span, old.block, old.raw)
        self.assertFails(tags, "the step says nowhere to go")

    def test_domain_without_pause_fails(self):
        self.assertFails(self.without("custom-domain", "auto", ["off"]), "the office is public on domain")

    def test_domain_without_placeholder_rollback_fails(self):
        self.assertFails(self.without("custom-domain", "rollback", ["placeholder"]),
                         "the office is public on domain")

    def test_domain_access_before_add_fails(self):
        self.assertFails(self.moved("custom-domain", "access-protect", ["domain"], "domain-add"),
                         "Cloudflare cannot do")

    def test_domain_roll_forward_before_check_fails(self):
        self.assertFails(self.moved("custom-domain", "rollback", ["office"], "check", ["domain"]),
                         "before a check of it has passed")
        self.assertFails(self.moved("custom-domain", "rollback", ["office"], "access-protect", ["domain"]),
                         "the office is public on domain")

    def test_domain_failure_remedy_dropped_fails(self):
        tags = list(self.tags)
        i = tag_index(tags, "custom-domain", "stop-if-fails", None, nth=2)
        old = tags[i]
        tags[i] = Tag(old.flows, [Action("stop-if-fails", old.actions[0].args, goto="stop-path")],
                      old.span, old.block, old.raw)
        self.assertFails(tags, "sends the reader to stop-path while the office is public on domain")

    def test_stop_path_rolls_forward_first_fails(self):
        self.assertFails(self.moved("stop-path", "rollback", ["office"], "domain-remove"),
                         "the office is public on domain")
        self.assertFails(self.without("stop-path", "domain-remove"), "the office is public on domain")

    def test_certificate_remedy_in_production_fails(self):
        tags = self.without("certificate", "rollback", ["placeholder"])
        self.assertFails(tags, "certificate (access-remove domain): the office is public on domain")
        tags = self.without("certificate", "auto", ["off"])
        self.assertFails(tags, "the office is public on domain")

    def test_certificate_remedy_deleting_pages_dev_applications_fails(self):
        # Production is the placeholder by then: only the old deployments' own addresses serve it.
        for args in ("access-remove domain pages.dev *.pages.dev", "access-remove domain *.pages.dev"):
            self.assertFails(self.changed("certificate", "access-remove", ["domain"], args),
                             "certificate (%s): the office is public on *.pages.dev" % args)

    def test_certificate_removes_access_before_rollback_fails(self):
        self.assertFails(self.moved("certificate", "access-remove", ["domain"], "auto", ["off"]),
                         "the office is public on domain")

    def test_offline_roll_forward_before_access_fails(self):
        for flow in ("offline-placeholder", "offline-rebuild"):
            tags = self.moved(flow, "rollback", ["office"], "access-protect")
            self.assertFails(tags, "%s step 2 (rollback office): the office is public on pages.dev" % flow)

    def test_offline_untick_removed_fails(self):
        self.assertFails(self.without("offline-placeholder", "auto", ["off"]),
                         "adds Access while the office is still public on pages.dev")
        # Not offline-rebuild: its build is already the placeholder there, so a push with automatic
        # deployments on brings back the placeholder, not the office. The replay passes it.

    def test_offline_untick_before_push_fails(self):
        self.assertFails(self.moved("offline-rebuild", "auto", ["off"], "deploy"),
                         "adds Access while the office is still public on pages.dev")

    def test_offline_without_rollback_fails(self):
        self.assertFails(self.without("offline-placeholder", "rollback", ["placeholder"]),
                         "adds Access while the office is still public")

    def test_offline_access_missing_a_hostname_fails(self):
        """The old deployments' addresses were public before the flow, so only its end shows it."""
        # Step 2 checks twice (before and after the roll forward), so both checks and both stops.
        for verb in ("access-protect", "policy", "check", "check", "stop-if-fails", "stop-if-fails"):
            self.tags = self.changed("offline-placeholder", verb, ["pages.dev", "*.pages.dev", "domain"],
                                     verb + " pages.dev domain")
        self.assertFails(self.tags, "offline-placeholder ends with the office public on *.pages.dev")

    def test_flow_that_stops_short_fails(self):
        self.tags = self.without("custom-domain", "rollback", ["office"])
        self.assertFails(self.without("custom-domain", "auto", ["on"]),
                         "custom-domain does not reach its end state")

    def test_new_application_never_checked_on_the_office_fails(self):
        """Certificate renewal creates the domain's application again; step 7 checks it on the
        office's files, which step 5 (placeholder) cannot."""
        self.assertFails(self.changed("certificate", "repeat", None, "repeat custom-domain 4-6"),
                         "certificate ends with the office on domain and no check of it there")

    def test_offline_no_check_after_roll_forward_fails(self):
        self.tags = self.without("offline-placeholder", "check", None, nth=1)
        self.assertFails(self.without("offline-placeholder", "stop-if-fails", None, nth=2),
                         "offline-placeholder ends with the office on pages.dev and no check of it there")

    def test_offline_failure_after_roll_forward_with_nowhere_to_go_fails(self):
        """The flow starts public, so a stop with no remedy is held to the production addresses,
        not only to what was public at the start."""
        tags = list(self.tags)
        i = tag_index(tags, "offline-placeholder", "stop-if-fails", None, nth=2)
        old = tags[i]
        tags[i] = Tag(old.flows, [Action("stop-if-fails", old.actions[0].args)], old.span, old.block, old.raw)
        self.assertFails(tags, "offline-placeholder step 2, if it fails: the office stays public on pages.dev")

    def test_offline_domain_stop_sent_to_the_stop_path_fails(self):
        """The stop path rolls forward without the check that take-offline step 2 ends with."""
        tags = list(self.tags)
        i = tag_index(tags, "offline-placeholder", "stop-if-fails", ["domain"])
        old = tags[i]
        tags[i] = Tag(old.flows, [Action("stop-if-fails", ["domain"], goto="stop-path")], old.span, old.block,
                      old.raw)
        self.assertFails(tags, "offline-placeholder step 2, if it fails -> stop-path ends with the office on "
                               "pages.dev and no check of it there")

    def test_stop_covering_fewer_hosts_than_its_check_fails(self):
        self.assertFails(self.changed("first-deploy", "stop-if-fails", ["pages.dev", "*.pages.dev"],
                                      "stop-if-fails pages.dev"),
                         "first-deploy step access-5 (check pages.dev *.pages.dev): not followed by what to do")

    def test_application_without_policy_fails(self):
        self.assertFails(self.without("first-deploy", "policy"),
                         "first-deploy step access-5 (check pages.dev *.pages.dev): the check of pages.dev, "
                         "*.pages.dev cannot pass")

    def test_every_access_change_takes_back_its_checks(self):
        """The model rule behind the two tests above: a check holds only until the hostname's
        Access application or policy changes."""
        for verb in ("access-protect domain", "access-remove domain", "policy domain",
                     "access-move domain pages.dev"):
            s = State(project=True, build="app", production="app", domain=True, deployments=set(["app"]),
                      apps=set(HOSTS), policies=set(HOSTS), verified=set(HOSTS), office_checked=set(HOSTS))
            words = verb.split()
            self.assertIsNone(apply(Action(words[0], words[1:]), s), verb)
            self.assertFalse(set(words[1:]) & (s.verified | s.office_checked), verb)
            self.assertIn("*.pages.dev", s.verified & s.office_checked, verb)

    def test_office_check_needs_the_office_in_production(self):
        """A check while the placeholder serves, with the office due at the next push, is a check of
        the placeholder."""
        s = State(project=True, build="app", auto=True, production="placeholder", deployments=set(["placeholder"]),
                  apps=set(HOSTS), policies=set(HOSTS))
        self.assertTrue(s.serving("pages.dev"))
        self.assertIsNone(apply(Action("check", ["pages.dev"]), s))
        self.assertEqual(s.verified, set(["pages.dev"]))
        self.assertEqual(s.office_checked, set())

    def test_quote_without_forbid_fails(self):
        self.assertFails(self.without("certificate", "forbid"), "without a `forbid` step right after it")

    def test_flow_dropped_fails(self):
        tags = [t for t in self.tags if "stop-path" not in [f for f, _ in t.flows]]
        self.assertFails(tags, "flow stop-path has no steps")


def section_of(body):
    return SECTION_HEADING + " behind Cloudflare Access\n\n" + body + "\n\n## Next\n"


class ProseControls(unittest.TestCase):
    """Each step's words against its comment, and the words only some steps may say."""

    def ok(self, verb, span):
        action = parse_tag("step certificate: " + verb, [], span, 0).actions[-1]
        self.assertEqual(prose_problems(action, span), [], (verb, span))

    def bad(self, verb, span):
        action = parse_tag("step certificate: " + verb, [], span, 0).actions[-1]
        self.assertTrue(prose_problems(action, span), (verb, span))

    def test_stop_branches(self):
        verb = "stop-if-fails domain -> goto stop-path"
        tail = ' Fix it, or follow "If the domain cannot go behind Access" below.'
        for good in ("If you see `ok`, stop: do not go on to step 6.", "Should it show `ok`, stop.",
                     "If one of them shows `ok`, stop: do not go on.", "If `ok` shows, do not go on to step 6."):
            self.ok(verb, good + tail)
        for bad in ("If you see `ok`, do not worry: go on to step 6.",
                    "If you see `ok`, stop worrying and go on to step 6.",
                    "If you see `ok`, it may be cached: go on to step 6 and follow step 7 if needed.",
                    "If either shows `ok`, do not worry, deploy the office anyway.",
                    "If you see the file, do not panic, it is cached; carry on.",
                    "If you see `ok`, that is fine, carry on.",
                    "If `example.com` is not in the Domain list, carry on with step 6."):
            self.bad(verb, bad + tail)
        self.bad(verb, "If you see `ok`, stop.")  # does not say where to go
        for bad in ("If you see `ok`, you need not stop: that is the placeholder, so step 6 is safe.",
                    "If you see `ok`, there is no need to stop; step 6 is safe.",
                    "If you see `ok`, you need not stop there, or follow \"If the domain cannot go behind "
                    "Access\" later.",
                    "If you see `ok`, the reader does not have to stop, or follow \"If the domain cannot go "
                    "behind Access\" later."):
            self.bad(verb, bad + tail)
        self.bad("stop-if-fails pages.dev *.pages.dev -> goto take-offline",
                 "If you see the file, it is your own cached session, so there is no need to follow \"Is my "
                 "office public right now?\" below.")
        self.ok("stop-if-fails pages.dev *.pages.dev -> goto take-offline",
                "If you see the file, follow \"Is my office public right now?\" below.")
        self.bad("stop-if-fails pages.dev *.pages.dev",
                 "If either shows `ok`, that is expected for a new project; still, stop and think before you "
                 "deploy the office.")
        remedy = "stop-if-fails domain -> rollback placeholder; auto off; goto stop-path"
        self.ok(remedy, "If the file loads, roll back to the placeholder at once (then untick automatic "
                        "deployments), or follow \"If the domain cannot go behind Access\".")
        self.bad(remedy, "If the file loads, stop, or follow \"If the domain cannot go behind Access\".")
        # A stop with no goto keeps the reader here, so its words may not name another flow.
        self.bad("stop-if-fails domain", "If the domain's zone is not on this Cloudflare account, stop and "
                                         "follow \"If the domain cannot go behind Access\" below.")
        self.ok("stop-if-fails domain", "If the domain's zone is not on this Cloudflare account, stop: take "
                                        "the domain off the project, then come back here and check again.")

    def test_forbid(self):
        for good in ("Never do that while the office is in production, because it publishes `config.js`.",
                     "Do not do that while the office is in production."):
            self.ok("forbid", good)
        for bad in ("Never mind the wait: do that now, it only takes a minute.", "Do that now.",
                    "It is quick. Never do that while the office is in production."):
            self.bad("forbid", bad)

    def test_access_remove_names_only_the_domain(self):
        self.ok("access-remove domain", "then delete only the domain's own Access application (not the "
                                        "two `pages.dev` ones),")
        for bad in ("then delete the project's Access applications,",
                    "then delete the domain's and the two `pages.dev` ones,",
                    "then delete the domain's own Access application and the `pages.dev` ones,",
                    "then delete all the Access applications,"):
            self.bad("access-remove domain", bad)

    def test_actions_say_what_they_do(self):
        self.ok("rollback placeholder", "Deployments → the placeholder deployment → ⋯ → **Roll back to this deployment**.")
        self.bad("rollback placeholder", "Deployments → the latest office deployment → ⋯ → **Rollback to this deployment**.")
        self.bad("rollback office", "Deployments → the placeholder deployment → ⋯ → **Rollback to this deployment**.")
        self.ok("auto off", "Settings: clear **Enable automatic production branch deployments** and save.")
        self.bad("auto off", "Settings: keep **Enable automatic production branch deployments** on.")
        self.ok("access-move *.pages.dev pages.dev", "Under Public hostname, remove the `*` from the "
                                                     "**Subdomain** field. It now covers `<project>.pages.dev`.")
        self.bad("access-protect *.pages.dev", "Do not select **Enable access policy** again for "
                                               "`*.<project>.pages.dev`.")
        self.ok("check domain", "In a private (incognito) window, open `https://office.example.com/`. You "
                                "should get the Access login page.")
        self.bad("check domain", "Open `https://office.example.com/`. It should load.")
        self.bad("set-build placeholder", "Set the build output directory to `app`.")
        self.ok("set-build placeholder", "Set the build output directory as `placeholder`.")
        self.bad("set-build placeholder", "Set the build command to `cp -r app placeholder && echo ok > "
                                          "placeholder/index.html` and the build output directory to `placeholder`.")
        roll = " roll forward: Deployments → the latest office deployment → ⋯ → **Rollback to this deployment**,"
        self.ok("rollback office", "Once Custom domains no longer lists it," + roll)
        for bad in ("Even if Custom domains still lists it,", "Whether or not Custom domains lists it,"):
            self.bad("rollback office", bad + roll)

    def test_checks_need_a_private_window_and_the_sign_in(self):
        every = "check pages.dev *.pages.dev domain"
        self.ok(every, "and check every address again in a private window: each should give the Access sign-in.")
        for bad in ("and check every address again.",
                    "and, optionally, check every address again in a private window: each should give the "
                    "Access sign-in.",
                    "Check every address in your usual browser window; each should show the office.",
                    "and, if you have time, check every address again in a private window: each should give "
                    "the Access sign-in."):
            self.bad(every, bad)
        url = " open `https://office.example.com/`. You should get the Access sign-in."
        self.ok("check domain", "In a private or incognito window," + url)
        for bad in ("In a private window or your usual one,", "In a private window, or this one if it is quicker,"):
            self.bad("check domain", bad + url)

    def test_policies_name_your_address(self):
        for good in ("Open each application's policy and make sure it is Action Allow, Include Emails with your "
                     "address (or the people you choose).",
                     "Add a policy with Action Allow, Include Emails, your address, as above, then **Create**."):
            self.ok("policy domain", good)
        self.bad("policy domain", "Add a policy with Action Allow, Include Emails, then **Create**.")
        self.bad("policy domain", "Never add Action Allow, Include Emails, your address, as above.")

    def test_diagnosis_needs_a_private_window(self):
        url = " and go to `https://<project>.pages.dev/instance/config.js`."
        self.ok("diagnose pages.dev", "Open a private window" + url)
        self.bad("diagnose pages.dev", "Open a private window or your usual one" + url)

    def guarded(self, body):
        return guarded_problems(parse(section_of(body))[1])

    def test_access_off_only_in_the_quote(self):
        for sentence in ("Remove Access from the domain until it verifies.",
                         "Delete the domain's Access application until the certificate verifies.",
                         "Pause Access on the domain for a few minutes.",
                         "Access can be disabled on the domain until it verifies.",
                         "Access on the domain may be turned off until it verifies.",
                         "Take Access off the domain until it verifies.",
                         "With Access off on the domain, the certificate verifies.",
                         "Detach the Access application from the domain.",
                         "Disable the domain's policy until it verifies.",
                         "If Access blocks the deploy, turn it off.",
                         "Disabling Access on the domain for a minute is fine.",
                         "Turn off Access until the deploy ends.",
                         "Keep the first, and drop the second once the office is up.",
                         "You may also want to drop the `*.<project>.pages.dev` application then.",
                         "Get rid of the domain's Access application while it verifies."):
            self.assertTrue(self.guarded(sentence), sentence)
            self.assertTrue(self.guarded("1. " + sentence + "<!-- step certificate: note -->"), sentence)
        self.assertEqual(self.guarded("Cloudflare's fix is to disable Access over the domain."
                                      "<!-- step certificate: quote -->"), [])

    def test_production_words_only_in_their_steps(self):
        for body in ("Then Deployments → the office → **Rollback to this deployment**.",
                     "1. Push to `main` now.<!-- step certificate: note -->",
                     "Tick **Enable automatic production branch deployments** again.",
                     "Or set the output folder to `app` now.",
                     "Custom domains → **Set up a domain**.",
                     "Wait until it is active, then roll forward to the latest office deployment.",
                     "Meanwhile, under Deployments, promote the latest office deployment.",
                     "Then roll back to the latest office deployment.",
                     "Then Custom domains, add office.example.com.",
                     "Add `office.example.com` as a custom domain too.",
                     "Then add your custom domain.",
                     "Under Custom domains, add one for the office."):
            self.assertTrue(self.guarded(body), body)
        for body in ("Do not roll forward while the project still lists a custom domain.",
                     "Come back here and check again, without rolling forward there.",
                     "Cloudflare cannot add a custom domain that already has an Access policy on it."):
            self.assertEqual(self.guarded(body), [], body)
        # Turning Access off stays guarded when negated: "do not ... until" still tells the reader to.
        self.assertTrue(self.guarded("Do not disable Access on the domain until it verifies."))

    def test_weak_policies(self):
        for body in ("Include Emails, your address, or if not sure, Everyone.", "Action Bypass.",
                     "Allow for Everyone.", "Temporarily set the policy to Bypass.",
                     "Action Allow, Include Emails ending in `@gmail.com`.",
                     "Include Emails with your address (or Login Methods: One-time PIN).",
                     "Include Emails with your address (or, to share it, Include Anyone with a link).",
                     "Include anyone who has the link.",
                     "Include Emails with your address or `@example.com`.",
                     "Include an Email domain, `example.com`.",
                     "Allow Anyone with the link."):
            self.assertTrue(self.guarded(body), body)
        for body in ("never Everyone, and never a Bypass action.",
                     "so the office stays private for everyone but you.",
                     "Pages serves everything in `app/` to anyone who can reach the address."):
            self.assertEqual(self.guarded(body), [], body)


class WholeFileControls(unittest.TestCase):
    """Edits to the real file, words and comments together, as a reader would make them."""

    def edited(self, old, new):
        text = read_setup()
        self.assertEqual(text.count(old), 1, old)
        return problems(text.replace(old, new))

    def test_harmless_rewordings_pass(self):
        for old, new in (("In a private window, open `https://office.example.com/`.",
                          "In a private (incognito) window, open `https://office.example.com/`."),
                         ("**Rollback to this\n   deployment**. Production", "**Roll back to this\n   deployment**. Production"),
                         ("delete the `*` from", "remove the `*` from"),
                         ("untick **Enable automatic", "clear **Enable automatic"),
                         ("set Subdomain `office`", "set the subdomain to `office`"),
                         ("Never do that while", "Do not do that while"),
                         ("Cloudflare's fix is to disable Access over", "Cloudflare suggests disabling Access over"),
                         ("If either shows `ok`", "If one of them shows `ok`"),
                         ("If you see `ok`, stop: do\n   not go on", "Should it show `ok`, stop: do\n   not go on"),
                         ("If you see the file,\n   stop and roll back", "If the file loads,\n   roll back"),
                         ("Do them in this order.", "Do them in this order, so the office stays private for "
                                                    "everyone but you.")):
            self.assertEqual(self.edited(old, new), [], new)

    def test_unsafe_rewordings_fail(self):
        for old, new in (
                # The certificate remedy without taking the office out of production first.
                ("steps 1 and 2 (pause automatic deployments,<!-- step certificate: auto off -->\n"
                 "roll back to the placeholder),<!-- step certificate: rollback placeholder --> then",
                 "<!-- step certificate: auto off --><!-- step certificate: rollback placeholder -->"),
                # ... or deleting the pages.dev applications too.
                ("domain's own Access application (not the two `pages.dev` ones)",
                 "domain's own Access application and the two `pages.dev` ones"),
                ("Never do that while the office is in\nproduction, because",
                 "Never mind the wait: do that now, because"),
                (" Then untick automatic production deployments, as in\n     custom domain step 1, so the "
                 "next push does not bring the office back.", " It is fine."),
                ("If you see `ok`, stop: do\n   not go on to step 6.", "If you see `ok`, do not worry: go\n   on to step 6."),
                ("stop here and follow", "carry on with step 6, or follow"),
                ("(Deployments → the latest office deployment → ⋯ → **Rollback to this deployment**)<!-- step "
                 "offline-placeholder 2, offline-rebuild 2: rollback office -->",
                 "<!-- step offline-placeholder 2, offline-rebuild 2: rollback office -->"),
                # The stop after the office deploys, negated.
                ('If you see the file, follow "Is my office public right now?" below.',
                 'If you see the file, it is your own cached session, so there is no need to follow "Is my '
                 'office public right now?" below.'),
                ("If one still shows `ok` or the file, stop: do not roll forward.",
                 "If one still shows `ok` or the file, you need not stop: roll forward, Access catches up."),
                # A check in a signed-in window, or one that may be skipped.
                ("3. In a private window, open `https://<project>.pages.dev/instance/config.js`",
                 "3. In a private window or your usual one, open `https://<project>.pages.dev/instance/config.js`"),
                ("and check every address again in a private window: each should give the Access sign-in.",
                 "and check every address again."),
                # Production rolled, or the domain added, in words no comment names.
                ("Wait\n   until Cloudflare shows the domain as active.<!--",
                 "Wait\n   until Cloudflare shows the domain as active, then roll forward to the latest office "
                 "deployment.<!--"),
                ("nothing new).<!-- step first-deploy deploy-2: deploy -->",
                 "nothing new). Then Custom domains, add `office.example.com`.<!-- step first-deploy deploy-2: deploy -->"),
                # Policies wider than your address.
                ("Add a policy with Action Allow, Include Emails, your address, as above, then **Create**.",
                 "Add a policy with Action Allow, Include Emails ending in `@gmail.com`, then **Create**."),
                ("(or the people you choose)", "(or Login Methods: One-time PIN, so anyone you send the link to)"),
                # A placeholder that carries app/instance/, and a stop path that rolls forward anyway.
                ("`mkdir -p placeholder && echo ok > placeholder/index.html`",
                 "`cp -r app placeholder && echo ok > placeholder/index.html`"),
                ("Once Custom domains no longer lists it, roll forward:",
                 "Even if Custom domains still lists it, roll forward:"),
                # The wildcard application dropped.
                ("Keep both.<!--", "Keep the first, and drop the second once the office is up.<!--")):
            self.assertTrue(self.edited(old, new), new)

    def test_certificate_without_the_office_check_fails(self):
        found = self.edited("and then steps 4 to 7.<!-- step certificate: repeat custom-domain 4-7 -->",
                            "and then steps 4 to 6.<!-- step certificate: repeat custom-domain 4-6 -->")
        self.assertIn("certificate ends with the office on domain and no check of it there since its Access "
                      "changed", found)

    def test_comment_layout_fails(self):
        """What Markdown would show: an unclosed comment, two hyphens in one, a step comment outside
        step 2."""
        for old, new, reason in (
                ("<!-- step custom-domain 6: rollback office -->", "<!-- step custom-domain 6: rollback office",
                 "an HTML comment is not closed"),
                ("<!-- step custom-domain 4: note -->", "<!-- step custom-domain 4: note -- see Cloudflare -->",
                 "a comment holds `--`"),
                ("<!-- step custom-domain 4: note -->", "<!-- step custom-domain 4: note --->",
                 "a comment holds `--`"),
                ("## Run it on your own machine with Docker\n",
                 "## Run it on your own machine with Docker\n\nNothing here.<!-- step first-deploy 9: note -->\n",
                 "a step comment sits outside step 2")):
            found = self.edited(old, new)
            self.assertTrue([p for p in found if reason in p], (reason, found))

    def test_step_comment_at_line_start_fails(self):
        found = self.edited("before Access covers it. Do them in this order.",
                            "before Access covers it.\n<!-- step certificate: note -->Do them in this order.")
        self.assertTrue([p for p in found if "starts with a step comment" in p], found)

    def test_untagged_numbered_step_fails(self):
        found = self.edited("3. Only as a last resort", "3. Wait a day.\n4. Only as a last resort")
        self.assertTrue([p for p in found if "a numbered step has no step comment" in p], found)

    def test_unknown_comment_fails(self):
        found = self.edited("<!-- step custom-domain 1: auto off -->", "<!-- stpe custom-domain 1: auto off -->")
        self.assertTrue([p for p in found if "neither `step ...` nor `about: ...`" in p], found)

    def test_renamed_heading_fails_loudly(self):
        with self.assertRaises(ValueError):
            problems(read_setup().replace("## 2. Host it", "## 2. Put it"))


# `python`, `python3`, `python3.9` or `py`, any interpreter flags, then `-m http.server`; the command
# runs to the end of its line (after `\` continuations are joined), a closing backtick or a quote.
HTTP_SERVER = re.compile(r"\b(?:python[0-9.]*|py)(?:\s+-[^\s-]\S*)*\s+-m\s+http\.server\b[^\n`'\"]*")
BIND = re.compile(r"(?<!\S)(?:--bind(?:=|\s+)|-b\s*)(\S+)")
LOOPBACK = ("127.0.0.1", "::1")
SKIP_DIRS = (".git", "node_modules", "out", ".claude")


def unbound_servers(text):
    """Every `python -m http.server` command in text whose last --bind/-b is not loopback.
    http.server keeps the last --bind it is given, and a `#` comment is not part of the command."""
    text = re.sub(r"\\\r?\n", " ", text)
    bad = []
    for m in HTTP_SERVER.finditer(text):
        command = re.split(r"\s#", m.group(0), maxsplit=1)[0]
        binds = BIND.findall(command)
        if not binds or binds[-1].rstrip(".,;:)") not in LOOPBACK:
            bad.append(m.group(0))
    return bad


def text_files(root):
    """Every file under root that decodes as UTF-8 and has no NUL byte, outside SKIP_DIRS."""
    for top, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = os.path.join(top, name)
            with open(path, "rb") as f:
                data = f.read()
            if b"\0" in data:
                continue
            try:
                yield path, data.decode("utf-8")
            except UnicodeDecodeError:
                continue


def scan(root, skip=None):
    """(commands seen, files with an unbound one) over every text file under root."""
    seen, bad = 0, []
    for path, text in text_files(root):
        if os.path.abspath(path) == skip:
            continue
        seen += len(HTTP_SERVER.findall(text))
        if unbound_servers(text):
            bad.append(path)
    return seen, bad


class LocalServerBindsLoopback(unittest.TestCase):
    """http.server listens on every interface by default, which would serve app/instance/ to the
    whole network."""

    def test_controls(self):
        for ok in ("python3 -m http.server --bind 127.0.0.1 -d app 8080",
                   "python3 -m http.server --bind=127.0.0.1 -d app 8080",
                   "python3 -m http.server -b 127.0.0.1 8080",
                   "python3 -m http.server \\\n  --bind 127.0.0.1 -d app 8080",
                   "python3 -m http.server --bind ::1 8080",
                   "run python3 -m http.server --bind 127.0.0.1.",
                   "python3 -m http.server --bind 127.0.0.1 -d my-build 8080",
                   "python3 -m http.server --bind 0.0.0.0 --bind 127.0.0.1 8080"):
            self.assertEqual(unbound_servers(ok), [], ok)
        for bad in ("python3 -m http.server -d app 8080",
                    "python3 -m http.server --bind 0.0.0.0 8080",
                    "python -m http.server 8080",
                    "python3.9 -m http.server 8080",
                    "python3 -I -m http.server 8080",
                    "python3 -m  http.server 8080",
                    "py -m http.server 8080",
                    "python3 -m http.server --bind 127.0.0.1 --bind 0.0.0.0 8080",
                    "python3 -m http.server -d app 8080  # add --bind 127.0.0.1 on shared networks",
                    '"serve": "python3 -m http.server -d app 8080",'):
            self.assertEqual(len(unbound_servers(bad)), 1, bad)

    def test_scan_reads_every_text_file(self):
        """Any extension, any case, and no extension at all; a binary file is skipped."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for name in ("Makefile", "notes.txt", "serve.py", "page.html", "X.MD"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write("python3 -m http.server -d app 8080\n")
            with open(os.path.join(d, "blob.bin"), "wb") as f:
                f.write(b"\0python3 -m http.server 8080\n")
            seen, bad = scan(d)
        self.assertEqual(seen, 5)
        self.assertEqual(sorted(os.path.basename(p) for p in bad),
                         ["Makefile", "X.MD", "notes.txt", "page.html", "serve.py"])

    def test_docs_bind_loopback(self):
        seen, bad = scan(ROOT, skip=os.path.abspath(__file__))  # its controls are unbound on purpose
        self.assertEqual(bad, [])
        self.assertGreater(seen, 0, "no http.server command found, so the scan proved nothing")


if __name__ == "__main__":
    unittest.main()
