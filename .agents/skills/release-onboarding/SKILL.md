---
name: release-onboarding
description: Connect an existing first-party command-line project to omzcj CalVer, reproducible GitHub Release assets, and downstream Homebrew updates. Use only when explicitly invoked for release onboarding or migration; use the Apple-specific skill for signing, notarization, or TestFlight.
---

# Release Onboarding

Connect an existing project to `omzcj/release-ci` without changing its product
behavior. Do not create application source code or a new repository.

1. Read the repository root `VERSIONING.md`; it and the executable validator
   are the policy source of truth. Do not duplicate or relax their regex.
2. Inspect the working tree, remote, current version source, release tags,
   tests, build inputs, existing workflows, and any Formula in
   `omzcj/homebrew-omzcj` before editing.
3. Use canonical `YYYY.MM.DD.N` unless the project is an upstream-derived
   package or external Formula covered by an explicit policy exception.
4. Preserve project-specific validation in a repository script or the thin
   caller workflow. Pin the reusable workflow to a full release commit SHA.
5. Package only declared repository-relative paths. Never include credentials,
   build caches, local configuration, or untracked files.
6. Run the local project checks, release-ci tests, archive reproducibility
   check, and workflow syntax checks that apply to the change.
7. Show the proposed commit, Tag, Release assets, and Tap change before any
   external mutation. Onboarding does not itself authorize creating a Tag,
   Release, or Homebrew PR.

Never delete, move, or overwrite a historical Tag or Release. Correct mistakes
with a new revision. Do not add signing keys or extra release secrets; the
generic source workflow uses the caller's scoped `GITHUB_TOKEN`.

For exact caller inputs, migration checks, and Tap boundaries, read
[references/integration-contract.md](references/integration-contract.md).

If the project needs Developer ID signing, notarization, App Store profiles, or
TestFlight, use `$apple-release-onboarding` instead and keep this generic source
workflow out of the Apple release path.
