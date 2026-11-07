# SPDX-License-Identifier: Apache-2.0
# docs/SETUP.md, step 2: the hosting order that keeps app/instance/ from being public.
#
# Pages serves app/instance/config.js (repo names, agents, runbook links) to anyone who reaches
# the site, at <project>.pages.dev, at every custom domain and at each deployment's own
# <hash>.<project>.pages.dev address. These tests hold the facts the step depends on, by order
# and presence rather than by exact sentence:
#   - the first deployment is a placeholder, and no `app` output directory appears before Access
#     is set up and checked;
#   - Access narrows the first application to <project>.pages.dev (deletes the `*`), then keeps
#     the *.<project>.pages.dev application, and a private window checks
#     https://<project>.pages.dev/ before the office is built;
#   - the policy is Action Allow and includes emails; Everyone and Bypass appear only negated;
#   - after the office deploys, config.js is checked on pages.dev and on a deployment address;
#   - a custom domain is added only while production is rolled back to the placeholder, is put
#     behind Access and checked before rolling forward (Cloudflare cannot add a domain that
#     already has an Access policy);
#   - "Is my office public right now?" checks a deployment address, and its first remedy is the
#     rollback, then unticking automatic production deployments, with deleting the project after;
#   - every private-window check before a deploy or a roll forward, and after one, says what to do
#     when it fails ("If you see `ok`, stop", "If you see the file, follow ...");
#   - nothing tells the reader to disable or turn off Access, or to remove an Access application
#     while the office is up, except the sentence quoting Cloudflare's own fix, which the next
#     sentence forbids with "Never ..."; and the domain stop path removes the domain before it
#     rolls forward.
# Markdown wraps lines, so every check runs on text with its whitespace collapsed, and the markers
# allow small rewordings (private (incognito) window, Roll back, output directory as, login page).
# Also: any `python -m http.server` command in a tracked text file binds 127.0.0.1.
# Standard library only. Run: python3 -m unittest discover -s tests
import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(ROOT, "docs", "SETUP.md")

SECTION_HEADING = "## 2. Host it on Cloudflare Pages"
_OUT = r"output(?:\s+(?:directory|folder|dir))?\W{0,6}(?:(?:to|as)\W{0,3})?`?"
PLACEHOLDER_OUT = re.compile(_OUT + r"placeholder\b", re.I)
APP_OUT = re.compile(_OUT + r"app\b", re.I)
ENABLE_ACCESS = "Enable access policy"
NARROW = re.compile(r"delete the (?:wildcard|\W{0,4}\*)", re.I)
WILDCARD = "`*.<project>.pages.dev`"
PAGES_ROOT = "`https://<project>.pages.dev/`"
DEPLOY_ADDR = "<hash>.<project>.pages.dev"
SIGN_IN = re.compile(r"Access (?:sign-?in|log-?in)", re.I)
PRIVATE = re.compile(r"private\W{0,3}(?:\([^)]{0,20}\)\W{0,3})?window|incognito", re.I)
PAGES_CONFIG = "`https://<project>.pages.dev/instance/config.js`"
EVERYONE = re.compile(r"\bEveryone\b", re.I)
BYPASS = re.compile(r"\bBypass\b", re.I)
ALLOW = re.compile(r"Action\W{0,6}Allow\b", re.I)
INCLUDE_EMAILS = re.compile(r"Include\W{0,6}Emails", re.I)
ROLLBACK = re.compile(r"Roll ?back to this deployment", re.I)
SUBDOMAIN = re.compile(r"\bSubdomain\b")
UNTICK = re.compile(r"untick\W{0,4}(?:enable\s+)?automatic production", re.I)
DOMAIN_ADD = "Set up a domain"
DOMAIN_ACCESS = "Add public hostname"
DOMAIN_ROOT = "`https://office.example.com/`"
DOMAIN_CONFIG = "`https://office.example.com/instance/config.js`"
PUBLIC_CHECK = "**Is my office public right now?**"
STOP_PATH = "**If the domain cannot go behind Access**"
REMOVE_DOMAIN = "Remove domain"
# What to do when a check fails: "If you see `ok`, stop", "If you see the file, follow ...".
STOP_BRANCH = re.compile(r"\bIf (?:either |it |you )?(?:see|get|show)s?\b[^.]{0,60}?"
                         r"\b(?:stop|do not|follow|roll back)\b", re.I)
