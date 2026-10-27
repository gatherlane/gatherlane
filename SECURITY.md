# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: on the repository, open **Security**, then
**Report a vulnerability**. Do not open a public issue for a security problem.

You can expect a first reply within seven days. We will agree on a fix and a disclosure date with
you, and credit you in the release notes unless you prefer otherwise.

## Supported versions

Only the latest commit on `main` is supported. There are no release branches yet.

## What is in scope

Gatherlane holds GitHub tokens, so these matter most:

- **Tokens in the page.** Read-only tokens, and the optional token with Actions write access used
  for "Run now", are kept in the browser (session storage, or local storage when the user ticks
  "Remember") and must only ever be sent to `api.github.com`. Anything
  that sends a token elsewhere, or lets a status file, PR title or other GitHub content run script
  in the page, is a vulnerability.
- **The content security policy** in `app/_headers`. A way around it is in scope.
- **The reporter** (`tools/gatherlane.py`). It reads a write token from the environment or from
  `~/.config/gatherlane/env`. Leaking that token (for example in logs or commit messages) is in scope.
- **Status files are untrusted input.** Anyone who can write to the status branch can write any
  text there; the page must show it as text, never as markup.

Out of scope: the security of GitHub itself, of the hosting you choose, and attacks that need
write access to your own repository's `main` branch.
