# release-ci

Shared, secret-free release automation for first-party `omzcj` command-line
projects. It owns the version contract, reproducible source packaging, and the
reusable GitHub workflow used to create releases consumed by
[`omzcj/homebrew-omzcj`](https://github.com/omzcj/homebrew-omzcj).

Current release: `v2026.08.29.2`.

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
    uses: omzcj/release-ci/.github/workflows/source-release.yml@COMMIT_SHA
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
