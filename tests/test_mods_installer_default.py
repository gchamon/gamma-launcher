from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from launcher.mods.info import ModInfo
from launcher.mods.installer.default import DefaultInstaller


class MockedDownloader:

    @property
    def archive(self, *args, **kwargs):
        return Path('/downloads/example-mod.7z')

    def extract(self, to: Path):
        gamedata = to / 'testsubdir' / 'gamedata'
        gamedata.mkdir(parents=True)
        (gamedata / 'flag').write_text('YES')


def mocked_downloader_factory(info: ModInfo, *args, **kwargs):
    return MockedDownloader() if info.url else None


class DefaultInstallerTestCase(TestCase):

    def _installer(self) -> DefaultInstaller:
        return DefaultInstaller(ModInfo({
            'name': '005 - bar',
            'url': 'something',
            'subdirs': ['testsubdir'],
        }))

    def _write_meta_ini(self, install_dir: Path, archive_name: str) -> None:
        install_dir.mkdir()
        (install_dir / 'meta.ini').write_text(
            '[General]\n'
            f'version={archive_name}\n'
            f'newestversion={archive_name}\n'
            f'installationFile={archive_name}\n'
        )

    @patch('launcher.mods.installer.base.DownloaderFactory', side_effect=mocked_downloader_factory)
    def test_logs_extracting_archive_before_installing_subdir(self, _) -> None:
        installer = self._installer()

        with TemporaryDirectory(prefix='gamma-launcher-default-installer-tests-') as dir:
            stdout = StringIO()
            with redirect_stdout(stdout):
                installer.install(Path(dir))

        output = stdout.getvalue()
        extracting = '    Extracting example-mod.7z...'
        installing = f'    Installing testsubdir -> {Path(dir) / installer.info.name}'

        self.assertIn(extracting, output)
        self.assertIn(installing, output)
        self.assertLess(output.index(extracting), output.index(installing))

    @patch('launcher.mods.installer.base.DownloaderFactory', side_effect=mocked_downloader_factory)
    def test_skips_install_when_meta_ini_matches_archive(self, _) -> None:
        installer = self._installer()

        with TemporaryDirectory(prefix='gamma-launcher-default-installer-tests-') as dir:
            root = Path(dir)
            self._write_meta_ini(root / installer.info.name, 'example-mod.7z')

            stdout = StringIO()
            with redirect_stdout(stdout):
                installer.install(root)

        output = stdout.getvalue()
        self.assertIn('    Skipping 005 - bar; example-mod.7z is already installed', output)
        self.assertNotIn('    Extracting example-mod.7z...', output)
        self.assertNotIn('    Installing testsubdir ->', output)

    @patch('launcher.mods.installer.base.DownloaderFactory', side_effect=mocked_downloader_factory)
    def test_installs_when_meta_ini_is_missing(self, _) -> None:
        installer = self._installer()

        with TemporaryDirectory(prefix='gamma-launcher-default-installer-tests-') as dir:
            root = Path(dir)
            (root / installer.info.name).mkdir()

            stdout = StringIO()
            with redirect_stdout(stdout):
                installer.install(root)

        output = stdout.getvalue()
        self.assertIn('    Extracting example-mod.7z...', output)
        self.assertIn('    Installing testsubdir ->', output)

    @patch('launcher.mods.installer.base.DownloaderFactory', side_effect=mocked_downloader_factory)
    def test_installs_when_meta_ini_archive_differs(self, _) -> None:
        installer = self._installer()

        with TemporaryDirectory(prefix='gamma-launcher-default-installer-tests-') as dir:
            root = Path(dir)
            self._write_meta_ini(root / installer.info.name, 'older-example-mod.7z')

            stdout = StringIO()
            with redirect_stdout(stdout):
                installer.install(root)

        output = stdout.getvalue()
        self.assertIn('    Extracting example-mod.7z...', output)
        self.assertIn('    Installing testsubdir ->', output)

    @patch('launcher.mods.installer.base.DownloaderFactory', side_effect=mocked_downloader_factory)
    def test_force_reinstall_ignores_matching_meta_ini(self, _) -> None:
        installer = self._installer()

        with TemporaryDirectory(prefix='gamma-launcher-default-installer-tests-') as dir:
            root = Path(dir)
            self._write_meta_ini(root / installer.info.name, 'example-mod.7z')

            stdout = StringIO()
            with redirect_stdout(stdout):
                installer.install(root, force=True)

        output = stdout.getvalue()
        self.assertIn('    Extracting example-mod.7z...', output)
        self.assertIn('    Installing testsubdir ->', output)
