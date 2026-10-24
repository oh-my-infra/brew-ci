# brew-ci maintenance

## Read first

- Read `README.md`, `VERSIONING.md`, and the affected workflow, composite action or script. Check Git status and preserve concurrent edits; do not reset, clean, stash, force-push, or switch branches without instruction.
- This public repository owns shared source-release automation and reproducible packaging. Caller products own their triggers and release policy; Homebrew Formulae/Casks and autobump remain in the tap repository.

## Release contracts

- Preserve canonical versions, immutable tags/releases, archive paths, checksum validation, deterministic packaging, and caller permissions. Document any intentional input/output or compatibility change.
- Keep each interface contract separate: legacy source-beta/promote workflows accept an explicitly selected candidate and digest; the opt-in fast_release coordinator permits automatic promotion after required checks. Both preserve exact candidate identity and original artifact bytes. See README and VERSIONING.
- Keep `automation-ref`, reusable workflow references and implementation action references pinned as documented. Changes here do not authorize updating or releasing downstream products.
- Verification with `publish: false` still runs the caller-provided command. Check its effects before running; do not dispatch release workflows, create tags/releases, install packages, or touch the tap just to validate documentation.
- Keep credentials, signing assets, generated archives and actual caller runtime data out of Git and logs.

## Validation and handoff

- Relevant local checks are `python3 -m unittest discover -s tests -v`, `bash -n scripts/source_release.sh scripts/source_beta.sh scripts/promote_source_beta.sh`, and `git diff --check`; see `.github/workflows/ci.yml`.
- Use temporary fixture repositories for tests, not real product releases. Respect explicit requests to skip CI/tests and report checks actually run.
- Update `README.md` for workflow usage and `VERSIONING.md` for version policy; do not maintain a second policy in this file. Handoff includes the exact commit, compatibility impact, actual checks, and any separately authorized rollout still pending.
