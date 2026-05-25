import json
import re
import shutil
import sqlite3
import time

from bs4 import BeautifulSoup
from os import environ
from pathlib import Path
from requests.exceptions import HTTPError
from subprocess import DEVNULL, Popen
from time import sleep
from typing import Dict
from urllib.parse import urlparse, unquote

from launcher.exceptions import HashError, ModDBDownloadError
from launcher.mods.downloader.base import DefaultDownloader, g_session


_browser_processes = []
_browser_services_started = False


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

    def _get_cached_browser_archive(self, to: Path) -> Path:
        dl_dir = self._browser_download_dir(to)
        archives = [i for i in dl_dir.iterdir() if i.is_file() and not i.name.endswith(('.crdownload', '.part'))] \
            if dl_dir.is_dir() else []

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
        profile_dir: Path, since_us: int, debug: bool = False
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
                if debug:
                    names = [r[0] for r in conn.execute(
                        "SELECT DISTINCT name FROM moz_anno_attributes"
                    ).fetchall()]
                    wal_size = wal.stat().st_size if wal.exists() else 0
                    shm_size = shm.stat().st_size if shm.exists() else 0
                    total = conn.execute(
                        "SELECT COUNT(*) FROM moz_annos d"
                        " JOIN moz_anno_attributes da ON d.anno_attribute_id = da.id"
                        " WHERE da.name = 'downloads/destinationFileURI'"
                    ).fetchone()[0]
                    print(f'[*] places.sqlite annotation attributes: {names}')
                    print(f'[*] WAL={wal_size}B SHM={shm_size}B total download rows={total}')
                row = conn.execute(
                    "SELECT d.content,"
                    " (SELECT m.content FROM moz_annos m"
                    "  JOIN moz_anno_attributes ma ON m.anno_attribute_id = ma.id"
                    "  WHERE m.place_id = d.place_id AND ma.name = 'downloads/metaData'"
                    "  LIMIT 1)"
                    " FROM moz_annos d"
                    " JOIN moz_anno_attributes da ON d.anno_attribute_id = da.id"
                    " WHERE da.name = 'downloads/destinationFileURI'"
                    "   AND d.lastModified >= ?"
                    " ORDER BY d.lastModified DESC LIMIT 1",
                    (since_us,)
                ).fetchone()
                if row:
                    dest = Path(unquote(urlparse(row[0]).path))
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
    def _wait_for_download(profile_dir: Path, dl_dir: Path, since_us: int, timeout: int = 600) -> Path:
        logged_dest = False
        schema_dumped = False

        for tick in range(timeout):
            # Fast path: prefs redirected the download into dl_dir
            if dl_dir.is_dir():
                files = [
                    f for f in dl_dir.iterdir()
                    if f.is_file() and not f.name.endswith(('.part', '.crdownload'))
                ]
                if files:
                    sleep(1)
                    return files[0]

            db = profile_dir / 'places.sqlite'
            if not logged_dest and tick % 15 == 0:
                size_info = f'found ({db.stat().st_size} bytes)' if db.exists() else 'not found'
                print(f'[*] Waiting for download... places.sqlite: {size_info} | profile: {profile_dir}')

            debug = db.exists() and not schema_dumped
            if debug:
                schema_dumped = True

            info = ModDBDownloader._get_download_info_from_places(profile_dir, since_us, debug=debug)
            if info is not None:
                dest, is_complete = info
                if not logged_dest:
                    print(f'[*] Download detected: {dest} — waiting for Firefox to finish...')
                    logged_dest = True
                if is_complete:
                    print(f'[+] Download complete: {dest.name}')
                    sleep(1)
                    if dest.parent == dl_dir:
                        return dest
                    target = dl_dir / dest.name
                    shutil.move(str(dest), str(target))
                    return target

            sleep(1)
        raise ModDBDownloadError("Timed out waiting for download to complete in browser")

    def _download_with_browser(self, to: Path) -> Path:
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

        print('[+] ModDB requires a real browser session')
        print('[*] Open http://localhost:6080/vnc.html?autoconnect=1')
        print('[*] Solve the Cloudflare check, then click "Download Now" in the browser.')
        print('[*] The launcher will continue automatically once the file finishes downloading.')

        since_us = int(time.time() * 1_000_000)
        proc = Popen(
            ['firefox', '--no-remote', '--profile', str(profile_dir), self._url],
            env={**environ, 'DISPLAY': ':99'},
            stdout=DEVNULL, stderr=DEVNULL,
        )
        try:
            downloaded = self._wait_for_download(profile_dir, dl_dir, since_us)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
                proc.wait()

        self._archive = downloaded
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
