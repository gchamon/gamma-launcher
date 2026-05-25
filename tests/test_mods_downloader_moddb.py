from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from launcher.mods.downloader.moddb import ModDBDownloader

from common import basic_url2, mocked_get, moddb_start_url, moddb_page_info, moddb_mirror_url


class ModDBDownloaderTestCase(TestCase):

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
            archive = pdir / 'moddb' / '277404' / 'manual.7z'
            archive.parent.mkdir(parents=True)
            archive.write_text('TEST')

            self.assertEqual(o._get_cached_browser_archive(pdir), archive)

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
            self.assertEqual(o.download(Path(dir)), Path('/tmp/manual.7z'))

        mock_browser.assert_called_once()