# Turning Access off: "disable Access", "turn off the Access policy", "turn Access off", and a
# pronoun ("disable it", "turn it off") in a sentence that names Access before it.
_OFF = r"(?:disabl|deactivat)\w*|(?:turn|switch)\w*\s+off"
ACCESS_OFF = re.compile(r"\b(?:%s)\b[^.]{0,40}?\bAccess\b" % _OFF
                        + r"|\b(?:turn|switch)\w*\s+(?:[\w']+\s+){0,3}?Access\b[^.]{0,30}?\boff\b"
                        + r"|\bAccess\b[^.]*\b(?:(?:%s)\s+(?:it|them)|(?:turn|switch)\w*\s+(?:it|them)\s+off)\b" % _OFF,
                        re.I)
ACCESS_REMOVED = re.compile(r"\b(?:remov|delet)\w*\b[^.]{0,40}?\bAccess\b", re.I)
DELETE = "Delete project"


def normalise(text):
    return re.sub(r"\s+", " ", text).strip()


def pages_section(markdown):
    """Step 2 of SETUP.md, from its heading to the next level-two heading, whitespace collapsed.
    Raises ValueError when the heading is missing, so a renamed step fails loudly."""
    start = markdown.find(SECTION_HEADING)
    if start < 0:
        raise ValueError("no %r heading" % SECTION_HEADING)
    end = markdown.find("\n## ", start + len(SECTION_HEADING))
    return normalise(markdown[start:] if end < 0 else markdown[start:end])


def paragraph(markdown, marker):
    """The paragraph of step 2 that holds marker, up to the next blank line, whitespace collapsed."""
    start = markdown.find(SECTION_HEADING)
    at = markdown.find(marker, start)
    end = re.search(r"\n\s*\n", markdown[at:])
    return normalise(markdown[at:at + end.start()] if end else markdown[at:])


def _find(s, needle, start=0, end=None):
    """Index of needle (a string or a compiled pattern) in s[start:end], or -1."""
    end = len(s) if end is None else end
    if isinstance(needle, str):
        return s.find(needle, start, end)
    m = needle.search(s, start, end)
    return m.start() if m else -1


def unnegated(s, pattern):
    """Matches of pattern in s not just after "never" or "not", so "never Everyone" is fine and
    "Include Everyone" or "Action Bypass" is not."""
    return [m.group(0) for m in pattern.finditer(s)
            if not re.search(r"\b(?:never|not)\b", s[max(0, m.start() - 12):m.start()], re.I)]


def sentences(s):
    return re.split(r"(?<=[.!?])(?:\*\*)?\s+", s)


def access_turned_off(s):
    """Sentences that turn Access off, or remove an Access application while something is up.
    The one allowed is Cloudflare's own fix quoted as such ("Cloudflare's fix is ...") when the
    sentence right after it forbids it ("Never ...")."""
    parts = sentences(s)
    bad = []
    for i, sentence in enumerate(parts):
        off = ACCESS_OFF.search(sentence)
        removed = ACCESS_REMOVED.search(sentence) and re.search(r"\bwhile\b", sentence, re.I)
        if not (off or removed):
            continue
        if (sentence.startswith("Cloudflare's fix is") and i + 1 < len(parts)
                and parts[i + 1].startswith("Never")):
            continue
        bad.append(sentence)
    return bad


