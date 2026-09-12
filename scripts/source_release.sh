#!/usr/bin/env bash
# Shared entry point for the composite action; inputs are passed through env.
set -euo pipefail

publish="${PUBLISH-true}"
case "$publish" in
  true|false) ;;
  *) echo 'publish must be exactly true or false' >&2; exit 1 ;;
esac

: "${VERSION_FILE:?VERSION_FILE is required}"
: "${VALIDATE_COMMAND:?VALIDATE_COMMAND is required}"
: "${PROJECT_NAME:?PROJECT_NAME is required}"
: "${PACKAGE_PATHS:?PACKAGE_PATHS is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
version="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [[ "$publish" == true ]]; then
  python3 "$script_dir/validate_version.py" "$version" --require-today
else
  python3 "$script_dir/validate_version.py" "$version"
fi
tag="v$version"
if [[ "$publish" == true ]] && gh release view "$tag" >/dev/null 2>&1; then
  echo "Release $tag already exists; bump $VERSION_FILE first." >&2
  exit 1
fi
printf 'version=%s\ntag=%s\n' "$version" "$tag" >> "$GITHUB_OUTPUT"

bash -euo pipefail -c "$VALIDATE_COMMAND"
paths=()
while IFS= read -r path; do
  [[ -z "$path" ]] || paths+=("$path")
done <<< "$PACKAGE_PATHS"
if [[ "${#paths[@]}" -eq 0 ]]; then
  echo 'package-paths must contain at least one path' >&2
  exit 1
fi
asset="$PROJECT_NAME-$version.tar.gz"
python3 "$script_dir/package_release.py" \
  --name "$PROJECT_NAME" --version "$version" --output "dist/$asset" "${paths[@]}"
(cd dist && shasum -a 256 "$asset" > "$asset.sha256")

if [[ "$publish" == false ]]; then
  repeat_dir="$(mktemp -d "${TMPDIR:-/tmp}/brew-ci-reproducibility.XXXXXXXX")"
  trap 'rm -rf -- "$repeat_dir"' EXIT
  python3 "$script_dir/package_release.py" \
    --name "$PROJECT_NAME" --version "$version" --output "$repeat_dir/$asset" "${paths[@]}"
  cmp "dist/$asset" "$repeat_dir/$asset"
  echo "Dry run complete: two archives are identical; no tag or release was created."
else
  : "${GITHUB_SHA:?GITHUB_SHA is required for publishing}"
  gh release create "$tag" "dist/$asset" "dist/$asset.sha256" \
    --target "$GITHUB_SHA" --title "$version" --generate-notes
fi
