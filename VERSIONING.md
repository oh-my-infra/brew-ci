# Versioning policy

## Canonical CalVer

First-party continuously delivered projects use:

```text
YYYY.MM.DD.N
```

- `YYYY.MM.DD` is the release date in `Asia/Shanghai`.
- `N` is a positive, non-zero-padded integer scoped to one repository and day.
- The first release of a day is `.1`, followed by `.2`, `.3`, and so on.
- Repository version files and release assets omit the `v` prefix.
- Git tags add the prefix: `vYYYY.MM.DD.N`.

Do not use `.01`: Homebrew and RubyGems normalize `.1` and `.01` as the same
version, which makes upgrades ambiguous.

## Apple applications

App Store/TestFlight application marketing versions use three components,
`YYYY.MM.DD`; Git tags and published artifacts use `vYYYY.MM.DD.N`, with
independent monotonic Apple build numbers. Direct-distributed miniTools retains
its complete four-component `YYYY.MM.DD.N` display version and an independent
Sparkle build identity as specified in its DISTRIBUTION.md. Do not apply the
App Store display-version rule to all macOS applications.

## Upstream-derived packages

Repackaged upstream software may use `<upstream-version>.<revision>` when the
upstream version is the primary compatibility signal. RustDeskX is the current
exception. External Formulae retain their upstream version schemes.

## Release invariants

- A version source is changed in the same commit as its release inputs.
- A release workflow validates the version before packaging. Verification with
  `publish: false` accepts an existing valid version without requiring today's
  date, packages twice, and never creates tags or releases.
- Tags and releases are never overwritten, renamed, or moved.
- Assets use deterministic names containing the project and full version.
- Homebrew consumes the exact published version and immutable asset checksum.
- A corrected release receives a new version; an incorrect historical release
  remains as an audit record.

## Transition

Historical versions without `.N` and historical semantic versions remain
valid records. Projects adopt this policy with a new compliant release; no
history rewrite is required.

## Candidate-first opt-in

Automatic candidates reserve a new date revision before building, including
unpublished/superseded candidates. GitHub run IDs identify immutable Beta attempts.
The formal Git tag targets the protected squash-merge commit whose Git tree is
identical to the tested candidate; the manifest preserves both source identities.
A successful automated validation replaces human approval only for opted-in callers.
