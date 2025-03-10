#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2025 Bardia Moshiri <bardia@furilabs.com>
# Copyright (C) 2025 Luis Garcia <git@luigi311.com>

from argparse import ArgumentParser
from inspect import currentframe
from pathlib import Path
from time import time
import asyncio
import aiohttp
import aiofiles
import aiosqlite
import functools
import json
import msgspec
import sys
import os

from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, signal
from dbus_fast import BusType, Variant

DEFAULT_REPO_CONFIG_DIR = "/usr/lib/android-store/repos"
CUSTOM_REPO_CONFIG_DIR = "/etc/android-store/repos"
DATABASE = os.path.expanduser("~/.cache/android-store/android-store.db")
CACHE_DIR = os.path.expanduser("~/.cache/android-store/repo")
DOWNLOAD_CACHE_DIR = os.path.expanduser("~/.cache/android-store/downloads")
IDLE_TIMEOUT = 120

class FDroidInterface(ServiceInterface):
    def __init__(self, verbose=False, idle_callback=None):
        store_print("Initializing F-Droid store daemon", verbose)
        super().__init__('io.FuriOS.AndroidStore.fdroid')
        self.verbose = verbose
        self.session = None
        self.db = None
        self.idle_callback = idle_callback
        self.idle_timer = None

        # Task queue implementation
        self._task_queue = asyncio.Queue()
        self._task_processor = None
        self._running = False
        # Start the task processor
        self._start_task_processor()

        # Start the idle timer
        self._reset_idle_timer()

    async def init_db(self):
        os.makedirs(CACHE_DIR, exist_ok=True)

        # Connect to the SQLite database asynchronously
        self.db = await aiosqlite.connect(DATABASE)
        # Optional performance tweaks:
        # - Allow concurrent reads: conn.execute("PRAGMA journal_mode = WAL")
        await self.db.execute("PRAGMA journal_mode = WAL")
        # Create tables if they do not exist
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                repository TEXT NOT NULL,
                package_id TEXT NOT NULL,
                repository_url TEXT NOT NULL,
                name TEXT,
                summary TEXT,
                description TEXT,
                license TEXT,
                categories TEXT,
                author TEXT,
                web_url TEXT,
                source_url TEXT,
                tracker_url TEXT,
                changelog_url TEXT,
                donation_url TEXT,
                added_date TEXT,
                last_updated TEXT,
                package JSON,
                PRIMARY KEY (repository, package_id)
            )
        """)

        # Create an index for lower(name) to speed up searches
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_apps_lower_name ON apps(LOWER(name));
        """)

        await self.db.commit()
        store_print("Database initialized", self.verbose)

    def _start_task_processor(self):
        """Start the async task processor if it's not already running"""
        if not self._running:
            self._running = True
            self._task_processor = asyncio.create_task(self._process_task_queue())
            store_print("Task processor started", self.verbose)

    def _reset_idle_timer(self):
        """Reset the idle timer when activity occurs"""
        if self.idle_timer:
            self.idle_timer.cancel()

        if self.idle_callback:
            self.idle_timer = asyncio.create_task(self._idle_countdown())

    async def _idle_countdown(self):
        """Count down to service shutdown due to inactivity"""
        try:
            await asyncio.sleep(IDLE_TIMEOUT)
            store_print(f"Service idle for {IDLE_TIMEOUT} seconds, shutting down", self.verbose)
            if self.idle_callback:
                await self.idle_callback()
        except asyncio.CancelledError:
            pass

    async def _process_task_queue(self):
        """Process tasks in queue one at a time"""
        while self._running:
            try:
                # Get next task from queue
                task, future = await self._task_queue.get()

                # Reset idle timer on activity
                self._reset_idle_timer()

                try:
                    # Execute the task
                    result = await task()

                    # Set the result for the waiting caller
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                    store_print(f"Task error: {e}", self.verbose)

                # Mark task as done
                self._task_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                store_print(f"Task processor error: {e}", self.verbose)

    async def _queue_task(self, task_func):
        """Queue a task and wait for its result"""
        future = asyncio.Future()
        await self._task_queue.put((task_func, future))

        # Reset idle timer on activity
        self._reset_idle_timer()

        # Wait for the task to complete and return its result
        return await future

    async def ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def cleanup_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def read_repo_list(self, repo_file, repo_dir):
        try:
            with open(os.path.join(repo_dir, repo_file), 'r') as f:
                return [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except FileNotFoundError:
            return []

    async def ping_session_manager(self):
        bus = None
        try:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()

            introspection = await bus.introspect('id.waydro.Session', '/SessionManager')
            proxy = bus.get_proxy_object('id.waydro.Session', '/SessionManager', introspection)
            interface = proxy.get_interface('id.waydro.SessionManager')

            await interface.call_ping()

            bus.disconnect()

            return True
        except Exception as e:
            return False

    async def download_index(self, repo_url, repo_name):
        await self.ensure_session()

        repo_cache_dir = os.path.join(CACHE_DIR, repo_name)
        os.makedirs(repo_cache_dir, exist_ok=True)

        repo_url = repo_url.rstrip('/')
        index_url = f"{repo_url}/index-v2.json"
        try:
            async with self.session.get(index_url) as response:
                if response.status == 200:
                    json_content = await response.read()
                    index_path = os.path.join(repo_cache_dir, 'index-v2.json')
                    url_path = os.path.join(repo_cache_dir, "repo_url.txt")

                    async with aiofiles.open(index_path, 'wb') as f:
                        await f.write(json_content)
                    async with aiofiles.open(url_path, 'w') as f:
                        await f.write(repo_url)

                    return True
            return False
        except Exception as e:
            store_print(f"Error downloading index for {repo_url}: {e}", self.verbose)
            return False

    async def process_all_indexes_to_db(self):
        """
        Iterate through all repository index files in CACHE_DIR, parse them, and update
        the apps table in one transaction.
        """
        rows = []
        # Iterate over all subdirectories in CACHE_DIR (each repo should have its own folder)
        for repo_dir in os.listdir(CACHE_DIR):
            repo_path = os.path.join(CACHE_DIR, repo_dir)
            index_path = os.path.join(repo_path, 'index-v2.json')
            url_path = os.path.join(repo_path, 'repo_url.txt')

            if not os.path.exists(index_path) or not os.path.exists(url_path):
                continue
            try:
                async with aiofiles.open(index_path, 'rb') as f:
                    raw_data = await f.read()
                index_data = msgspec.json.decode(raw_data)

                async with aiofiles.open(url_path, 'r') as f:
                    repository_url = await f.read()
            except Exception as e:
                store_print(f"Error processing {index_path}: {e}", self.verbose)
                continue

            # Process each package from the index
            for package_id, package_data in index_data.get("packages", {}).items():
                name = self.get_localized_text(package_data["metadata"].get("name", ""))
                latest_version = self.get_latest_version(package_data["versions"])
                if not latest_version:
                    continue

                package_info = self.get_package_info(package_id, package_data["metadata"], latest_version, repository_url)
                row = {
                    "repository": repo_dir,
                    "package_id": package_id,
                    "repository_url": repository_url,
                    "name": name,
                    "summary": self.get_localized_text(package_data["metadata"].get("summary", "N/A")),
                    "description": self.get_localized_text(package_data["metadata"].get("description", "N/A")),
                    "license": package_data["metadata"].get("license", "N/A"),
                    "categories": json.dumps(package_data["metadata"].get("categories", [])),
                    "author": package_data["metadata"].get("author", {}).get("name", "N/A"),
                    "web_url": package_data["metadata"].get("webSite", "N/A"),
                    "source_url": package_data["metadata"].get("sourceCode", "N/A"),
                    "tracker_url": package_data["metadata"].get("issueTracker", "N/A"),
                    "changelog_url": package_data["metadata"].get("changelog", "N/A"),
                    "donation_url": json.dumps(package_data["metadata"].get("donate", [])),
                    "added_date": package_data["metadata"].get("added", "N/A"),
                    "last_updated": package_data["metadata"].get("lastUpdated", "N/A"),
                    "package": json.dumps(package_info),
                }
                rows.append(row)

            # Clean up the index files after processing to prevent reprocessing
            os.remove(index_path)
            os.remove(url_path)

        # If any rows were gathered, update the database in one transaction.
        if rows:
            async with self.db.execute("BEGIN TRANSACTION;"):
                # full refresh, clear all previous entries.
                await self.db.execute("DELETE FROM apps;")
                await self.db.executemany(
                    """
                    INSERT INTO apps (
                        repository, package_id, repository_url, name, summary, description, license,
                        categories, author, web_url, source_url, tracker_url, changelog_url,
                        donation_url, added_date, last_updated, package
                    )
                    VALUES (
                        :repository, :package_id, :repository_url, :name, :summary, :description, :license,
                        :categories, :author, :web_url, :source_url, :tracker_url, :changelog_url,
                        :donation_url, :added_date, :last_updated, :package
                    )
                    ON CONFLICT(repository, package_id) DO UPDATE SET
                        repository_url = excluded.repository_url,
                        name = excluded.name,
                        summary = excluded.summary,
                        description = excluded.description,
                        license = excluded.license,
                        categories = excluded.categories,
                        author = excluded.author,
                        web_url = excluded.web_url,
                        source_url = excluded.source_url,
                        tracker_url = excluded.tracker_url,
                        changelog_url = excluded.changelog_url,
                        donation_url = excluded.donation_url,
                        added_date = excluded.added_date,
                        last_updated = excluded.last_updated,
                        package = excluded.package;
                    """,
                    rows,
                )
                await self.db.commit()
            store_print("Database updated successfully from cached indexes", self.verbose)
            return True
        else:
            store_print("No index data found in cache.", self.verbose)
            return False

    def get_localized_text(self, text_obj, lang='en-US'):
        if isinstance(text_obj, dict):
            return text_obj.get(lang, list(text_obj.values())[0] if text_obj else 'N/A')
        return text_obj if text_obj else 'N/A'

    def get_latest_version(self, versions):
        if not versions:
            return None

        latest = sorted(
            versions.items(),
            key=lambda x: x[1]['manifest']['versionCode'] if 'versionCode' in x[1]['manifest'] else 0,
            reverse=True
        )[0]

        return latest[1]

    def get_package_info(self, package_id, metadata, version_info, repository_url):
        apk_name = version_info['file']['name']
        download_url = f"{repository_url}{apk_name}"

        icon_url = 'N/A'
        if 'icon' in metadata:
            icon_path = self.get_localized_text(metadata['icon'])
            if isinstance(icon_path, dict) and 'name' in icon_path:
                icon_url = f"{repository_url}{icon_path['name']}"

        manifest = version_info['manifest']
        return {
            'apk_name': apk_name.lstrip('/'),
            'download_url': download_url,
            'icon_url': icon_url,
            'version': manifest.get('versionName', 'N/A'),
            'version_code': manifest.get('versionCode', 'N/A'),
            'size': version_info['file'].get('size', 'N/A'),
            'min_sdk': manifest.get('usesSdk', {}).get('minSdkVersion', 'N/A'),
            'target_sdk': manifest.get('usesSdk', {}).get('targetSdkVersion', 'N/A'),
            'permissions': [p['name'] for p in manifest.get('usesPermission', []) if isinstance(p, dict)],
            'features': manifest.get('features', []),
            'hash': version_info['file'].get('sha256', 'N/A'),
            'hash_type': 'sha256'
        }

    async def install_app(self, package_path):
        try:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()

            introspection = await bus.introspect('id.waydro.Session', '/SessionManager')
            proxy = bus.get_proxy_object('id.waydro.Session', '/SessionManager', introspection)
            interface = proxy.get_interface('id.waydro.SessionManager')

            await interface.call_install_app(package_path)

            bus.disconnect()
            return True
        except Exception as e:
            store_print(f"Error installing app: {e}", self.verbose)
            return False

    async def remove_app(self, package_name):
        try:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()

            introspection = await bus.introspect('id.waydro.Session', '/SessionManager')
            proxy = bus.get_proxy_object('id.waydro.Session', '/SessionManager', introspection)
            interface = proxy.get_interface('id.waydro.SessionManager')

            await interface.call_remove_app(package_name)

            bus.disconnect()
            return True
        except Exception as e:
            store_print(f"Error removing app: {e}", self.verbose)
            return False

    async def get_apps_info(self):
        try:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()
            introspection = await bus.introspect('id.waydro.Session', '/SessionManager')
            proxy = bus.get_proxy_object('id.waydro.Session', '/SessionManager', introspection)
            interface = proxy.get_interface('id.waydro.SessionManager')

            apps_info = await interface.call_get_apps_info()
            result = []

            for app in apps_info:
                app_info = {
                    'id': Variant('s', app['packageName'].value),
                    'packageName': Variant('s', app['packageName'].value),
                    'name': Variant('s', app['name'].value),
                    'versionName': Variant('s', app['versionName'].value),
                    'state': Variant('s', 'installed')
                }
                result.append(app_info)

            bus.disconnect()
            return result
        except Exception as e:
            store_print(f"Error getting apps info: {e}", self.verbose)
            return []

    @method()
    async def Search(self, query: 's') -> 's':
        async def _search_task():
            store_print(f"Searching for {query}", self.verbose)
            results = []

            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return json.dumps(results)

            # Use the database to perform the search.
            sql_query = """
                SELECT repository, package_id, name, summary, description, license,
                    categories, author, web_url, source_url, tracker_url, 
                    changelog_url, donation_url, added_date, last_updated, package
                FROM apps
                WHERE LOWER(name) LIKE LOWER(?)
            """
            # Wildcard search, e.g. "%query%"
            async with self.db.execute(sql_query, (f"%{query}%",)) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    app_info = {
                        'repository': row[0],
                        'id': row[1],
                        'name': row[2],
                        'summary': row[3],
                        'description': row[4],
                        'license': row[5],
                        'categories': json.loads(row[6]) if row[6] else None,
                        'author': row[7],
                        'web_url': row[8],
                        'source_url': row[9],
                        'tracker_url': row[10],
                        'changelog_url': row[11],
                        'donation_url': json.loads(row[12]) if row[12] else None,
                        'added_date': row[13],
                        'last_updated': row[14],
                        'package': json.loads(row[15]) if row[15] else None
                    }
                    results.append(app_info)
            return json.dumps(results)
        return await self._queue_task(_search_task)

    async def process_repo_file(self, config_file, repo_dir):
        """
        Process a single repository configuration file by iterating through its mirrors sequentially.
        """
        repos = self.read_repo_list(config_file, repo_dir)
        repo_success = False
        for repo_url in repos:
            store_print(f"Downloading {config_file} index from {repo_url} (from {repo_dir})", self.verbose)
            if await self.download_index(repo_url, config_file):
                store_print(f"Successfully downloaded {config_file}", self.verbose)
                repo_success = True
                break
            else:
                store_print(f"Failed to download from {repo_url}, trying next mirror...", self.verbose)
        
        if not repo_success:
            store_print(f"Failed to download {config_file} from all mirrors", self.verbose)
        
        return repo_success

    async def update_cache(self):
        all_repo_files = set()

        if os.path.exists(CUSTOM_REPO_CONFIG_DIR) and os.path.isdir(CUSTOM_REPO_CONFIG_DIR):
            for config_file in os.listdir(CUSTOM_REPO_CONFIG_DIR):
                if os.path.isfile(os.path.join(CUSTOM_REPO_CONFIG_DIR, config_file)):
                    all_repo_files.add(config_file)
                    store_print(f"Found repository in custom dir: {config_file}", self.verbose)

        if os.path.exists(DEFAULT_REPO_CONFIG_DIR) and os.path.isdir(DEFAULT_REPO_CONFIG_DIR):
            for config_file in os.listdir(DEFAULT_REPO_CONFIG_DIR):
                if os.path.isfile(os.path.join(DEFAULT_REPO_CONFIG_DIR, config_file)) and config_file not in all_repo_files:
                    all_repo_files.add(config_file)
                    store_print(f"Found repository in default dir: {config_file}", self.verbose)

        tasks = []
        for config_file in all_repo_files:
            # Check custom dir first, then fall back to default
            if os.path.exists(os.path.join(CUSTOM_REPO_CONFIG_DIR, config_file)):
                repo_dir = CUSTOM_REPO_CONFIG_DIR
            else:
                repo_dir = DEFAULT_REPO_CONFIG_DIR
            tasks.append(asyncio.create_task(self.process_repo_file(config_file, repo_dir)))

        results = await asyncio.gather(*tasks)
        overall_success = all(results)
        await self.process_all_indexes_to_db()

        await self.cleanup_session()
        return overall_success

    @method()
    async def UpdateCache(self) -> 'b':
        async def _update_cache_task():
            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return False
            return await self.update_cache()
        return await self._queue_task(_update_cache_task)

    @method()
    async def Install(self, package_id: 's') -> 'b':
        async def _install_task():
            store_print(f"Installing package {package_id}", self.verbose)
            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return False

            if not os.path.exists(CACHE_DIR):
                store_print("Cache directory not found. Updating cache first", self.verbose)
                await self.update_cache()

            try:
                package_info = None
                sql_query = """
                    SELECT repository, package
                    FROM apps
                    WHERE package_id = ?
                """

                async with self.db.execute(sql_query, (package_id,)) as cursor:
                    rows = await cursor.fetchall()
                    if len(rows) > 1:
                        store_print(f"Multiple entries found for {package_id}", self.verbose)
                    
                    for row in rows:
                        repository, package_json = row
                        store_print(f"Found package {package_id} in {repository}", self.verbose)
                        package_info = json.loads(package_json)
                        break

                if not package_info:
                    store_print(f"Package {package_id} not found", self.verbose)
                    return False

                os.makedirs(DOWNLOAD_CACHE_DIR, exist_ok=True)
                await self.ensure_session()
                filepath = os.path.join(DOWNLOAD_CACHE_DIR, package_info['apk_name'])
                async with self.session.get(package_info['download_url']) as response:
                    if response.status == 200:
                        with open(filepath, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)

                        store_print(f"APK downloaded to: {filepath}", self.verbose)
                        success = await self.install_app(filepath)
                        os.remove(filepath)
                        if success:
                            self.AppInstalled(package_id)
                            store_print(f"Successfully installed {package_id}", self.verbose)
                            return True
                        else:
                            store_print(f"Failed to install {package_id}", self.verbose)
                            return False
                    else:
                        store_print(f"Download failed with status: {response.status}", self.verbose)
                        return False
            except Exception as e:
                store_print(f"Installation failed: {e}", self.verbose)
                return False
        return await self._queue_task(_install_task)

    @signal()
    def AppInstalled(self, package_id: 's') -> 's':
        return package_id

    @method()
    async def GetRepositories(self) -> 'a(ss)':
        async def _get_repositories_task():
            store_print("Getting repositories", self.verbose)
            repositories = []

            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return repositories

            repo_files = {}  # filename -> (repo_dir, url)

            if os.path.exists(CUSTOM_REPO_CONFIG_DIR) and os.path.isdir(CUSTOM_REPO_CONFIG_DIR):
                for repo_file in os.listdir(CUSTOM_REPO_CONFIG_DIR):
                    repo_path = os.path.join(CUSTOM_REPO_CONFIG_DIR, repo_file)
                    if os.path.isfile(repo_path):
                        with open(repo_path, 'r') as f:
                            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                            if lines:
                                repo_files[repo_file] = (CUSTOM_REPO_CONFIG_DIR, lines[0])

            if os.path.exists(DEFAULT_REPO_CONFIG_DIR) and os.path.isdir(DEFAULT_REPO_CONFIG_DIR):
                for repo_file in os.listdir(DEFAULT_REPO_CONFIG_DIR):
                    if repo_file in repo_files:
                        continue

                    repo_path = os.path.join(DEFAULT_REPO_CONFIG_DIR, repo_file)
                    if os.path.isfile(repo_path):
                        with open(repo_path, 'r') as f:
                            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                            if lines:
                                repo_files[repo_file] = (DEFAULT_REPO_CONFIG_DIR, lines[0])

            for repo_file, (repo_dir, repo_url) in repo_files.items():
                source = "custom" if repo_dir == CUSTOM_REPO_CONFIG_DIR else "default"
                repositories.append([f"{repo_file} ({source})", repo_url])
            return repositories

        return await self._queue_task(_get_repositories_task)

    @method()
    async def GetUpgradable(self) -> 'aa{sv}':
        async def _get_upgradable_task():
            store_print("Getting upgradable", self.verbose)
            upgradable = []

            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return upgradable

            raw_upgradable = await self.get_upgradable_packages()
            for pkg in raw_upgradable:
                upgradable_info = {
                    'id': Variant('s', pkg['id']),
                    'name': Variant('s', pkg.get('name', pkg['id'])),
                    'packageName': Variant('s', pkg['id']),
                    'currentVersion': Variant('s', pkg['current_version']),
                    'availableVersion': Variant('s', pkg['available_version']),
                    'repository': Variant('s', pkg['repo_url']),
                    'package': Variant('s', json.dumps(pkg['packageInfo']))
                }
                upgradable.append(upgradable_info)
                store_print(f"{upgradable_info['packageName'].value} {upgradable_info['name'].value} {upgradable_info['currentVersion'].value} {upgradable_info['availableVersion'].value}", self.verbose)
            return upgradable
        return await self._queue_task(_get_upgradable_task)

    async def get_upgradable_packages(self):
        upgradable = []
        installed_apps = await self.get_apps_info()
        if not os.path.exists(CACHE_DIR):
            store_print("Cache directory not found. Updating cache first", self.verbose)
            await self.update_cache()

        for app in installed_apps:
            package_name = app['packageName'].value
            current_version = app['versionName'].value

            async with self.db.execute(
                "SELECT repository, package, package_id, repository_url FROM apps WHERE package_id = ?",
                (package_name,)
            ) as cursor:
                rows = await cursor.fetchall()

            for row in rows:
                repository, package_json, package_id, repository_url = row
                if not package_json:
                    continue
                available_pkg = json.loads(package_json)
                repo_version = available_pkg.get("version", "N/A")

                if repo_version != current_version:
                    upgradable_info = {
                        'id': package_name,
                        'packageInfo': available_pkg,
                        'repo_url': repository_url,
                        'current_version': current_version,
                        'available_version': repo_version,
                        'name': app['name'].value,
                    }
                    upgradable.append(upgradable_info)
                    break
        return upgradable

    @method()
    async def UpgradePackages(self, packages: 'as') -> 'b':
        async def _upgrade_packages_task(packages: 'as'):
            store_print(f"Upgrading packages {packages}", self.verbose)

            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return False

            upgradables = await self.get_upgradable_packages()
            if not packages:
                packages = [pkg['id'] for pkg in upgradables]
                store_print(f"Upgrading all available packages: {packages}", self.verbose)

            os.makedirs(DOWNLOAD_CACHE_DIR, exist_ok=True)
            await self.ensure_session()
            for package in packages:
                for pkg in upgradables:
                    if pkg['id'] == package:
                        store_print(f"Installing upgrade for {package}", self.verbose)
                        try:
                            package_info = pkg['packageInfo']
                            download_url = package_info['download_url']
                            apk_name = package_info['apk_name']
                            filepath = os.path.join(DOWNLOAD_CACHE_DIR, apk_name)
                            async with self.session.get(download_url) as response:
                                if response.status == 200:
                                    with open(filepath, 'wb') as f:
                                        async for chunk in response.content.iter_chunked(8192):
                                            f.write(chunk)

                                    store_print(f"APK downloaded to: {filepath}", self.verbose)
                                    success = await self.install_app(filepath)
                                    os.remove(filepath)
                                    if not success:
                                        store_print(f"Failed to upgrade {package}", self.verbose)
                                        return False
                                else:
                                    store_print(f"Download failed with status: {response.status}", self.verbose)
                                    return False
                        except Exception as e:
                            store_print(f"Error upgrading {package}: {e}", self.verbose)
                            return False
                        break
            await self.cleanup_session()
            return True
        return await self._queue_task(functools.partial(_upgrade_packages_task, packages))

    @method()
    async def RemoveRepository(self, repo_id: 's') -> 'b':
        async def _remove_repository_task():
            store_print(f"Removing repository {repo_id}", self.verbose)
            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return False
            return True
        return await self._queue_task(_remove_repository_task)

    @method()
    async def GetInstalledApps(self) -> 'aa{sv}':
        async def _get_installed_apps_task():
            store_print("Getting installed apps", self.verbose)
            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return []
            return await self.get_apps_info()
        return await self._queue_task(_get_installed_apps_task)

    @method()
    async def UninstallApp(self, package_name: 's') -> 'b':
        async def _uninstall_app_task():
            store_print(f"Uninstalling app {package_name}", self.verbose)
            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return False
            return await self.remove_app(package_name)
        return await self._queue_task(_uninstall_app_task)

    async def cleanup(self):
        """Clean up resources when service is stopping"""
        self._running = False
        if self.idle_timer:
            self.idle_timer.cancel()
        if self._task_processor:
            self._task_processor.cancel()
            try:
                await self._task_processor
            except asyncio.CancelledError:
                pass
        await self.cleanup_session()

class AndroidStoreService:
    def __init__(self, verbose):
        store_print("Initializing Android store service", verbose)
        self.verbose = verbose
        self.bus = None
        self.fdroid_interface = None
        self.shutdown_event = asyncio.Event()

    async def shutdown(self):
        """Shutdown the service after idle timeout"""
        store_print("Shutting down service due to inactivity", self.verbose)
        self.shutdown_event.set()

    async def setup(self):
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()

        self.fdroid_interface = FDroidInterface(verbose=self.verbose, idle_callback=self.shutdown)
        # Initialize the database
        await self.fdroid_interface.init_db()
        self.bus.export('/fdroid', self.fdroid_interface)

        await self.bus.request_name('io.FuriOS.AndroidStore')

        try:
            disconnect_task = asyncio.create_task(self.bus.wait_for_disconnect())
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())

            done, pending = await asyncio.wait(
                [disconnect_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if disconnect_task in done:
                print("Session bus disconnected, exiting")
            else:
                print("Idle timeout reached, exiting")
        except Exception as e:
            store_print(f"Error in service main loop: {e}", self.verbose)
        finally:
            if self.fdroid_interface:
                await self.fdroid_interface.cleanup()

def store_print(message, verbose):
    if not verbose:
        return

    frame = currentframe()
    caller_frame = frame.f_back

    bus_name = None

    if 'self' in caller_frame.f_locals:
        cls = caller_frame.f_locals['self']
        cls_name = cls.__class__.__name__

        if hasattr(cls, 'bus') and cls.bus:
            bus_name = cls.bus._requested_name if hasattr(cls.bus, '_requested_name') else None
        elif hasattr(cls, '_interface_name'):
            bus_name = cls._interface_name

        func_name = caller_frame.f_code.co_name

        if bus_name:
            full_message = f"[{bus_name}] {cls_name}.{func_name}: {message}"
        else:
            full_message = f"{cls_name}.{func_name}: {message}"
    else:
        func_name = caller_frame.f_code.co_name
        full_message = f"{func_name}: {message}"
    print(f"{time()} {full_message}")

async def main():
    # Disable buffering for stdout and stderr so that logs are written immediately
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    parser = ArgumentParser(description="Run the Android store daemon", add_help=False)
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output.')
    args = parser.parse_args()

    service = AndroidStoreService(verbose=args.verbose)
    await service.setup()

if __name__ == "__main__":
    asyncio.run(main())
