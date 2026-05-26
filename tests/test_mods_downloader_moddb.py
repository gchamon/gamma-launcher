from pathlib import Path
from io import StringIO
import json
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

from launcher.mods.downloader.moddb import ModDBDownloader

from common import basic_url2, mocked_get, moddb_start_url, moddb_page_info, moddb_mirror_url


class ModDBDownloaderTestCase(TestCase):

    @staticmethod
    def _write_zip(path: Path, content: str = 'TEST') -> None:
        with ZipFile(path, 'w') as archive:
            archive.writestr('test.txt', content)

    @patch('launcher.mods.downloader.moddb.g_session.get', side_effect=mocked_get)
    def test_get_download_url(self, mock_request) -> None:
        self.assertEqual(ModDBDownloader._get_download_url(moddb_start_url,), basic_url2)

        self.assertEqual(len(mock_request.call_args_list), 2)
        self.assertTrue(mock_request.call_args_list[0].called_with(moddb_start_url))
        self.assertTrue(mock_request.call_args_list[1].called_with(moddb_mirror_url))

    def test_is_challenge_response(self) -> None:
        self.assertTrue(ModDBDownloader._is_challenge_response(
            '<title>Just a moment...</title><script src="https://challenges.cloudflare.com/test.js"></script>',
            403
        ))
        self.assertFalse(ModDBDownloader._is_challenge_response('<html>download page</html>', 200))

    @patch('launcher.mods.downloader.moddb.g_session.get', side_effect=mocked_get)
    def test_parse_moddb_metadata(self, mock_request) -> None:
        o = ModDBDownloader._parse_moddb_metadata(moddb_page_info)

        self.assertEqual(o['Filename'], 'Anomaly-1.5.3-Full.2.7z')
        self.assertEqual(o['MD5 Hash'], 'd6bce51a4e6d98f9610ef0aa967ba964')
        self.assertEqual(o['Download'], 'https://www.moddb.com/downloads/start/277404')

        mock_request.assert_called_once_with(moddb_page_info)

    @patch('launcher.mods.downloader.moddb.g_session.get', side_effect=mocked_get)
    def test_download(self, mock_request) -> None:
        o = ModDBDownloader(moddb_start_url, moddb_page_info)

        # TODO: Better test cases (check cache, requests call, ...)
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)

            o.download(pdir)
            self.assertTrue((pdir / 'Anomaly-1.5.3-Full.2.7z').exists())

    def test_cached_browser_archive_is_accepted(self) -> None:
        o = ModDBDownloader(moddb_start_url, '')

        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            archive = pdir / 'moddb' / '277404' / 'manual.zip'
            archive.parent.mkdir(parents=True)
            self._write_zip(archive)

            self.assertEqual(o._get_cached_browser_archive(pdir), archive)

    def test_cached_browser_archive_ignores_unexpected_filename(self) -> None:
        o = ModDBDownloader(moddb_start_url, '')
        o._user_wanted_name = 'expected.zip'

        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            wrong = pdir / 'moddb' / '277404' / 'wrong.zip'
            wrong.parent.mkdir(parents=True)
            self._write_zip(wrong)

            self.assertIsNone(o._get_cached_browser_archive(pdir))

    def test_cached_browser_archive_removes_html_saved_as_zip(self) -> None:
        o = ModDBDownloader(moddb_start_url, '')
        o._user_wanted_name = 'expected.zip'

        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            archive = pdir / 'moddb' / '277404' / 'expected.zip'
            archive.parent.mkdir(parents=True)
            archive.write_text('<!DOCTYPE html><title>Opps - ModDB</title>')

            self.assertIsNone(o._get_cached_browser_archive(pdir))
            self.assertFalse(archive.exists())
            self.assertEqual(len(list(archive.parent.glob('expected.zip.invalid-*'))), 0)

    def test_cached_browser_archive_removes_old_invalid_file(self) -> None:
        o = ModDBDownloader(moddb_start_url, '')

        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            archive = pdir / 'moddb' / '277404' / 'expected.zip.invalid-123'
            archive.parent.mkdir(parents=True)
            self._write_zip(archive)

            self.assertIsNone(o._get_cached_browser_archive(pdir))
            self.assertFalse(archive.exists())

    def test_browser_candidate_waits_for_stable_size(self) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            archive = pdir / 'expected.zip'
            self._write_zip(archive)
            sizes = {}

            self.assertIsNone(ModDBDownloader._accept_browser_candidate(
                archive, pdir, expected_name='expected.zip', stable_sizes=sizes
            ))
            self.assertEqual(ModDBDownloader._accept_browser_candidate(
                archive, pdir, expected_name='expected.zip', stable_sizes=sizes
            ), archive)

    def test_browser_candidate_waits_while_part_exists(self) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            archive = pdir / 'expected.zip'
            part = pdir / 'expected.zip.part'
            self._write_zip(archive)
            part.write_text('partial')
            sizes = {str(archive): archive.stat().st_size}

            self.assertIsNone(ModDBDownloader._accept_browser_candidate(
                archive, pdir, expected_name='expected.zip', stable_sizes=sizes
            ))

            part.unlink()
            self.assertEqual(ModDBDownloader._accept_browser_candidate(
                archive, pdir, expected_name='expected.zip', stable_sizes=sizes
            ), archive)

    def test_browser_candidate_rejects_wrong_filename(self) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            archive = pdir / 'wrong.zip'
            self._write_zip(archive)
            sizes = {str(archive): archive.stat().st_size}

            self.assertIsNone(ModDBDownloader._accept_browser_candidate(
                archive, pdir, expected_name='expected.zip', stable_sizes=sizes
            ))

    def test_places_download_info_filters_expected_filename(self) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            profile = Path(dir)
            db = profile / 'places.sqlite'
            conn = sqlite3.connect(db)
            try:
                conn.execute('CREATE TABLE moz_anno_attributes (id INTEGER, name TEXT)')
                conn.execute(
                    'CREATE TABLE moz_annos '
                    '(place_id INTEGER, anno_attribute_id INTEGER, content TEXT, lastModified INTEGER)'
                )
                conn.execute(
                    'INSERT INTO moz_anno_attributes VALUES (1, "downloads/destinationFileURI")'
                )
                conn.execute(
                    'INSERT INTO moz_anno_attributes VALUES (2, "downloads/metaData")'
                )
                conn.execute(
                    'INSERT INTO moz_annos VALUES (1, 1, ?, 2000)',
                    ('file:///tmp/wrong.zip',)
                )
                conn.execute(
                    'INSERT INTO moz_annos VALUES (1, 2, ?, 2000)',
                    (json.dumps({'state': 1}),)
                )
                conn.execute(
                    'INSERT INTO moz_annos VALUES (2, 1, ?, 3000)',
                    ('file:///tmp/expected.zip',)
                )
                conn.execute(
                    'INSERT INTO moz_annos VALUES (2, 2, ?, 3000)',
                    (json.dumps({'state': 1}),)
                )
                conn.commit()
            finally:
                conn.close()

            self.assertEqual(
                ModDBDownloader._get_download_info_from_places(
                    profile, since_us=1000, expected_name='expected.zip'
                ),
                (Path('/tmp/expected.zip'), True)
            )

    @patch('launcher.mods.downloader.moddb.sleep')
    def test_wait_for_download_ignores_live_invalid_then_accepts_valid_file(self, mock_sleep) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()
            html = dl_dir / 'expected.zip'
            html.write_text('<html><title>Opps - ModDB</title>')

            def after_first_sleep(_seconds):
                if not html.exists():
                    return
                if html.read_text(errors='ignore').startswith('<html>'):
                    self._write_zip(html)

            mock_sleep.side_effect = after_first_sleep

            self.assertEqual(
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=4,
                    expected_name='expected.zip',
                ),
                dl_dir / 'expected.zip'
            )
            self.assertTrue(html.exists())
            self.assertEqual(len(list(dl_dir.glob('expected.zip.invalid-*'))), 0)

    @patch('sys.stdout', new_callable=StringIO)
    def test_live_invalid_candidate_is_not_removed(self, stdout) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            archive = pdir / 'expected.zip'
            archive.write_text('<html><title>Opps - ModDB</title>')
            sizes = {str(archive): archive.stat().st_size}
            rejected = {}

            self.assertIsNone(ModDBDownloader._accept_browser_candidate(
                archive, pdir, expected_name='expected.zip',
                stable_sizes=sizes, rejected=rejected,
                remove_invalid=False,
            ))
            self.assertTrue(archive.exists())
            self.assertEqual(len(list(pdir.glob('expected.zip.invalid-*'))), 0)
            self.assertNotIn('Ignoring browser download', stdout.getvalue())

    @patch('launcher.mods.downloader.moddb.sleep')
    def test_wait_for_download_reports_rejected_download_on_timeout(self, mock_sleep) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()
            archive = dl_dir / 'expected.zip'
            archive.write_text('<html><title>Opps - ModDB</title>')

            with self.assertRaises(Exception) as cm:
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=2,
                    expected_name='expected.zip',
                )

            self.assertIn('Timed out waiting for download', str(cm.exception))
            self.assertIn('expected.zip: download is an HTML page, not an archive', str(cm.exception))
            self.assertEqual(str(cm.exception).count('expected.zip:'), 1)

    @patch('launcher.mods.downloader.moddb.sleep')
    @patch('sys.stdout', new_callable=StringIO)
    def test_wait_for_download_prints_simple_wait_message(self, stdout, mock_sleep) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()

            with self.assertRaises(Exception):
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=1,
                    expected_name='expected.zip',
                )

            self.assertIn('Waiting for download to start...', stdout.getvalue())
            self.assertNotIn('places.sqlite:', stdout.getvalue())

    @patch('sys.stdout', new_callable=StringIO)
    def test_wait_for_download_prints_captcha_prompt_immediately(self, stdout) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()

            with self.assertRaises(Exception):
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=1,
                    expected_name='expected.zip',
                )

            self.assertIn('click to solve captcha:', stdout.getvalue())

    @patch('sys.stdout', new_callable=StringIO)
    def test_wait_for_download_does_not_prompt_when_archive_exists(self, stdout) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()
            archive = dl_dir / 'expected.zip'
            self._write_zip(archive)

            self.assertEqual(
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=2,
                    expected_name='expected.zip',
                ),
                archive
            )
            self.assertNotIn('click to solve captcha:', stdout.getvalue())

    @patch('launcher.mods.downloader.moddb.sleep')
    @patch('sys.stdout', new_callable=StringIO)
    def test_wait_for_download_delays_captcha_prompt_after_prior_success(self, stdout, mock_sleep) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()

            def create_archive(_seconds):
                archive = dl_dir / 'expected.zip'
                if not archive.exists():
                    self._write_zip(archive)

            mock_sleep.side_effect = create_archive

            self.assertEqual(
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=4,
                    expected_name='expected.zip', prompt_after=20,
                ),
                dl_dir / 'expected.zip'
            )
            self.assertNotIn('click to solve captcha:', stdout.getvalue())

    @patch('launcher.mods.downloader.moddb.sleep')
    @patch('sys.stdout', new_callable=StringIO)
    def test_wait_for_download_prints_delayed_captcha_prompt_once(self, stdout, mock_sleep) -> None:
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()

            with self.assertRaises(Exception):
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=22,
                    expected_name='expected.zip', prompt_after=20,
                )

            self.assertEqual(stdout.getvalue().count('click to solve captcha:'), 1)

    @patch('launcher.mods.downloader.moddb.ModDBDownloader._accept_places_download')
    @patch('launcher.mods.downloader.moddb.sleep')
    @patch('sys.stdout', new_callable=StringIO)
    def test_wait_for_download_suppresses_prompt_after_history_detection(
        self, stdout, mock_sleep, mock_accept_places
    ) -> None:
        mock_accept_places.return_value = (None, True)
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            pdir = Path(dir)
            profile = pdir / 'profile'
            dl_dir = pdir / 'downloads'
            profile.mkdir()
            dl_dir.mkdir()

            with self.assertRaises(Exception):
                ModDBDownloader._wait_for_download(
                    profile, dl_dir, since_us=0, timeout=22,
                    expected_name='expected.zip', prompt_after=20,
                )

            self.assertIn('Download detected in Firefox history', stdout.getvalue())
            self.assertNotIn('click to solve captcha:', stdout.getvalue())

    @patch('launcher.mods.downloader.moddb.ModDBDownloader._download_with_browser')
    @patch('launcher.mods.downloader.moddb.g_session.get')
    def test_challenge_falls_back_to_browser(self, mock_request, mock_browser) -> None:
        class ChallengeResponse:
            status_code = 403
            text = '<title>Just a moment...</title>'

        mock_request.return_value = ChallengeResponse()
        mock_browser.return_value = Path('/tmp/manual.7z')

        o = ModDBDownloader(moddb_start_url, '')
        with TemporaryDirectory(prefix='gamma-launcher-moddb-downloader-test-') as dir:
            self.assertEqual(
                o.download(Path(dir), browser_download_timeout=123),
                Path('/tmp/manual.7z')
            )

        mock_browser.assert_called_once_with(Path(dir), 123)
