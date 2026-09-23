"""Offline tests: all platform calls are mocked; no credits consumed."""
from concurrent.futures import ThreadPoolExecutor
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import image_server as service


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = patch.object(service, 'STORE', Path(self.temp.name))
        self.storage.start()
        self.source = {'id': 'a' * 32, 'kind': 'image', 'created': 0, 'prompt': 'test image',
                       'ratio': '9:16', 'status': 'done', 'images': ['source.png'], 'videos': []}
        service.folder(self.source['id']).mkdir()
        service.save(self.source)
        (service.folder(self.source['id']) / 'source.png').write_bytes(b'png-test')
        self.payload = {'request_id': 'b' * 32, 'source_job': self.source['id'], 'source_image': 'source.png',
                        'prompt': 'Camera slowly moves forward', 'model': 'seedance2.0fast_vip', 'duration': 5}

    def tearDown(self):
        self.storage.stop()
        self.temp.cleanup()

    def create_video(self):
        return service.create_job(self.payload, 'video')[0]

    def waiting_video(self):
        job = self.create_video()
        job.update(status='waiting', submit_id='remote-video')
        service.save(job)
        return job

    def test_video_command_uses_owned_reference_and_poll_zero(self):
        job = self.create_video()
        with patch.object(service, 'cli', return_value={'submit_id': 'remote-id', 'credit_count': 5}) as mock:
            service.submit(job)
        args = mock.call_args.args
        self.assertEqual(args[0], 'image2video')
        self.assertIn('--image=' + str(service.media_file(self.source, 'source.png')), args)
        self.assertIn('--duration=5', args)
        self.assertIn('--ratio=9:16', args)
        self.assertIn('--video_resolution=720p', args)
        self.assertIn('--poll=0', args)
        self.assertEqual(service.read_job(job['id'])['submit_id'], 'remote-id')

    def test_image_command_still_generates_one_image(self):
        job, _ = service.create_job({'request_id': 'c' * 32, 'prompt': 'test image', 'ratio': '16:9'}, 'image')
        self.assertIn('--generate_num=1', service.submission_args(job))
        self.assertEqual(service.submission_args(job)[0], 'text2image')

    def test_concurrent_duplicate_requests_submit_only_once(self):
        def dispatch(_):
            job, created = service.create_job(dict(self.payload), 'video')
            if created:
                service.submit(job)
            return job['id']
        with patch.object(service, 'cli', return_value={'submit_id': 'remote'}) as mock:
            with ThreadPoolExecutor(max_workers=8) as pool:
                ids = list(pool.map(dispatch, range(12)))
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(len(set(ids)), 1)
        service.recover()
        self.assertFalse(service.create_job(self.payload, 'video')[1])

    def test_changed_payload_with_same_id_rejected(self):
        self.create_video()
        for field, value in [('duration', 10), ('prompt', 'different prompt')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                service.create_job(dict(self.payload, **{field: value}), 'video')

    def test_same_content_new_id_reuses_pending_task(self):
        job = self.create_video()
        replay, created = service.create_job(dict(self.payload, request_id='c' * 32), 'video')
        self.assertFalse(created)
        self.assertEqual(replay['id'], job['id'])

    def test_invalid_references_and_options_rejected(self):
        changes = [{'source_job': '../outside'}, {'source_image': '../source.png'},
                   {'source_image': 'C:\\outside.png'}, {'source_image': 'other.png'},
                   {'model': 'unknown'}, {'model': 'seedance1.5pro'}, {'duration': True}, {'duration': 30}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises((ValueError, FileNotFoundError)):
                service.create_job(dict(self.payload, **change), 'video')
        self.source['status'] = 'waiting'
        service.save(self.source)
        with self.assertRaises(ValueError):
            self.create_video()

    def test_missing_reference_fails_before_generation(self):
        job = self.create_video()
        (service.folder(self.source['id']) / 'source.png').unlink()
        with patch.object(service, 'cli') as mock:
            service.submit(job)
        mock.assert_not_called()
        self.assertEqual(job['status'], 'failed')

    def test_timeout_and_invalid_response_never_retry_submission(self):
        job = self.create_video()
        with patch.object(service, 'cli', side_effect=TimeoutError('timeout')) as mock:
            service.submit(job)
            service.recover()
            service.poll_once()
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(service.read_job(job['id'])['status'], 'uncertain')
        replay, created = service.create_job(dict(self.payload, request_id='c' * 32), 'video')
        self.assertFalse(created)
        self.assertEqual(replay['id'], job['id'])

    def test_malformed_submission_response_never_retries(self):
        job = self.create_video()
        with patch.object(service, 'cli', return_value={}) as mock:
            service.submit(job)
            service.recover()
            service.poll_once()
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(service.read_job(job['id'])['status'], 'uncertain')

    def test_restart_keeps_remote_ids_and_isolates_corrupt_files(self):
        job = self.create_video()
        for status, submit_id, expected in [('submitting', None, 'uncertain'),
                                             ('submitting', 'remote', 'waiting'),
                                             ('uncertain', 'remote', 'waiting')]:
            job.update(status=status)
            job.pop('submit_id', None)
            if submit_id:
                job['submit_id'] = submit_id
            service.save(job)
            service.recover()
            self.assertEqual(service.read_job(job['id'])['status'], expected)
        for number, data in [(1, 'invalid json'), (2, '[]'), (3, '{"id": "wrong"}'),
                             (4, json.dumps({'id': '4' * 32, 'created': 1, 'status': []}))]:
            path = service.folder(str(number) * 32)
            path.mkdir()
            (path / 'job.json').write_text(data, encoding='utf-8')
        self.assertEqual(len(service.listing()), 6)
        with patch.object(service, 'cli', return_value={'gen_status': 'querying'}) as mock:
            service.poll_once()
        self.assertEqual(mock.call_count, 1)

    def test_known_remote_id_remains_queryable_after_save_error(self):
        job = self.create_video()
        real_save = service.save
        seen = 0
        def intermittent_save(record):
            nonlocal seen
            seen += 1
            if seen == 2:
                raise PermissionError('brief file sharing violation')
            real_save(record)
        with patch.object(service, 'save', side_effect=intermittent_save), patch.object(service, 'cli', return_value={'submit_id': 'remote'}):
            service.submit(job)
        persisted = service.read_job(job['id'])
        self.assertEqual(persisted['status'], 'waiting')
        self.assertEqual(persisted['submit_id'], 'remote')

    def test_success_downloads_video_and_terminal_job_is_not_queried(self):
        job = self.waiting_video()
        stale = copy.deepcopy(job)
        def result(*args):
            self.assertEqual(args[0], 'query_result')
            if any(arg.startswith('--download_dir=') for arg in args):
                (service.folder(job['id']) / 'result.mp4').write_bytes(b'test-video')
            return {'gen_status': 'success', 'credit_count': 5}
        with patch.object(service, 'cli', side_effect=result) as mock:
            service.query(job)
            service.query(stale)
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(service.read_job(job['id'])['videos'], ['result.mp4'])
        self.assertEqual(job['status'], 'done')

    def test_download_error_retries_only_queries(self):
        job = self.waiting_video()
        with patch.object(service, 'cli', side_effect=[{'gen_status': 'success'}, TimeoutError('download failed')]):
            service.query(job)
        record = service.read_job(job['id'])
        self.assertEqual(record['status'], 'downloading')
        self.assertIn('download failed', record['query_error'])
        def result(*args):
            self.assertEqual(args[0], 'query_result')
            if any(arg.startswith('--download_dir=') for arg in args):
                (service.folder(job['id']) / 'result.mp4').write_bytes(b'test-video')
            return {'gen_status': 'success'}
        with patch.object(service, 'cli', side_effect=result):
            service.poll_once()
        self.assertEqual(service.read_job(job['id'])['status'], 'done')

    def test_concurrent_queries_are_serialized(self):
        job = self.waiting_video()
        entered, release = threading.Event(), threading.Event()
        def result(*args):
            entered.set()
            release.wait(3)
            return {'gen_status': 'querying'}
        with patch.object(service, 'cli', side_effect=result) as mock:
            thread = threading.Thread(target=service.query, args=(copy.deepcopy(job),))
            thread.start()
            self.assertTrue(entered.wait(3))
            service.query(copy.deepcopy(job))
            release.set()
            thread.join(3)
        self.assertEqual(mock.call_count, 1)

    def test_failure_is_not_resubmitted(self):
        job = self.waiting_video()
        with patch.object(service, 'cli', return_value={'gen_status': 'fail', 'fail_reason': 'denied'}) as mock:
            service.query(job)
            service.poll_once()
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(job['message'], 'denied')

    def test_local_preview_keeps_original_and_never_calls_platform(self):
        job = self.waiting_video()
        job.update(status='done', videos=['result.mp4'])
        service.save(job)
        original = service.folder(job['id']) / 'result.mp4'
        original.write_bytes(b'original-mp4')
        def convert(args, **kwargs):
            Path(args[-1]).write_bytes(b'webm-preview')
            return SimpleNamespace(returncode=0, stderr='')
        with patch.object(service, 'find_ffmpeg', return_value=Path('ffmpeg.exe')), patch.object(service.subprocess, 'run', side_effect=convert) as convert_mock, patch.object(service, 'cli') as platform:
            service.make_preview(job)
            service.make_preview(job)
        platform.assert_not_called()
        self.assertEqual(convert_mock.call_count, 1)
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['videos'], ['result.mp4'])
        self.assertEqual(original.read_bytes(), b'original-mp4')
        self.assertEqual(service.media_file(job, job['preview_video']).read_bytes(), b'webm-preview')

    def test_preview_failure_does_not_lose_finished_video(self):
        job = self.waiting_video()
        job.update(status='done', videos=['result.mp4'])
        service.save(job)
        (service.folder(job['id']) / 'result.mp4').write_bytes(b'original-mp4')
        with patch.object(service, 'find_ffmpeg', return_value=None), patch.object(service, 'cli') as platform:
            service.make_preview(job)
        platform.assert_not_called()
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['preview_status'], 'failed')
        self.assertEqual(job['videos'], ['result.mp4'])

    def test_restart_retries_interrupted_local_preview_only(self):
        job = self.waiting_video()
        job.update(status='done', videos=['result.mp4'], preview_status='converting')
        service.save(job)
        with patch.object(service, 'cli') as platform:
            service.recover()
        platform.assert_not_called()
        self.assertEqual(service.read_job(job['id'])['status'], 'done')
        self.assertNotIn('preview_status', service.read_job(job['id']))

    def test_http_video_ranges_head_token_and_host(self):
        job = self.waiting_video()
        job.update(status='done', videos=['result.mp4'])
        service.save(job)
        (service.folder(job['id']) / 'result.mp4').write_bytes(b'0123456789')
        server = service.ThreadingHTTPServer(('127.0.0.1', 0), service.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(method, path, headers=None, body=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=3)
            connection.request(method, path, body, headers={'Host': '127.0.0.1:7861', **(headers or {})})
            response = connection.getresponse()
            result = response.status, dict(response.getheaders()), response.read()
            connection.close()
            return result
        try:
            path = f"/media/{job['id']}/result.mp4"
            status, headers, body = request('GET', path, {'Range': 'bytes=2-5'})
            self.assertEqual((status, body), (206, b'2345'))
            self.assertEqual(headers['Content-Range'], 'bytes 2-5/10')
            self.assertEqual(headers['Content-Type'], 'video/mp4')
            self.assertEqual(request('GET', path, {'Range': 'bytes=-3'})[2], b'789')
            self.assertEqual(request('GET', path, {'Range': 'bytes=99-'})[0], 416)
            status, headers, body = request('HEAD', path)
            self.assertEqual((status, body, headers['Content-Length']), (200, b'', '10'))
            self.assertEqual(request('GET', path, {'Host': 'evil.example'})[0], 403)
            self.assertEqual(request('POST', '/api/video', body=json.dumps(self.payload))[0], 403)
            self.assertEqual(request('GET', f"/media/{job['id']}/..%5Cjob.json")[0], 400)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
