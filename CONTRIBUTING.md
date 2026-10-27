# Contributing to Gatherlane

Thank you for helping. Gatherlane is small on purpose: a static page, a standard-library reporter
and no backend. Changes that keep it that way are the easiest to accept.

## The one rule

**The office never shows a status that did not come from a status file or from GitHub.** Every
badge, inbox item and card must trace back to a real event. Sample data is always labelled SAMPLE,
and live and sample data are never mixed. A change that guesses, interpolates or fills in a status
will not be merged, however nice it looks. Decoration (bobbing characters, lamps, the walking
"you") is fine as long as it says nothing about status.

## Layout

- `app/js/` is the engine. It must work for any office and must not name any particular fleet.
- `app/instance/` is one office: `config.js`, `building.js`, `sample.js`. In this repository it is
  a copy of `examples/instance/`. Change the example there, and keep the two in step.
- `tools/gatherlane.py` is the reporter. Standard library only, Python 3.9 or later.
- `schema/` holds the JSON Schemas for status files and `control/pause.json`. A change to the
  status format needs a schema change, a reporter change and an app change in the same pull request.

## Running the tests

```sh
npm ci && npx playwright install chromium
npm test
```

`npm run test:py` runs the reporter tests and needs nothing but Python. `npm run test:browser` and
`npm run test:example` run the Playwright smoke tests in sample mode and in a mocked live mode.
CI runs all of them on every pull request.

## Pull requests

- One change per pull request, with a test when it fixes a bug (the test should fail without the fix).
- Say how you checked it: the commands you ran and what they printed. Screenshots help for
  anything visual; say whether they are from a real browser or from the Playwright tests.
- Keep the page free of new network destinations. The content security policy in `app/_headers`
  only allows `api.github.com`, and tokens must never go anywhere else.
- No new runtime dependencies for the page or the reporter without discussing it in an issue first.

Good first issues are labelled `good first issue`: new furniture, mascots and props, runner
snippets for other schedulers, and documentation.

## Licence

Gatherlane is licensed under Apache-2.0. By contributing you agree that your contribution is
licensed under the same terms (Apache-2.0, section 5). Please add
`SPDX-License-Identifier: Apache-2.0` at the top of new source files, as the existing ones do.

## Conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).
