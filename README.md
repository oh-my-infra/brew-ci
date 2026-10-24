# brew-ci

Shared, secret-free release automation for first-party `oh-my-brew` command-line
projects. It owns the version contract, reproducible source packaging, and the
reusable GitHub workflow used to create releases consumed by
[`oh-my-brew/homebrew-tap`](https://github.com/oh-my-brew/homebrew-tap).

Current release: `v2026.09.12.1`.

The Homebrew tap remains a downstream consumer. Formula and Cask updates,
livechecks, autobump, and `brew test-bot` stay in that repository.

## Candidate beta and promotion

`source-beta.yml` packages an exact caller commit as an immutable prerelease
`vVERSION-beta.N`. It runs the caller's validation command, builds the archive
twice, and publishes only when both byte streams match. The archive keeps the
canonical stable `VERSION`; the beta suffix identifies the candidate Release,
not a different payload version. Its workflow outputs the immutable tag and
archive SHA-256; both values form the approval identity passed to promotion.

`promote-source-beta.yml` accepts only an explicitly selected beta tag and the
SHA-256 recorded when that candidate was approved. It reads the repository's
default branch through the GitHub API, fetches its current remote head, and
requires the candidate commit to be its ancestor. It downloads the candidate
archive and checksum, verifies their names, candidate checksum, approved
digest, paths and embedded `VERSION`, then attaches those exact bytes to `vVERSION`.
Promotion never rebuilds or replaces an existing stable Release.

Both reusable workflows require `automation-ref`, the same immutable brew-ci
commit used after `@` in the caller. This lets the workflow check out its helper
scripts without using a moving branch. A new brew-ci release therefore has to
be published before a product can pin and adopt these workflows.

Beta Releases must be marked prerelease. GitHub `releases/latest`, Homebrew
livecheck and normal stable updaters continue to see only stable Releases.

Maintenance starts with [AGENTS.md](AGENTS.md), this README and
[VERSIONING.md](VERSIONING.md). The retired private `assassinor/github`
workspace is not required; this repository owns the executable release policy
and shared workflows.

## Release contract

- Canonical versions use `YYYY.MM.DD.N`, without a leading `v`.
- Git tags use `vYYYY.MM.DD.N`.
- `N` starts at `1` for each repository and date and is never zero-padded.
- A release date is interpreted in `Asia/Shanghai` and must equal the current
  release date.
- Existing historical tags are immutable and are never renamed or moved.
- Release archives and SHA-256 files are generated reproducibly.

See [VERSIONING.md](VERSIONING.md) for the complete policy.

## Reusable workflow

Call `.github/workflows/source-release.yml` at an immutable commit SHA. The
caller owns its triggers and grants `contents: write`; the called workflow
cannot elevate caller permissions.

```yaml
jobs:
  release:
    permissions:
      contents: write
    uses: oh-my-infra/brew-ci/.github/workflows/source-release.yml@COMMIT_SHA
    with:
      runner: macos-15-intel
      project-name: example
      version-file: VERSION
      validate-command: ./tests/test.sh
      package-paths: |
        VERSION
        LICENSE
        example
```

The implementation action used by the reusable workflow is independently
pinned to a full commit SHA.

## Verification without publishing

The reusable workflow accepts `publish` as a boolean, defaulting to `true` for
existing callers. Pass `publish: false` to validate the existing version, run
the project's validation command, and create two archives whose bytes must
match. This mode skips today's-release-date and already-published checks and
does not create tags or releases. It leaves `VERSION` unchanged and writes the
archive and checksum under `dist/` in the caller checkout.

A manual caller can default to verification while preserving automatic source
releases on push:

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      publish:
        description: Publish a new release
        type: boolean
        default: false

jobs:
  release:
    permissions:
      contents: write
    uses: oh-my-infra/brew-ci/.github/workflows/source-release.yml@COMMIT_SHA
    with:
      publish: ${{ github.event_name == 'push' || inputs.publish == true }}
      # Supply the project inputs shown above.
```

The composite action accepts only the exact strings `"true"` and `"false"`;
invalid values fail before validation or publishing. Its `tag` output is the
derived tag name, including in verification mode where no tag is created.
Verification still executes the caller-provided validation command, which must
itself be suitable for running without publishing.

## Migration and immutable references

This repository moved from `omzcj/release-ci` to `oh-my-infra/brew-ci`. Update
callers to the new repository and the full commit SHA for this release. Old
workflow versions contain the previous owner in their nested action reference;
changing only the caller's owner while keeping an old workflow SHA is not
sufficient. Historical tags and releases remain unchanged, and rerunning
historical workflows with the old repository name is not supported.

Shared automation releases use annotated, signed `vYYYY.MM.DD.N` tags. Keep the
workflow SHA and its independently pinned implementation action SHA immutable.

## Local maintenance checks

See [AGENTS.md](AGENTS.md) for maintenance and release boundaries. The local
checks used by `.github/workflows/ci.yml` are:

```sh
python3 -m unittest discover -s tests -v
bash -n scripts/source_release.sh scripts/source_beta.sh scripts/promote_source_beta.sh
git diff --check
```

These checks do not require publishing a product or creating a release tag.

## Candidate-first automatic releases

`scripts/fast_release.py` is an opt-in coordinator used by omcli and miniTools.
Trusted default-branch workflows prepare an isolated version candidate PR from a
same-repository writer's requested source. Packaging and quality checks run in
parallel; Beta publication does not wait for tests. Successful checks permit a
protected squash merge and promotion of the downloaded Beta bytes, never a rebuild.
The merged Git tree must equal the tested candidate tree.

A serialized `release-state` branch reserves versions and records the latest
candidate. Source PR changes and newer registered candidates invalidate old
publication. Preparation, Beta feed writes, and final promotion share a publication
lock; compute jobs remain parallel. Every candidate has an immutable manifest,
commit, tree, run identity and SHA-256. Reruns retain the same identity.

Callers retain their required branch checks and Apple signing/notarization policy.
Automatic Git tags use a dedicated per-repository SSH signing secret and a public
allowed-signers file pinned in trusted default-branch code. This verifies the tag
cryptographically without copying a user's personal signing key or requiring
account-wide signing-key administration. Existing release workflows are unchanged
for callers that have not opted in. Tests use isolated fixtures and mocked APIs.
