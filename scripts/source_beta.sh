#!/usr/bin/env bash
set -euo pipefail

: "${VERSION_FILE:?VERSION_FILE is required}"
: "${VALIDATE_COMMAND:?VALIDATE_COMMAND is required}"
: "${PROJECT_NAME:?PROJECT_NAME is required}"
: "${PACKAGE_PATHS:?PACKAGE_PATHS is required}"
: "${BETA_NUMBER:?BETA_NUMBER is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
: "${SOURCE_COMMIT:?SOURCE_COMMIT is required}"

[[ "$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'source-commit must be exactly 40 lowercase hexadecimal characters' >&2
  exit 1
}

[[ "$BETA_NUMBER" =~ ^[1-9][0-9]*$ ]] || {
  echo 'beta-number must be a non-zero-padded positive integer' >&2
  exit 1
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
version="$(tr -d '[:space:]' < "$VERSION_FILE")"
python3 "$script_dir/validate_version.py" "$version" --require-today
tag="v$version-beta.$BETA_NUMBER"

if gh release view "$tag" >/dev/null 2>&1; then
  echo "Candidate Release $tag already exists; choose the next beta number." >&2
  exit 1
fi
if gh release view "v$version" >/dev/null 2>&1; then
  echo "Stable Release v$version already exists; choose the next version." >&2
  exit 1
fi

printf 'version=%s\ntag=%s\n' "$version" "$tag" >> "$GITHUB_OUTPUT"
bash -euo pipefail -c "$VALIDATE_COMMAND"

paths=()
while IFS= read -r path; do
  [[ -z "$path" ]] || paths+=("$path")
done <<< "$PACKAGE_PATHS"
[[ "${#paths[@]}" -gt 0 ]] || {
  echo 'package-paths must contain at least one path' >&2
  exit 1
}

asset="$PROJECT_NAME-$version.tar.gz"
python3 "$script_dir/package_release.py" \
  --name "$PROJECT_NAME" --version "$version" --output "dist/$asset" "${paths[@]}"
(cd dist && shasum -a 256 "$asset" > "$asset.sha256")
candidate_sha256="$(shasum -a 256 "dist/$asset" | awk '{ print $1 }')"

repeat_dir="$(mktemp -d "${TMPDIR:-/tmp}/brew-ci-beta-reproducibility.XXXXXXXX")"
trap 'rm -rf -- "$repeat_dir"' EXIT
python3 "$script_dir/package_release.py" \
  --name "$PROJECT_NAME" --version "$version" --output "$repeat_dir/$asset" "${paths[@]}"
cmp "dist/$asset" "$repeat_dir/$asset"
printf 'sha256=%s\n' "$candidate_sha256" >> "$GITHUB_OUTPUT"

gh release create "$tag" "dist/$asset" "dist/$asset.sha256" \
  --target "$SOURCE_COMMIT" --title "$version beta $BETA_NUMBER" --prerelease \
  --notes "Candidate built from $SOURCE_COMMIT. Promote only after explicit user approval."
