# Integration contract

## Generic source projects

The project keeps a thin workflow with its own trigger and permissions. It
calls `omzcj/release-ci/.github/workflows/source-release.yml` at the full commit
SHA for an immutable `release-ci` CalVer tag.

Required inputs:

- `project-name`: canonical lowercase archive prefix.
- `version-file`: normally `VERSION`.
- `validate-command`: a repository-owned test or validation command.
- `package-paths`: newline-separated, repository-relative release inputs.
- `runner`: only override when project validation requires a specific runner.

The caller grants `contents: write`. Do not pass repository, organization,
Apple, or personal secrets to the generic workflow.

## Migration checks

- Confirm `VERSION` is the single canonical version source and is included in
  the archive.
- Confirm executable bits, symlinks, archive root, and Formula installation
  paths survive the shared packager.
- Confirm the release Tag does not already exist.
- Confirm the date matches `Asia/Shanghai` on the intended release day.
- Confirm the project-specific validation runs before the Release is created.
- Confirm generated archives are byte-for-byte reproducible.

## Homebrew boundary

`release-ci` creates the upstream Release. `homebrew-omzcj` consumes it and owns
Formula/Cask URLs, checksums, livechecks, autobump, and `brew test-bot`.

When changing from GitHub-generated source archives to explicit Release assets,
update the Formula URL shape after the new asset exists. Run `brew audit`,
installation/test checks where practical, and Tap CI before merging.

## External mutations

Commits within an explicitly requested onboarding are in scope. Creating or
pushing a Tag, publishing a Release, triggering an upload, changing a remote
Formula, or merging a Tap PR requires explicit authorization for that action.
