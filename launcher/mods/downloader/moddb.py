import json
import re
import shutil
import sqlite3
import time
import zipfile

from bs4 import BeautifulSoup
from os import environ
from pathlib import Path
from requests.exceptions import HTTPError
from subprocess import DEVNULL, Popen
from time import sleep
from typing import Dict
from urllib.parse import urlparse, unquote

from launcher.exceptions import HashError, ModDBDownloadError
from launcher.hash import check_hash
from launcher.mods.downloader.base import DefaultDownloader, g_session


_browser_processes = []
_browser_services_started = False
_browser_download_succeeded = False
_browser_prompt_url = 'http://localhost:6080/vnc.html?autoconnect=1'


class ModDBDownloader(DefaultDownloader):
    "Specialization of `launcher.mods.downloader.base.DefaultDownloader` to manage ModDB URLs"

    def __init__(self, url: str, iurl: str) -> None:
        super().__init__(url)
        self._iurl = iurl

    @property
    def moddb_id(self) -> str:
        return urlparse(self._url).path.rstrip('/').split('/')[-1]

    @staticmethod
    def _is_challenge_response(text: str, status_code: int = 200) -> bool:
        page = text.lower()
        return (
            status_code == 403
            or 'just a moment' in page
            or 'challenges.cloudflare.com' in page
            or 'cf-turnstile' in page
        )

    @staticmethod
    def _parse_moddb_metadata(url: str) -> Dict[str, str]:
        r = g_session.get(url)

        if r.status_code != 200:
            r.raise_for_status()

        soup = BeautifulSoup(r.text, features="html.parser")
        result = {}

        for i in soup.body.find_all('div', attrs={'class': "row clear"}):
            try:
                name = i.h5.text
                value = i.span.text.strip()
            except AttributeError:
                # if div have no h5 or span child, just ignore it.
                continue

            # We can parse more, but we don't need it.
            if name in ('Filename', 'MD5 Hash'):
                result[name] = value
        try:
            result['Download'] = soup.find(id='downloadmirrorstoggle')['href'].strip()
        except TypeError:
            pass

        return result

    @staticmethod
    def _get_download_url(url: str) -> str:
        id = url.split('/')[-1]
        r = g_session.get(url)
        if ModDBDownloader._is_challenge_response(r.text, r.status_code):
            raise ModDBDownloadError(f"ModDB challenge page returned when requesting {url}")

        s = re.search(f'/downloads/mirror/{id}/[^"]*', r.text)
        if not s:
            raise ModDBDownloadError(f"Download link not found when requesting {url}")

        return g_session.get(f"https://www.moddb.com{s[0]}", allow_redirects=False).headers["location"]

    @staticmethod
    def _start_browser_services() -> None:
        global _browser_services_started

        if _browser_services_started:
            return

        environ.setdefault('DISPLAY', ':99')
        services = [
            ['Xvfb', ':99', '-screen', '0', '1280x900x24'],
            ['fluxbox'],
            ['x11vnc', '-display', ':99', '-forever', '-shared', '-nopw', '-quiet'],
            ['websockify', '--web=/usr/share/novnc', '6080', 'localhost:5900'],
        ]

        for command in services:
            try:
                _browser_processes.append(Popen(command, stdout=DEVNULL, stderr=DEVNULL))
            except FileNotFoundError as e:
                raise ModDBDownloadError(
                    f"Cannot start browser helper {command[0]}. Rebuild the container image."
                ) from e

        _browser_services_started = True
        sleep(2)

    def _browser_profile_dir(self, to: Path) -> Path:
        app_path = Path('/app')
        if app_path.is_dir():
            return app_path / '.moddb-firefox-profile'

        return to / 'moddb-firefox-profile'

    def _browser_download_dir(self, to: Path) -> Path:
        return to / 'moddb' / self.moddb_id

    @staticmethod
    def _quarantine_browser_download(path: Path, reason: str) -> None:
        invalid = path.with_name(f'{path.name}.invalid-{int(time.time())}')
        print(f'[!] Ignoring browser download {path.name}: {reason}')
        try:
            path.rename(invalid)
            print(f'[*] Moved rejected download to {invalid}')
        except OSError as e:
            print(f'[!] Could not move rejected download {path}: {e}')

    @staticmethod
    def _browser_archive_rejection_reason(
        archive: Path, expected_hash: str = None
    ) -> str | None:
        if not archive.is_file():
            return f'file does not exist: {archive}'

        try:
            head = archive.read_bytes()[:512]
        except OSError as e:
            return f'could not read file: {e}'

        stripped = head.lstrip().lower()
        if stripped.startswith((b'<!doctype html', b'<html')):
            return 'download is an HTML page, not an archive'

        suffix = archive.suffix.lower()
        if suffix == '.zip' and not zipfile.is_zipfile(archive):
            return 'download is not a valid ZIP archive'
        if suffix == '.7z' and not head.startswith(b'7z\xbc\xaf\x27\x1c'):
            return 'download is not a valid 7z archive'
        if suffix == '.rar' and not head.startswith((b'Rar!\x1a\x07\x00', b'Rar!\x1a\x07\x01\x00')):
            return 'download is not a valid RAR archive'

        if expected_hash and not check_hash(archive, expected_hash):
            return 'download hash does not match ModDB metadata'

        return None

    @staticmethod
    def _download_part_exists(path: Path) -> bool:
        return any((
            path.with_name(f'{path.name}.part').exists(),
            path.with_suffix(f'{path.suffix}.part').exists(),
            (path.parent / f'{path.name}.part').exists(),
        ))

    @staticmethod
    def _accept_browser_candidate(
        candidate: Path,
        dl_dir: Path,
        expected_name: str = None,
        expected_hash: str = None,
        stable_sizes: dict[str, int] = None,
        rejected: set[str] = None,
        quarantine_invalid: bool = True,
    ) -> Path | None:
        if expected_name and candidate.name != expected_name:
            return None

        if not candidate.is_file() or candidate.name.endswith(('.part', '.crdownload')):
            return None

        if ModDBDownloader._download_part_exists(candidate):
            return None

        try:
            size = candidate.stat().st_size
        except OSError:
            return None

        key = str(candidate)
        if stable_sizes is not None and stable_sizes.get(key) != size:
            stable_sizes[key] = size
            return None

        reason = ModDBDownloader._browser_archive_rejection_reason(candidate, expected_hash)
        if reason:
            if rejected is None or key not in rejected:
                if quarantine_invalid:
                    ModDBDownloader._quarantine_browser_download(candidate, reason)
                else:
                    print(f'[!] Ignoring browser download {candidate.name}: {reason}')
                if rejected is not None:
                    rejected.add(key)
            return None

        if candidate.parent == dl_dir:
            return candidate

        target = dl_dir / candidate.name
        shutil.move(str(candidate), str(target))
        return target

    def _get_cached_browser_archive(self, to: Path) -> Path:
        dl_dir = self._browser_download_dir(to)
        archives = [i for i in dl_dir.iterdir() if i.is_file() and not i.name.endswith(('.crdownload', '.part'))] \
            if dl_dir.is_dir() else []

        if not archives:
            return None

        if self._user_wanted_name:
            for archive in [i for i in archives if i.name != self._user_wanted_name]:
                print(
                    f'[*] Ignoring cached browser download {archive.name}; '
                    f'waiting for {self._user_wanted_name}'
                )
            archives = [i for i in archives if i.name == self._user_wanted_name]

        for archive in archives.copy():
            reason = self._browser_archive_rejection_reason(archive, self._archivehash)
            if reason:
                self._quarantine_browser_download(archive, reason)
                archives.remove(archive)

        if not archives:
            return None

        if len(archives) > 1:
            raise ModDBDownloadError(f"Multiple ModDB archives found in {dl_dir}; leave only the intended file")

        return archives[0]

    @staticmethod
    def _write_firefox_prefs(profile_dir: Path, dl_dir: Path) -> None:
        mime_types = ",".join([
            "application/octet-stream",
            "application/zip",
            "application/x-zip-compressed",
            "application/x-rar-compressed",
            "application/vnd.rar",
            "application/x-7z-compressed",
            "application/x-compressed",
        ])
        (profile_dir / 'prefs.js').write_text(
            f'user_pref("browser.download.folderList", 2);\n'
            f'user_pref("browser.download.dir", "{dl_dir}");\n'
            f'user_pref("browser.download.useDownloadDir", true);\n'
            f'user_pref("browser.download.manager.showWhenStarting", false);\n'
            f'user_pref("browser.download.alwaysOpenPanel", false);\n'
            f'user_pref("browser.download.always_ask_before_handling_new_types", false);\n'
            f'user_pref("ui.systemUsesDarkTheme", 1);\n'
            f'user_pref("browser.helperApps.neverAsk.saveToDisk", "{mime_types}");\n'
        )

    @staticmethod
    def _get_download_info_from_places(
        profile_dir: Path, since_us: int, expected_name: str = None
    ) -> tuple[Path, bool] | None:
        db = profile_dir / 'places.sqlite'
        wal = profile_dir / 'places.sqlite-wal'
        shm = profile_dir / 'places.sqlite-shm'
        tmp = profile_dir / 'places.tmp.sqlite'
        tmp_wal = profile_dir / 'places.tmp.sqlite-wal'
        tmp_shm = profile_dir / 'places.tmp.sqlite-shm'

        def cleanup():
            tmp.unlink(missing_ok=True)
            tmp_wal.unlink(missing_ok=True)
            tmp_shm.unlink(missing_ok=True)

        if not db.exists():
            return None
        try:
            # Firefox uses WAL mode for places.sqlite — copy the -wal and -shm
            # siblings too so SQLite replays the WAL when we open the copy.
            shutil.copy2(str(db), str(tmp))
            if wal.exists():
                shutil.copy2(str(wal), str(tmp_wal))
            if shm.exists():
                shutil.copy2(str(shm), str(tmp_shm))
            conn = sqlite3.connect(str(tmp))
            try:
                rows = conn.execute(
                    "SELECT d.content,"
                    " (SELECT m.content FROM moz_annos m"
                    "  JOIN moz_anno_attributes ma ON m.anno_attribute_id = ma.id"
                    "  WHERE m.place_id = d.place_id AND ma.name = 'downloads/metaData'"
                    "  LIMIT 1)"
                    " FROM moz_annos d"
                    " JOIN moz_anno_attributes da ON d.anno_attribute_id = da.id"
                    " WHERE da.name = 'downloads/destinationFileURI'"
                    "   AND d.lastModified >= ?"
                    " ORDER BY d.lastModified DESC",
                    (since_us,)
                ).fetchall()
                for row in rows:
                    dest = Path(unquote(urlparse(row[0]).path))
                    if expected_name and dest.name != expected_name:
                        continue
                    meta = json.loads(row[1]) if row[1] else {}
                    return dest, meta.get('state') == 1
            finally:
                conn.close()
                cleanup()
        except (sqlite3.OperationalError, OSError) as e:
            print(f'[!] places.sqlite read error: {e}')
            cleanup()
        return None

    @staticmethod
    def _wait_for_download(
        profile_dir: Path, dl_dir: Path, since_us: int, timeout: int = 600,
        expected_name: str = None, expected_hash: str = None,
        prompt_after: int = 0
    ) -> Path:
        logged_dest = False
        stable_sizes = {}
        rejected = set()
        prompt_shown = prompt_after == 0
        if prompt_shown:
            print(f'[*] click to solve captcha: {_browser_prompt_url}')

        for tick in range(timeout):
            if not prompt_shown and tick >= prompt_after:
                print(f'[*] click to solve captcha: {_browser_prompt_url}')
                prompt_shown = True

            # Fast path: prefs redirected the download into dl_dir
            if dl_dir.is_dir():
                candidates = [
                    f for f in dl_dir.iterdir()
                    if f.is_file() and not f.name.endswith(('.part', '.crdownload'))
                ]
                for candidate in candidates:
                    accepted = ModDBDownloader._accept_browser_candidate(
                        candidate, dl_dir, expected_name, expected_hash,
                        stable_sizes, rejected, quarantine_invalid=False
                    )
                    if accepted:
                        print(f'[+] Download complete: {accepted.name}')
                        return accepted

            db = profile_dir / 'places.sqlite'
            if not logged_dest and tick % 20 == 0:
                size_info = f'found ({db.stat().st_size} bytes)' if db.exists() else 'not found'
                print(f'[*] Waiting for download... places.sqlite: {size_info}')

            info = ModDBDownloader._get_download_info_from_places(
                profile_dir, since_us, expected_name
            )
            if info is not None:
                dest, is_complete = info
                if not logged_dest:
                    print(f'[*] Download detected: {dest} — waiting for Firefox to finish...')
                    logged_dest = True
                if is_complete:
                    accepted = ModDBDownloader._accept_browser_candidate(
                        dest, dl_dir, expected_name, expected_hash,
                        stable_sizes, rejected, quarantine_invalid=False
                    )
                    if accepted:
                        print(f'[+] Download complete: {accepted.name}')
                        return accepted

            sleep(1)
        raise ModDBDownloadError("Timed out waiting for download to complete in browser")

    def _download_with_browser(self, to: Path) -> Path:
        global _browser_download_succeeded

        cached = self._get_cached_browser_archive(to)
        if cached:
            self._archive = cached
            return cached

        self._start_browser_services()
        dl_dir = self._browser_download_dir(to)
        dl_dir.mkdir(parents=True, exist_ok=True)
        profile_dir = self._browser_profile_dir(to)
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._write_firefox_prefs(profile_dir, dl_dir)

        since_us = int(time.time() * 1_000_000)
        proc = Popen(
            ['firefox', '--no-remote', '--profile', str(profile_dir), self._url],
            env={**environ, 'DISPLAY': ':99'},
            stdout=DEVNULL, stderr=DEVNULL,
        )
        try:
            downloaded = self._wait_for_download(
                profile_dir, dl_dir, since_us,
                expected_name=self._user_wanted_name,
                expected_hash=self._archivehash,
                prompt_after=20 if _browser_download_succeeded else 0,
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
                proc.wait()

        self._archive = downloaded
        _browser_download_succeeded = True
        return downloaded

    def _set_vars_from_metadata(self):
        if not self._iurl:
            return

        try:
            metadata = self._parse_moddb_metadata(self._iurl) if self._iurl else {}

            self._archivehash = metadata.get('MD5 Hash', None)
            self._user_wanted_name = metadata.get('Filename', None)
        except HTTPError:
            metadata = {}

        return metadata

    def check(self, to: Path, update_cache: bool = False) -> None:
        if not self._iurl:
            raise HashError('No Info URL provided for this mod')

        metadata = self._set_vars_from_metadata()

        if not self._user_wanted_name:
            raise ModDBDownloadError(f'Could not find Filename in {self._iurl}')

        if not self._archivehash:
            raise ModDBDownloadError(f'Could not find archive hash in {self._iurl}')

        if metadata.get('Download', '') not in self._url:
            raise ModDBDownloadError(f'Skipping {self._user_wanted_name} since ModDB info do not match download url')

        self._url = self._get_download_url(self._url)

        super().check(to, update_cache)

    def download(self, to: Path, use_cached: bool = False, *args, **kwargs) -> Path:
        self._set_vars_from_metadata()
        try:
            self._url = self._get_download_url(self._url)
        except ModDBDownloadError as e:
            if 'challenge page' not in str(e) and 'Download link not found' not in str(e):
                raise
            return self._download_with_browser(to)

        return super().download(to, use_cached)
