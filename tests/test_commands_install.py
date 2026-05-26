from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from launcher.commands.install import FullInstall
from launcher.commands.install import AnomalyInstall
from launcher.mods.info import ModInfo


class MockedMod:

    def __init__(self, name: str, error: Exception = None) -> None:
        self.info = ModInfo({'name': name})
        self.error = error
        self.downloaded = False
        self.download_kwargs = None
        self.installed = False

    def download(self, *args, **kwargs) -> None:
        self.downloaded = True
        self.download_kwargs = kwargs
        if self.error:
            raise self.error

    def install(self, *args, **kwargs) -> None:
        self.installed = True


class FullInstallTestCase(TestCase):

    def test_browser_download_timeout_argument_defaults_to_ten_minutes(self) -> None:
        arg = AnomalyInstall.arguments["--browser-download-timeout"]

        self.assertEqual(arg["default"], 600)
        self.assertEqual(FullInstall.arguments["--browser-download-timeout"]["default"], 600)

    @patch('launcher.commands.install.read_mod_maker')
    def test_install_mods_collects_failures_and_continues(self, read_mod_maker) -> None:
        first = MockedMod('001 - first')
        second = MockedMod('002 - second', RuntimeError('download failed'))
        third = MockedMod('003 - third', RuntimeError('hash mismatch'))
        fourth = MockedMod('004 - fourth')
        read_mod_maker.return_value = [first, second, third, fourth]

        with TemporaryDirectory(prefix='gamma-launcher-install-tests-') as dir:
            pdir = Path(dir)
            installer = FullInstall()
            installer._grok_mod_dir = pdir
            installer._dl_dir = pdir / 'downloads'
            installer._mod_dir = pdir / 'mods'
            installer._browser_download_timeout = 123

            with self.assertRaises(RuntimeError) as cm:
                installer._install_mods()

        self.assertTrue(first.downloaded)
        self.assertTrue(first.installed)
        self.assertTrue(second.downloaded)
        self.assertFalse(second.installed)
        self.assertTrue(third.downloaded)
        self.assertFalse(third.installed)
        self.assertTrue(fourth.downloaded)
        self.assertTrue(fourth.installed)
        self.assertEqual(first.download_kwargs['browser_download_timeout'], 123)
        self.assertEqual(fourth.download_kwargs['browser_download_timeout'], 123)
        self.assertIn('Failed to install 2 mod(s)', str(cm.exception))
        self.assertIn('002 - second: download failed', str(cm.exception))
        self.assertIn('003 - third: hash mismatch', str(cm.exception))
