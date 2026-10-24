#!/usr/bin/env python3
"""Candidate-first releases. Called only by trusted default-branch workflows."""
import argparse
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import tarfile
from zoneinfo import ZoneInfo


def require(test, message):
    if not test:
        raise ValueError(message)


def run(*args, cwd=None):
    return subprocess.check_output(args, text=True, cwd=cwd).strip()


def api(path, method='GET', data=None, missing=False):
    args = ['gh', 'api', f'repos/{os.environ["GITHUB_REPOSITORY"]}/{path}', '--method', method]
    if data is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None, text=True, capture_output=True)
    if missing and result.returncode and 'HTTP 404' in result.stderr:
        return None
    require(result.returncode == 0, result.stderr)
    return json.loads(result.stdout) if result.stdout.strip() else None


def get_file(path, ref):
    item = api(f'contents/{path}?ref={ref}', missing=True)
    return base64.b64decode(item['content']) if item else None


def state():
    raw = get_file('.release-state.json', 'release-state')
    return json.loads(raw) if raw else None


def current(meta, existing=None):
    active = state() if existing is None else existing
    require(active is not None and active['run_id'] == meta['run_id'] and active['candidate'] == meta['candidate'], 'Superseded candidate; no publication permitted')
    if meta.get('source_pr'):
        pr = api(f'pulls/{meta["source_pr"]}')
        require(pr['state'] == 'open' and pr['head']['sha'] == meta['source'], 'Source PR changed or closed; candidate superseded')
    return active


def write_state(meta):
    ref = api('git/ref/heads/release-state', missing=True)
    parent = ref['object']['sha'] if ref else meta['base']
    tree = api(f'git/commits/{parent}')['tree']['sha']
    blob = api('git/blobs', 'POST', {'content': json.dumps(meta, sort_keys=True), 'encoding': 'utf-8'})['sha']
    tree = api('git/trees', 'POST', {'base_tree': tree, 'tree': [{'path': '.release-state.json', 'mode': '100644', 'type': 'blob', 'sha': blob}]})['sha']
    commit = api('git/commits', 'POST', {'message': f'Release intent {meta["run_id"]}', 'tree': tree, 'parents': [parent]})['sha']
    if ref:
        api('git/refs/heads/release-state', 'PATCH', {'sha': commit, 'force': False})
    else:
        api('git/refs', 'POST', {'ref': 'refs/heads/release-state', 'sha': commit})


def allocate_version(today, versions):
    pattern = re.compile(re.escape(today) + r'\.([1-9][0-9]*)$')
    used = [int(m[1]) for v in versions if (m := pattern.fullmatch(v))]
    return f'{today}.{max(used, default=0) + 1}'


def prepare():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    repo = api('')
    default = repo['default_branch']
    source_pr = event.get('pull_request')
    actor = os.environ['GITHUB_ACTOR']
    permission = api(f'collaborators/{actor}/permission')['permission']
    require(permission in ('admin', 'write', 'maintain'), 'Only repository writers can request a release')
    if source_pr:
        require(source_pr['head']['repo']['full_name'] == os.environ['GITHUB_REPOSITORY'] and not source_pr['draft'], 'Only ready same-repository PRs can release')
        require(not source_pr['head']['ref'].startswith('release/auto-'), 'Candidate PR cannot recursively release')
        source = source_pr['head']['sha']
    else:
        source = event['inputs']['source_ref']
        require(re.fullmatch('[0-9a-f]{40}', source), 'source_ref must be an exact commit')
        branches = api(f'commits/{source}/branches-where-head')
        require(branches, 'Manual source must be the head of a branch in this repository')
    base = api(f'git/ref/heads/{default}')['object']['sha']
    run_id = int(os.environ['GITHUB_RUN_ID'])
    previous = state()
    if previous:
        require(run_id >= previous['run_id'], 'A newer release request already exists')
        if run_id == previous['run_id']:
            require(previous['source'] == source, 'Rerun source changed')
            current(previous)
            return previous
    releases = api('releases?per_page=100')
    versions = [r['tag_name'].removeprefix('v').split('-beta.')[0] for r in releases]
    if previous:
        versions.append(previous['version'])
    product = os.environ['PRODUCT']
    version_file = 'VERSION' if product == 'omcli' else 'Support/Info.plist'
    raw = get_file(version_file, default)
    versions.append(raw.decode().strip() if product == 'omcli' else plistlib.loads(raw)['CFBundleShortVersionString'])
    today = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y.%m.%d')
    version = allocate_version(today, versions)
    branch = f'release/auto-{run_id}'
    api('git/refs', 'POST', {'ref': f'refs/heads/{branch}', 'sha': base})
    # Merge the requested source into an isolated branch before testing; never alter the developer's branch.
    api('merges', 'POST', {'base': branch, 'head': source, 'commit_message': f'Prepare source {source} for release'})
    parent = api(f'git/ref/heads/{branch}')['object']['sha']
    old = api(f'contents/{version_file}?ref={parent}')
    raw = base64.b64decode(old['content'])
    if product == 'omcli':
        raw = (version + '\n').encode()
    else:
        plist = plistlib.loads(raw)
        plist['CFBundleShortVersionString'] = version
        raw = plistlib.dumps(plist, sort_keys=False)
    result = api(f'contents/{version_file}', 'PUT', {'message': f'Release {product} {version}', 'branch': branch, 'sha': old['sha'], 'content': base64.b64encode(raw).decode()})
    candidate = result['commit']['sha']
    tree = api(f'git/commits/{candidate}')['tree']['sha']
    pr = api('pulls', 'POST', {'title': f'Release {product} {version}', 'head': branch, 'base': default, 'body': f'Automatic candidate from source `{source}`. Candidate `{candidate}`.\nBeta is built immediately; checks run in parallel and the same artifact is promoted automatically.\nRun: https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{run_id}'})
    meta = {'product': product, 'version': version, 'source': source, 'source_pr': source_pr['number'] if source_pr else None, 'candidate': candidate, 'tree': tree, 'base': base, 'default': default, 'branch': branch, 'pr': pr['number'], 'run_id': run_id, 'beta_tag': f'v{version}-beta.{run_id}', 'stable_tag': f'v{version}', 'phase': 'preparing'}
    write_state(meta)
    print(f'Candidate PR: {pr["html_url"]}')
    return meta


