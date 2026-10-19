#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_NAME:?PROJECT_NAME is required}"
: "${BETA_TAG:?BETA_TAG is required}"
: "${EXPECTED_SHA256:?EXPECTED_SHA256 is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

if [[ ! "$BETA_TAG" =~ ^v([0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[1-9][0-9]*)-beta\.([1-9][0-9]*)$ ]]; then
  echo 'beta-tag must use vYYYY.MM.DD.N-beta.M with positive, non-zero-padded counters' >&2
  exit 1
fi
version="${BASH_REMATCH[1]}"
stable_tag="v$version"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$script_dir/validate_version.py" "$version"
[[ "$EXPECTED_SHA256" =~ ^[0-9a-fA-F]{64}$ ]] || {
  echo 'expected-sha256 must be exactly 64 hexadecimal characters' >&2
  exit 1
}
expected_sha256="$(printf '%s' "$EXPECTED_SHA256" | tr '[:upper:]' '[:lower:]')"

[[ "$(gh release view "$BETA_TAG" --json isPrerelease --jq .isPrerelease)" == true ]] || {
  echo "$BETA_TAG is not a prerelease" >&2
  exit 1
}
if gh release view "$stable_tag" >/dev/null 2>&1; then
  echo "Stable Release $stable_tag already exists; refusing to overwrite it." >&2
  exit 1
fi

candidate_sha="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$BETA_TAG" --jq .object.sha)"
[[ "$candidate_sha" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Could not resolve $BETA_TAG to an immutable commit." >&2
  exit 1
}
default_branch="$(gh api "repos/$GITHUB_REPOSITORY" --jq .default_branch)"
git check-ref-format --branch "$default_branch" >/dev/null 2>&1 || {
  echo "Repository returned an invalid default branch: $default_branch" >&2
  exit 1
}
git fetch --no-tags origin "$default_branch"
default_head="$(git rev-parse FETCH_HEAD)"
[[ "$default_head" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Could not resolve origin/$default_branch to an immutable commit." >&2
  exit 1
}
git merge-base --is-ancestor "$candidate_sha" "$default_head" || {
  echo "Candidate commit $candidate_sha is not contained in origin/$default_branch at $default_head." >&2
  exit 1
}

asset="$PROJECT_NAME-$version.tar.gz"
download_dir="$(mktemp -d "${TMPDIR:-/tmp}/brew-ci-promote.XXXXXXXX")"
trap 'rm -rf -- "$download_dir"' EXIT
gh release download "$BETA_TAG" --dir "$download_dir" --pattern "$asset" --pattern "$asset.sha256"
[[ -f "$download_dir/$asset" && -f "$download_dir/$asset.sha256" ]] || {
  echo "Candidate must contain exactly the expected archive and checksum names." >&2
  exit 1
}
(cd "$download_dir" && shasum -a 256 -c "$asset.sha256")
actual_sha256="$(shasum -a 256 "$download_dir/$asset" | awk '{ print $1 }')"

expected_prefix="$PROJECT_NAME-$version/"
tar -tzf "$download_dir/$asset" | awk -v prefix="$expected_prefix" '
  BEGIN { found = 0 }
  {
    found = 1
    if (index($0, prefix) != 1 || $0 ~ /(^|\/)\.\.($|\/)/ || $0 ~ /^\// || $0 ~ /\\/) exit 1
  }
  END { if (!found) exit 1 }
'
if LC_ALL=C tar -tvzf "$download_dir/$asset" | awk '$1 ~ /^[lh]/ { found = 1 } END { exit found ? 0 : 1 }'; then
  echo 'Candidate archive contains a link.' >&2
  exit 1
fi
archive_version="$(tar -xOf "$download_dir/$asset" "$PROJECT_NAME-$version/VERSION" | tr -d '[:space:]')"
[[ "$archive_version" == "$version" ]] || {
  echo "Candidate archive VERSION is $archive_version, expected $version." >&2
  exit 1
}

declared_sha256="$(awk -v file="$asset" '$2 == file || $2 == "*" file { print $1 }' "$download_dir/$asset.sha256")"
[[ "$declared_sha256" =~ ^[0-9a-fA-F]{64}$ ]] || {
  echo 'Candidate checksum file has an unexpected format.' >&2
  exit 1
}
declared_sha256="$(printf '%s' "$declared_sha256" | tr '[:upper:]' '[:lower:]')"
[[ "$actual_sha256" == "$declared_sha256" && "$actual_sha256" == "$expected_sha256" ]] || {
  echo "Candidate SHA-256 does not match the approved digest." >&2
  exit 1
}

gh release create "$stable_tag" "$download_dir/$asset" "$download_dir/$asset.sha256" \
  --target "$candidate_sha" --title "$version" \
  --notes "Promoted without rebuilding from candidate $BETA_TAG ($candidate_sha)."
printf 'version=%s\ntag=%s\ncandidate-tag=%s\ncommit=%s\nsha256=%s\n' \
  "$version" "$stable_tag" "$BETA_TAG" "$candidate_sha" "$actual_sha256" >> "$GITHUB_OUTPUT"