def problems(markdown):
    """Every way step 2 breaks the safe order, as a list of reasons. Empty means it holds."""
    s = pages_section(markdown)
    found = []

    placeholder = _find(s, PLACEHOLDER_OUT)
    access = _find(s, ENABLE_ACCESS)
    app = _find(s, APP_OUT)
    public = _find(s, PUBLIC_CHECK)
    for name, at in (("placeholder output directory", placeholder), (ENABLE_ACCESS, access),
                     ("`app` output directory", app), (PUBLIC_CHECK, public)):
        if at < 0:
            found.append("missing: " + name)
    if found:
        return found

    # The first deployment, and Access before the office.
    if not placeholder < access:
        found.append("the first deployment is not the placeholder")
    if not access < app:
        found.append("an `app` output directory comes before Access is set up")
    # Enabling Access covers only *.<project>.pages.dev; deleting the `*` is what moves that
    # application onto <project>.pages.dev, and enabling again restores the wildcard one.
    narrow = _find(s, NARROW, access, app)
    if narrow < 0:
        found.append("Access does not narrow the first application to `<project>.pages.dev`")
    re_enable = _find(s, ENABLE_ACCESS, max(access, narrow) + 1, app)
    if re_enable < 0 or _find(s, WILDCARD, re_enable, app) < 0:
        found.append("Access does not keep the `*.<project>.pages.dev` application")
    if _find(s, ALLOW, access, app) < 0:
        found.append("the Access policy is not Action Allow")
    if _find(s, INCLUDE_EMAILS, access, app) < 0:
        found.append("the Access policy does not include emails")
    if unnegated(s, EVERYONE):
        found.append("an Access policy includes Everyone")
    if unnegated(s, BYPASS):
        found.append("an Access policy uses Bypass")
    check = _find(s, PRIVATE, max(access, re_enable), app)
    if check < 0 or _find(s, SIGN_IN, check, app) < 0:
        found.append("no private-window Access sign-in check before the office deploys")
    elif _find(s, PAGES_ROOT, check, app) < 0:
        found.append("the check before the office deploys does not open `https://<project>.pages.dev/`")
    elif _find(s, STOP_BRANCH, _find(s, PAGES_ROOT, check, app), app) < 0:
        found.append("the check before the office deploys does not say to stop if it fails")

    # After the office deploys, before the custom domain: config.js on pages.dev and on the
    # deployment's own address.
    first_rollback = _find(s, ROLLBACK, app, public)
    deploy_end = first_rollback if first_rollback >= 0 else public
    if _find(s, PAGES_CONFIG, app, deploy_end) < 0:
        found.append("no check of pages.dev /instance/config.js after the office deploys")
    if _find(s, DEPLOY_ADDR, app, deploy_end) < 0:
        found.append("no check of a deployment's own address after the office deploys")
    deploy_check = _find(s, PAGES_CONFIG, app, deploy_end)
    if deploy_check >= 0 and _find(s, STOP_BRANCH, deploy_check, deploy_end) < 0:
        found.append("the check after the office deploys does not say what to do if it fails")

    # Custom domain: placeholder in production, add, Access, check, roll forward, check.
    if 0 <= _find(s, DOMAIN_ADD) < app:
        found.append("a custom domain is added outside the custom domain steps")
    domain_add = _find(s, DOMAIN_ADD, app, public)
    if domain_add >= 0:
        steps = [("pause automatic production deployments", _find(s, UNTICK, app, domain_add)),
                 ("roll back to the placeholder", first_rollback),
                 ("add the domain", domain_add),
                 ("put the domain behind Access", _find(s, DOMAIN_ACCESS, domain_add, public)),
                 ("private-window check of the domain", _find(s, DOMAIN_ROOT, domain_add, public))]
        forward = _find(s, ROLLBACK, max(at for _, at in steps) + 1, public)
        steps += [("roll forward to the office", forward),
                  ("check the domain's config.js", _find(s, DOMAIN_CONFIG, max(forward, 0), public))]
        last = -1
        for name, at in steps:
            if at < 0 or at < last:
                found.append("custom domain: %s is missing or out of order" % name)
                break
            last = at
        if 0 <= first_rollback and "placeholder" not in s[max(app, first_rollback - 120):first_rollback]:
            found.append("custom domain: the first rollback is not to the placeholder")
        root_check = steps[4][1]
        domain_access = steps[3][1]
        if domain_access >= 0 and root_check >= 0 and (
                _find(s, ALLOW, domain_access, root_check) < 0
                or _find(s, INCLUDE_EMAILS, domain_access, root_check) < 0):
            found.append("custom domain: the domain's Access policy is not Action Allow, Include Emails")
        # The Domain list offers zones, so a subdomain goes in the Subdomain field.
        if domain_access >= 0 and root_check >= 0 and _find(s, SUBDOMAIN, domain_access, root_check) < 0:
            found.append("custom domain: the Access hostname does not use the Subdomain field")
        if 0 <= first_rollback < root_check and _find(s, ROLLBACK, first_rollback + 1, root_check) >= 0:
            found.append("custom domain: production rolls forward before the domain is checked behind Access")
        # Each domain check says what to do when it fails, before the next step.
        stop_path = _find(s, STOP_PATH, domain_add, public)
        config_check = steps[6][1]
        if 0 <= root_check < forward and _find(s, STOP_BRANCH, root_check, forward) < 0:
            found.append("custom domain: the check before rolling forward does not say to stop if it fails")
        if config_check >= 0 and _find(s, STOP_BRANCH, config_check,
                                       stop_path if stop_path > config_check else public) < 0:
            found.append("custom domain: the check after rolling forward does not say what to do if it fails")
        # The stop path: the domain goes before the office comes back.
        if stop_path < 0:
            found.append("custom domain: no stop path for a domain that cannot go behind Access")
        else:
            stop = paragraph(markdown, STOP_PATH)
            remove = _find(stop, REMOVE_DOMAIN)
            again = _find(stop, ROLLBACK)
            if remove < 0 or 0 <= again < remove:
                found.append("custom domain: the stop path rolls forward before it removes the domain")

    for sentence in access_turned_off(s):
        found.append("tells the reader to turn Access off: " + sentence[:80])

    # Is my office public right now?
    if _find(s, PAGES_CONFIG, public) < 0:
        found.append("the public check does not cover pages.dev")
    if _find(s, DEPLOY_ADDR, public) < 0:
        found.append("the public check does not cover a deployment's own address")
    remedy = _find(s, ROLLBACK, public)
    if remedy < 0 or "placeholder" not in s[max(public, remedy - 120):remedy]:
        found.append("the take-offline remedy does not roll back to the placeholder")
    delete = _find(s, DELETE, public)
    if 0 <= delete < remedy:
        found.append("deleting the project comes before the rollback")
    if remedy >= 0 and _find(s, UNTICK, remedy, delete if delete > remedy else None) < 0:
        found.append("the take-offline remedy does not untick automatic production deployments")
    return found


