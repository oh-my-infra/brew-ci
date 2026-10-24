import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('fast_release', Path(__file__).parents[1] / 'scripts/fast_release.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FastReleaseTests(unittest.TestCase):
    def meta(self):
        return {'product': 'omcli', 'version': '2026.10.25.1', 'candidate': 'a'*40, 'tree': 'b'*40,
                'run_id': 10, 'source': 'c'*40, 'source_pr': None, 'beta_tag': 'v2026.10.25.1-beta.10', 'pr': 2}

    def payload(self, directory):
        meta = self.meta()
        path = directory / 'omcli-2026.10.25.1.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            data = b'2026.10.25.1\n'
            info = tarfile.TarInfo('omcli-2026.10.25.1/VERSION')
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        m.manifest(meta, directory)
        return meta, path

    def test_calendar_allocation_reserves_unpublished_candidates(self):
        self.assertEqual(m.allocate_version('2026.10.25', ['2026.10.24.9', '2026.10.25.2']), '2026.10.25.3')
        self.assertEqual(m.allocate_version('2026.10.25', []), '2026.10.25.1')

    def test_latest_candidate_guard(self):
        meta = self.meta()
        m.current(meta, meta)
        for active in [dict(meta, run_id=11), dict(meta, candidate='d'*40)]:
            with self.assertRaisesRegex(ValueError, 'Superseded'):
                m.current(meta, active)

    @patch.object(m, 'api')
    def test_source_pr_update_or_closure_invalidates(self, api):
        meta = dict(self.meta(), source_pr=1)
        for pr in [{'state':'open','head':{'sha':'new'}}, {'state':'closed','head':{'sha':meta['source']},'merged':False}]:
            api.return_value = pr
            with self.assertRaisesRegex(ValueError, 'Source PR changed'):
                m.current(meta, meta)

    def test_manifest_and_exact_archive_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            meta, _=self.payload(directory)
            self.assertEqual(m.verify_payload(meta,directory)['candidate'],meta['candidate'])

    def test_changed_bytes_cannot_promote(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            meta,path=self.payload(directory)
            path.write_bytes(path.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                m.verify_payload(meta,directory)

    def test_substituted_candidate_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            meta,_=self.payload(directory)
            with self.assertRaisesRegex(ValueError,'Manifest mismatch'):
                m.verify_payload(dict(meta,candidate='other'),directory)

    def test_checksum_filename_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            meta,_=self.payload(directory)
            p=directory/'release-manifest.json';data=json.loads(p.read_text());data['asset']='../other';p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Unexpected artifact path'):
                m.verify_payload(meta,directory)

    @patch.object(m,'current',side_effect=ValueError('Superseded'))
    @patch.object(m,'run')
    def test_superseded_beta_has_no_write(self,run,current):
        with self.assertRaises(ValueError):m.publish_beta(self.meta(),Path('/unused'))
        run.assert_not_called()

    @patch.object(m,'current',side_effect=ValueError('Superseded'))
    @patch.object(m,'run')
    def test_superseded_promotion_has_no_write(self,run,current):
        with self.assertRaises(ValueError):m.promote(self.meta(),Path('/unused'))
        run.assert_not_called()

    @patch.object(m,'api')
    @patch.dict(os.environ,{'GITHUB_REPOSITORY':'oh-my-brew/omcli','GITHUB_ACTOR':'untrusted'})
    def test_nonwriter_cannot_prepare(self,api):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'event.json';p.write_text('{}')
            api.side_effect=[{'default_branch':'main'},{'permission':'read'}]
            with patch.dict(os.environ,{'GITHUB_EVENT_PATH':str(p)}):
                with self.assertRaisesRegex(ValueError,'repository writers'):m.prepare()
        self.assertEqual(api.call_count,2)

    @patch.object(m,'api')
    @patch.dict(os.environ,{'GITHUB_REPOSITORY':'oh-my-brew/omcli','GITHUB_ACTOR':'writer'})
    def test_fork_cannot_access_signing_pipeline(self,api):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'event.json';p.write_text(json.dumps({'pull_request':{'head':{'repo':{'full_name':'other/fork'}}}}))
            api.side_effect=[{'default_branch':'main'},{'permission':'write'}]
            with patch.dict(os.environ,{'GITHUB_EVENT_PATH':str(p)}):
                with self.assertRaisesRegex(ValueError,'same-repository'):m.prepare()
        self.assertEqual(api.call_count,2)


if __name__ == '__main__':unittest.main()
