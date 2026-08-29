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

Apple application marketing versions remain three components:
`YYYY.MM.DD`. Their Git tags and published artifact versions use
`vYYYY.MM.DD.N`; Apple build numbers remain independent monotonic integers.

## Upstream-derived packages

Repackaged upstream software may use `<upstream-version>.<revision>` when the
upstream version is the primary compatibility signal. RustDeskX is the current
exception. External Formulae retain their upstream version schemes.

## Release invariants

- A version source is changed in the same commit as its release inputs.
- A release workflow validates the version before packaging.
- Tags and releases are never overwritten, renamed, or moved.
- Assets use deterministic names containing the project and full version.
- Homebrew consumes the exact published version and immutable asset checksum.
- A corrected release receives a new version; an incorrect historical release
  remains as an audit record.

## Transition

Historical versions without `.N` and historical semantic versions remain
valid records. Projects adopt this policy with a new compliant release; no
history rewrite is required.