# A known-good step, wrapped the way Markdown wraps, as the positive control: the checks must
# accept it, or a clean result on the real file means nothing.
GOOD = """## 2. Host it on Cloudflare Pages behind Cloudflare Access

**Pages, with a placeholder first**
2. Set the build output
   directory to `placeholder`.

**Access**
1. Settings → General → **Enable access
   policy**.
2. Delete the `*`.
3. Settings → General → **Enable access policy** again, for
   `*.<project>.pages.dev`.
4. Policy: Action Allow, Include Emails, your address, never Everyone.
5. In a private window, open `https://<project>.pages.dev/`. You should get the Access
   sign-in. If you see `ok`, stop: do not deploy the office.

**Then deploy the office**
1. Set the build output directory to `app`.
3. In a private window, open `https://<project>.pages.dev/instance/config.js`, then the
   deployment's `<hash>.<project>.pages.dev` address. If you see the file, follow "Is my office
   public right now?".

**Custom domain**
1. Untick Enable automatic production branch deployments.
2. Deployments → the placeholder deployment → ⋯ → **Rollback to this
   deployment**.
3. Custom domains → **Set up a domain**.
4. Zero Trust → **Add public hostname** → Subdomain `office`, Domain `example.com`, Action Allow,
   Include Emails.
5. In a private window, open `https://office.example.com/`. If you see `ok`, stop: do not go on
   to step 6.
6. Deployments → the latest office deployment → ⋯ → **Rollback to this deployment**.
7. In a private window, open
   `https://office.example.com/instance/config.js`. If you see the file, roll back to the
   placeholder at once.

**If the domain cannot go behind Access**, delete the CNAME record, then Custom domains → ⋯ →
**Remove domain**. Then roll forward: Deployments → the latest office deployment → ⋯ →
**Rollback to this deployment**.

**Certificate renewal.** Cloudflare's fix is to disable Access over the domain until it verifies.
Never do that while the office is in production. Instead, roll back to the placeholder first.

**Is my office public
right now?** Open a private window and go to `https://<project>.pages.dev/instance/config.js`
and the latest `<hash>.<project>.pages.dev` address.
1. Deployments → the placeholder deployment → ⋯ → **Rollback to this deployment**. Then untick
   automatic production deployments.
3. Last resort: Settings → Delete project.

## Next step
"""