def manifest(meta, directory):
    name = f'omcli-{meta["version"]}.tar.gz' if meta['product'] == 'omcli' else f'miniTools-{meta["version"]}.zip'
    path = directory / name
    require(path.is_file(), f'Missing artifact {name}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / (name + '.sha256')).write_text(f'{digest}  {name}\n')
    result = dict(meta, asset=name, sha256=digest)
    (directory / 'release-manifest.json').write_text(json.dumps(result, sort_keys=True) + '\n')
    return result


def verify_payload(meta, directory):
    manifest_path = directory / 'release-manifest.json'
    payload = json.loads(manifest_path.read_text())
    for field in ('product', 'version', 'candidate', 'tree', 'run_id', 'beta_tag'):
        require(payload[field] == meta[field], f'Manifest mismatch: {field}')
    name = f'omcli-{meta["version"]}.tar.gz' if meta['product'] == 'omcli' else f'miniTools-{meta["version"]}.zip'
    require(payload['asset'] == name, 'Unexpected artifact path')
    digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    require(digest == payload['sha256'], 'Artifact SHA mismatch')
    require((directory / (name + '.sha256')).read_text().split() == [digest, name], 'Checksum mismatch')
    if meta['product'] == 'omcli':
        prefix = f'omcli-{meta["version"]}/'
        with tarfile.open(directory / name) as archive:
            members = archive.getmembers()
            require(members, 'Empty archive')
            for member in members:
                require(member.name.startswith(prefix) and '..' not in Path(member.name).parts and not member.issym() and not member.islnk(), 'Unsafe archive')
            require(archive.extractfile(prefix + 'VERSION').read().decode().strip() == meta['version'], 'Embedded version mismatch')
    return payload


def publish_beta(meta, directory):
    current(meta)
    payload = verify_payload(meta, directory)
    existing = api(f'releases/tags/{meta["beta_tag"]}', missing=True)
    if existing:
        require(existing['prerelease'] and not existing['draft'], 'Existing candidate is not a published prerelease')
        assets = {a['name']: a for a in existing['assets']}
        require(assets.get(payload['asset'], {}).get('digest') == 'sha256:' + payload['sha256'], 'Refusing to replace candidate bytes')
    else:
        files = [str(directory / payload['asset']), str(directory / (payload['asset'] + '.sha256')), str(directory / 'release-manifest.json')]
        if meta['product'] == 'miniTools':
            files += [str(directory / 'appcast-beta.xml'), str(directory / 'appcast.xml')]
        current(meta)
        run('gh', 'release', 'create', meta['beta_tag'], *files, '--repo', os.environ['GITHUB_REPOSITORY'], '--target', meta['candidate'], '--prerelease', '--latest=false', '--title', f'{meta["product"]} {meta["version"]} Beta', '--notes', f'Candidate commit: {meta["candidate"]}\nSHA-256: {payload["sha256"]}\nCI runs in parallel; promotion is automatic after checks pass.')
    if meta['product'] == 'miniTools':
        current(meta)
        feed = api('releases/tags/beta', missing=True)
        if feed is None:
            run('gh', 'release', 'create', 'beta', str(directory / 'appcast-beta.xml'), '--repo', os.environ['GITHUB_REPOSITORY'], '--target', meta['candidate'], '--prerelease', '--latest=false', '--title', 'miniTools Beta Update Feed')
        else:
            run('gh', 'release', 'upload', 'beta', str(directory / 'appcast-beta.xml'), '--repo', os.environ['GITHUB_REPOSITORY'], '--clobber')
    print(f'BETA_READY {meta["beta_tag"]} {payload["sha256"]}')


def promote(meta, directory):
    current(meta)
    # Re-read exact candidate bytes from GitHub, never from a rebuild.
    directory.mkdir(parents=True, exist_ok=True)
    run('gh', 'release', 'download', meta['beta_tag'], '--repo', os.environ['GITHUB_REPOSITORY'], '--dir', str(directory))
    payload = verify_payload(meta, directory)
    release = api(f'releases/tags/{meta["beta_tag"]}')
    require(release['prerelease'] and not release['draft'], 'Not a published beta')
    pr = api(f'pulls/{meta["pr"]}')
    require(pr['head']['sha'] == meta['candidate'], 'Candidate PR changed')
    if not pr['merged']:
        require(pr['state'] == 'open', 'Candidate PR closed')
        current(meta)
        merged = api(f'pulls/{meta["pr"]}/merge', 'PUT', {'sha': meta['candidate'], 'merge_method': 'squash', 'commit_title': f'Release {meta["product"]} {meta["version"]}'})
        require(merged['merged'], 'Branch protection rejected merge')
        merged_sha = merged['sha']
    else:
        merged_sha = pr['merge_commit_sha']
    require(api(f'git/commits/{merged_sha}')['tree']['sha'] == meta['tree'], 'Merged tree differs from tested candidate')
    current(meta)
    stable = api(f'releases/tags/{meta["stable_tag"]}', missing=True)
    if stable:
        require(any(a['name'] == payload['asset'] and a.get('digest') == 'sha256:' + payload['sha256'] for a in stable['assets']), 'Stable release has different bytes')
        print('Stable release already published with the same bytes')
        return
    source = Path(os.environ['SOURCE_DIRECTORY'])
    run('git', 'fetch', 'origin', merged_sha, cwd=source)
    tag = meta['stable_tag']
    tag_ref = api(f'git/ref/tags/{tag}', missing=True)
    if not tag_ref:
        run('git', '-c', 'gpg.format=ssh', '-c', f'user.signingkey={os.environ["RELEASE_SIGNING_KEY_FILE"]}', '-c', 'user.name=Release Automation', '-c', 'user.email=7605023+assassinor@users.noreply.github.com', 'tag', '-s', tag, merged_sha, '-m', f'{meta["product"]} {meta["version"]}', cwd=source)
        current(meta)
        run('git', '-c', 'credential.helper=!gh auth git-credential', 'push', 'origin', f'refs/tags/{tag}', cwd=source)
    else:
        run('git', 'fetch', 'origin', f'refs/tags/{tag}:refs/tags/{tag}', cwd=source)
    require(run('git', 'rev-parse', f'{tag}^{{commit}}', cwd=source) == merged_sha, 'Stable tag points to wrong commit')
    run('git', '-c', 'gpg.format=ssh', '-c', 'gpg.ssh.allowedSignersFile=.github/release-signers', 'verify-tag', tag, cwd=source)
    current(meta)
    files = [str(directory / payload['asset']), str(directory / (payload['asset'] + '.sha256')), str(directory / 'release-manifest.json')]
    if meta['product'] == 'miniTools':
        files.append(str(directory / 'appcast.xml'))
    run('gh', 'release', 'create', tag, *files, '--repo', os.environ['GITHUB_REPOSITORY'], '--verify-tag', '--latest', '--title', f'{meta["product"]} {meta["version"]}', '--notes', f'Automatically promoted from {meta["beta_tag"]}.\nCandidate: {meta["candidate"]}\nMerged commit: {merged_sha}\nSHA-256: {payload["sha256"]}\nSame artifact; no rebuild, re-signing or re-notarization.')
    # The source PR is redundant after the exact source was included via the candidate PR.
    if meta.get('source_pr'):
        api(f'pulls/{meta["source_pr"]}', 'PATCH', {'state': 'closed'})
    write_state(dict(meta, phase='released', merged=merged_sha, sha256=payload['sha256']))
    print(f'RELEASED {tag} {payload["sha256"]}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'manifest', 'beta', 'promote', 'check'])
    args = parser.parse_args()
    if args.mode == 'prepare':
        meta = prepare()
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                for key in ('candidate', 'version', 'pr'):
                    output.write(f'{key}={meta[key]}\n')
                output.write('metadata=' + json.dumps(meta, separators=(',', ':')) + '\n')
    else:
        meta = json.loads(os.environ['RELEASE_JSON'])
        directory = Path(os.environ.get('RELEASE_DIRECTORY', 'dist')).resolve()
        if args.mode == 'manifest':
            manifest(meta, directory)
        elif args.mode == 'beta':
            publish_beta(meta, directory)
        elif args.mode == 'promote':
            promote(meta, directory)
        else:
            current(meta)


if __name__ == '__main__':
    main()
