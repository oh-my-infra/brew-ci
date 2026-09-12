# brew-ci

Shared, secret-free release automation for first-party `oh-my-brew` command-line
projects. It owns the version contract, reproducible source packaging, and the
reusable GitHub workflow used to create releases consumed by
[`oh-my-brew/homebrew-tap`](https://github.com/oh-my-brew/homebrew-tap).

Current release: `v2026.09.12.1`.

The Homebrew tap remains a downstream consumer. Formula and Cask updates,
livechecks, autobump, and `brew test-bot` stay in that repository.

The explicit `$release-onboarding` Codex Skill is maintained in the private
`assassinor/github` workspace repository under `.agents/skills`. This repository
remains the public source of truth for the executable release policy and shared
workflow.

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