class Controls(unittest.TestCase):
    """Each mutation the step must not survive, made on GOOD, failing for its own reason."""

    def assertFlags(self, markdown, reason):
        self.assertIn(reason, problems(markdown))

    def test_good_order_passes(self):
        self.assertEqual(problems(GOOD), [])

    def test_first_deploy_building_app_fails(self):
        old = GOOD.replace("2. Set the build output\n   directory to `placeholder`.",
                           "2. Build command: leave empty. Build output directory: `app`.")
        self.assertIn("missing: placeholder output directory", problems(old))
        both = GOOD.replace("directory to `placeholder`.",
                            "directory to `placeholder`. Build output directory: `app`.")
        self.assertFlags(both, "an `app` output directory comes before Access is set up")

    def test_placeholder_after_access_fails(self):
        moved = GOOD.replace("2. Set the build output\n   directory to `placeholder`.", "")
        moved = moved.replace("4. Policy:", "Set the build output directory to `placeholder`.\n4. Policy:")
        self.assertFlags(moved, "the first deployment is not the placeholder")

    def test_wildcard_dropped_fails(self):
        cut = GOOD.replace("3. Settings → General → **Enable access policy** again, for\n"
                           "   `*.<project>.pages.dev`.\n", "")
        self.assertFlags(cut, "Access does not keep the `*.<project>.pages.dev` application")

    def test_include_everyone_fails(self):
        self.assertFlags(GOOD.replace("Include Emails", "Include → Everyone"),
                         "an Access policy includes Everyone")

    def test_access_sign_in_check_dropped_fails(self):
        cut = GOOD.replace("5. In a private window, open `https://<project>.pages.dev/`. You should get the Access\n"
                           "   sign-in. If you see `ok`, stop: do not deploy the office.\n", "")
        self.assertFlags(cut, "no private-window Access sign-in check before the office deploys")

    def test_post_deploy_checks_dropped_fail(self):
        cut = GOOD.replace("3. In a private window, open `https://<project>.pages.dev/instance/config.js`, then the\n"
                           "   deployment's `<hash>.<project>.pages.dev` address.", "")
        self.assertFlags(cut, "no check of pages.dev /instance/config.js after the office deploys")
        self.assertFlags(cut, "no check of a deployment's own address after the office deploys")

    def test_domain_access_before_add_fails(self):
        """The old order: hostname into Access first, then add the domain."""
        moved = GOOD.replace("3. Custom domains → **Set up a domain**.\n", "")
        moved = moved.replace("5. In a private window, open `https://office.example.com/`.",
                              "3. Custom domains → **Set up a domain**.\n5. In a private window, open "
                              "`https://office.example.com/`.")
        self.assertFlags(moved, "custom domain: put the domain behind Access is missing or out of order")

    def test_domain_without_placeholder_rollback_fails(self):
        cut = GOOD.replace("2. Deployments → the placeholder deployment → ⋯ → **Rollback to this\n"
                           "   deployment**.\n", "")
        self.assertTrue([p for p in problems(cut) if p.startswith("custom domain:")], problems(cut))

    def test_domain_roll_forward_before_check_fails(self):
        moved = GOOD.replace("6. Deployments → the latest office deployment → ⋯ → **Rollback to this deployment**.\n", "")
        moved = moved.replace("4. Zero Trust", "6. Deployments → the latest office deployment → ⋯ → "
                              "**Rollback to this deployment**.\n4. Zero Trust")
        self.assertTrue([p for p in problems(moved) if p.startswith("custom domain:")], problems(moved))

    def test_domain_extra_roll_forward_before_check_fails(self):
        """The later roll forward stays in place, but an earlier one brings the office back first."""
        moved = GOOD.replace("5. In a private window, open `https://office.example.com/`.",
                             "4b. Deployments → the office → **Rollback to this deployment**.\n"
                             "5. In a private window, open `https://office.example.com/`.")
        self.assertFlags(moved, "custom domain: production rolls forward before the domain is checked behind Access")

    def test_domain_added_with_the_project_fails(self):
        moved = GOOD.replace("directory to `placeholder`.", "directory to `placeholder`. Custom domains → Set up a domain.")
        self.assertFlags(moved, "a custom domain is added outside the custom domain steps")

    def test_public_check_without_deployment_address_fails(self):
        cut = GOOD.replace("\nand the latest `<hash>.<project>.pages.dev` address.", ".")
        self.assertFlags(cut, "the public check does not cover a deployment's own address")

    def test_take_offline_remedy_dropped_fails(self):
        cut = GOOD.replace("1. Deployments → the placeholder deployment → ⋯ → **Rollback to this deployment**. Then untick\n"
                           "   automatic production deployments.\n3. Last", "3. Last")
        self.assertFlags(cut, "the take-offline remedy does not roll back to the placeholder")

    def test_delete_before_rollback_fails(self):
        moved = GOOD.replace("3. Last resort: Settings → Delete project.\n", "")
        moved = moved.replace("address.\n1. Deployments", "address.\n0. Settings → Delete project.\n1. Deployments")
        self.assertFlags(moved, "deleting the project comes before the rollback")

    def test_text_after_the_section_does_not_count(self):
        """A marker that only appears in a later section does not satisfy step 2."""
        cut = GOOD.replace("\nand the latest `<hash>.<project>.pages.dev` address.", ".")
        cut += "The latest `<hash>.<project>.pages.dev` address.\n"
        self.assertFlags(cut, "the public check does not cover a deployment's own address")

    def test_narrowing_dropped_fails(self):
        """Without deleting the `*`, <project>.pages.dev itself is never behind Access."""
        self.assertFlags(GOOD.replace("2. Delete the `*`.\n", ""),
                         "Access does not narrow the first application to `<project>.pages.dev`")

    def test_narrowing_after_re_enable_fails(self):
        moved = GOOD.replace("2. Delete the `*`.\n", "")
        moved = moved.replace("4. Policy:", "2. Delete the `*`.\n4. Policy:")
        self.assertFlags(moved, "Access does not keep the `*.<project>.pages.dev` application")

    def test_pages_root_check_dropped_fails(self):
        cut = GOOD.replace("open `https://<project>.pages.dev/`. You", "open the placeholder's address. You")
        self.assertFlags(cut, "the check before the office deploys does not open `https://<project>.pages.dev/`")

    def test_bypass_fails(self):
        self.assertFlags(GOOD.replace("Action Allow, Include Emails, your", "Action Bypass, Include Emails, your"),
                         "an Access policy uses Bypass")
        self.assertFlags(GOOD.replace("Action Allow, Include Emails, your", "Action Bypass, Include Emails, your"),
                         "the Access policy is not Action Allow")
        domain = GOOD.replace("Action Allow,\n   Include Emails.", "a policy with Action Bypass for Everyone.")
        self.assertFlags(domain, "an Access policy uses Bypass")
        self.assertFlags(domain, "an Access policy includes Everyone")
        self.assertFlags(domain, "custom domain: the domain's Access policy is not Action Allow, Include Emails")

    def test_negated_everyone_and_bypass_pass(self):
        ok = GOOD.replace("never Everyone.", "never Everyone, and never a Bypass action.")
        self.assertEqual(problems(ok), [])

    def test_allow_missing_fails(self):
        self.assertFlags(GOOD.replace("4. Policy: Action Allow, ", "4. Policy: "),
                         "the Access policy is not Action Allow")

    def test_everyone_without_include_fails(self):
        self.assertFlags(GOOD.replace("never Everyone.", "Allow for Everyone."),
                         "an Access policy includes Everyone")

    def test_remedy_without_untick_fails(self):
        cut = GOOD.replace(" Then untick\n   automatic production deployments.", "")
        self.assertFlags(cut, "the take-offline remedy does not untick automatic production deployments")

    def test_domain_pause_dropped_fails(self):
        reason = "custom domain: pause automatic production deployments is missing or out of order"
        cut = GOOD.replace("1. Untick Enable automatic production branch deployments.\n", "")
        self.assertFlags(cut, reason)
        kept_on = GOOD.replace("1. Untick Enable automatic", "1. Keep Enable automatic")
        self.assertFlags(kept_on, reason)

    def test_domain_without_subdomain_field_fails(self):
        cut = GOOD.replace("Subdomain `office`, Domain `example.com`", "`office.example.com` in the Domain list")
        self.assertFlags(cut, "custom domain: the Access hostname does not use the Subdomain field")

    def test_harmless_rewordings_pass(self):
        for old, new in (("private window", "private (incognito) window"),
                         ("Rollback to this", "Roll back to this"),
                         ("directory to `placeholder`", "directory as `placeholder`"),
                         ("Access\n   sign-in", "Access login page")):
            self.assertIn(old, GOOD)
            self.assertEqual(problems(GOOD.replace(old, new)), [], new)

    def test_output_folder_app_before_access_fails(self):
        moved = GOOD.replace("directory to `placeholder`.",
                             "directory to `placeholder`. Or skip it and set the output folder to `app` now.")
        self.assertFlags(moved, "an `app` output directory comes before Access is set up")

    def replaced(self, old, new):
        self.assertIn(old, GOOD)
        return GOOD.replace(old, new)

    def test_access_off_fails(self):
        reason = "tells the reader to turn Access off"
        never = "Never do that while the office is in production."
        for markdown in (
                self.replaced(never, "Do that now: it only takes a few minutes, and then turn Access back on."),
                self.replaced(never, "Do that now."),
                self.replaced("3. Last resort", "2. If Access gets in the way, disable Access for the project "
                                                "while the office deploys.\n3. Last resort"),
                self.replaced("3. Last resort", "2. If Access gets in the way of a deploy, disable it for the "
                                                "project while the office deploys.\n3. Last resort"),
                self.replaced("3. Last resort", "2. Turn off Access until the deploy ends.\n3. Last resort"),
                self.replaced("3. Last resort", "2. Turn Access off for a minute.\n3. Last resort"),
                self.replaced("3. Last resort", "2. If the deploy fails, deactivate the Access applications."
                                                "\n3. Last resort"),
                self.replaced("3. Last resort", "2. If Access blocks the deploy, turn it off.\n3. Last resort"),
                self.replaced("3. Last resort", "2. Switch the Access policy off.\n3. Last resort"),
                self.replaced("3. Last resort", "2. Remove the domain's Access application while the office "
                                                "deploys.\n3. Last resort"),
                self.replaced("Cloudflare's fix is to", "So, to fix it,")):
            self.assertTrue([p for p in problems(markdown) if p.startswith(reason)], markdown)

    def test_access_off_quote_needs_never_right_after(self):
        moved = self.replaced("\nNever do that while the office is in production.",
                              "\nIt is quick. Never do that while the office is in production.")
        self.assertTrue([p for p in problems(moved) if p.startswith("tells the reader to turn Access off")])

    def test_removing_access_while_down_passes(self):
        """The certificate remedy deletes the domain's own application once production is the placeholder."""
        ok = self.replaced("Instead, roll back to the placeholder first.",
                           "Instead, roll back to the placeholder first, then delete only the domain's own "
                           "Access application, and turning off builds alone is not enough.")
        self.assertEqual(problems(ok), [])

    def test_stop_path_rolls_forward_first_fails(self):
        reason = "custom domain: the stop path rolls forward before it removes the domain"
        moved = self.replaced(
            "delete the CNAME record, then Custom domains → ⋯ →\n**Remove domain**. Then roll forward: "
            "Deployments → the latest office deployment → ⋯ →\n**Rollback to this deployment**.",
            "roll forward: Deployments → the latest office deployment → ⋯ →\n**Rollback to this deployment**. "
            "Then Custom domains → ⋯ → **Remove domain**.")
        self.assertFlags(moved, reason)
        self.assertFlags(self.replaced("**Remove domain**", "**Edit domain**"), reason)
        cut = self.replaced("**If the domain cannot go behind Access**", "**If it fails**")
        self.assertFlags(cut, "custom domain: no stop path for a domain that cannot go behind Access")

    def test_checks_without_a_stop_branch_fail(self):
        for old, reason in (
                (" If you see `ok`, stop: do not deploy the office.",
                 "the check before the office deploys does not say to stop if it fails"),
                (' If you see the file, follow "Is my office\n   public right now?".',
                 "the check after the office deploys does not say what to do if it fails"),
                (" If you see `ok`, stop: do not go on\n   to step 6.",
                 "custom domain: the check before rolling forward does not say to stop if it fails"),
                (" If you see the file, roll back to the\n   placeholder at once.",
                 "custom domain: the check after rolling forward does not say what to do if it fails")):
            self.assertFlags(self.replaced(old, ""), reason)
            self.assertFlags(self.replaced(old, " If you see `ok`, that is fine, carry on."), reason)

    def test_renamed_heading_fails_loudly(self):
        with self.assertRaises(ValueError):
            problems(GOOD.replace("## 2. Host it", "## 2. Put it"))


class SetupPagesOrder(unittest.TestCase):
    def test_setup_md_keeps_the_safe_order(self):
        with open(SETUP, encoding="utf-8") as f:
            self.assertEqual(problems(f.read()), [])

    def test_setup_md_says_what_is_public_and_what_is_not(self):
        with open(SETUP, encoding="utf-8") as f:
            s = pages_section(f.read())
        for phrase in ("`config.js` names every repo you watch", "Live GitHub data is not exposed",
                       "bound to `127.0.0.1` needs no Access"):
            self.assertIn(phrase, s)


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
