#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2025 Bardia Moshiri <bardia@furilabs.com>

from argparse import ArgumentParser
from inspect import currentframe
from pathlib import Path
from time import time
import asyncio
import aiohttp
import json
import sys
import os

from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, signal
from dbus_fast import BusType, Variant

DEFAULT_REPO_CONFIG_DIR = "/usr/lib/android-store/repos"
CUSTOM_REPO_CONFIG_DIR = "/etc/android-store/repos"
CACHE_DIR = os.path.expanduser("~/.cache/android-store/repo")
DOWNLOAD_CACHE_DIR = os.path.expanduser("~/.cache/android-store/downloads")

class FDroidInterface(ServiceInterface):
    def __init__(self, verbose=False):
        store_print("Initializing F-Droid store daemon", verbose)
        super().__init__('io.FuriOS.AndroidStore.fdroid')
        self.verbose = verbose
        self.session = None

        # Task queue implementation
        self._task_queue = asyncio.Queue()
        self._task_processor = None
        self._running = False
        # Start the task processor
        self._start_task_processor()

    def _start_task_processor(self):
        """Start the async task processor if it's not already running"""
        if not self._running:
            self._running = True
            self._task_processor = asyncio.create_task(self._process_task_queue())
            store_print("Task processor started", self.verbose)

    async def _process_task_queue(self):
        """Process tasks in queue one at a time"""
        while self._running:
            try:
                # Get next task from queue
                task, future = await self._task_queue.get()
                store_print(f"Processing task: {task.__name__}", self.verbose)

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
                store_print(f"Task completed: {task.__name__}", self.verbose)
            except asyncio.CancelledError:
                break
            except Exception as e:
                store_print(f"Task processor error: {e}", self.verbose)

    async def _queue_task(self, task_func):
        """Queue a task and wait for its result"""
        future = asyncio.Future()
        await self._task_queue.put((task_func, future))

        store_print(f"Task queued: {task_func.__name__}", self.verbose)

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

        index_url = f"{repo_url.rstrip('/')}/index-v2.json"
        try:
            async with self.session.get(index_url) as response:
                if response.status == 200:
                    json_content = await response.text()
                    index_path = os.path.join(repo_cache_dir, 'index-v2.json')
                    with open(index_path, 'w') as f:
                        f.write(json_content)
                    return True
            return False
        except Exception as e:
            store_print(f"Error downloading index for {repo_url}: {e}", self.verbose)
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

    def get_package_info(self, package_id, metadata, version_info, repo_url):
        apk_name = version_info['file']['name']
        download_url = f"{repo_url.rstrip('/')}{apk_name}"

        icon_url = 'N/A'
        if 'icon' in metadata:
            icon_path = self.get_localized_text(metadata['icon'])
            if isinstance(icon_path, dict) and 'name' in icon_path:
                icon_url = f"{repo_url.rstrip('/')}{icon_path['name']}"

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

    def get_repo_url(self, repo_file):
        """Get the URL for a repository, prioritizing custom directory over default"""
        custom_path = os.path.join(CUSTOM_REPO_CONFIG_DIR, repo_file)
        if os.path.exists(custom_path) and os.path.isfile(custom_path):
            try:
                with open(custom_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            return line
            except Exception as e:
                store_print(f"Error reading {custom_path}: {e}", self.verbose)

        default_path = os.path.join(DEFAULT_REPO_CONFIG_DIR, repo_file)
        if os.path.exists(default_path) and os.path.isfile(default_path):
            try:
                with open(default_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            return line
            except Exception as e:
                store_print(f"Error reading {default_path}: {e}", self.verbose)
        return None

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

            if not os.path.exists(CACHE_DIR):
                store_print("Cache directory not found. Updating cache first", self.verbose)
                await self.update_cache()

            for repo_dir in os.listdir(CACHE_DIR):
                index_path = os.path.join(CACHE_DIR, repo_dir, 'index-v2.json')
                if not os.path.exists(index_path):
                    continue

                try:
                    repo_url = None
                    with open(os.path.join(DEFAULT_REPO_CONFIG_DIR, repo_dir), 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                repo_url = line
                                break

                    if not repo_url:
                        continue

                    with open(index_path, 'r') as f:
                        index_data = json.load(f)

                    for package_id, package_data in index_data['packages'].items():
                        name = self.get_localized_text(package_data['metadata'].get('name', ''))
                        if query.lower() in name.lower():
                            latest_version = self.get_latest_version(package_data['versions'])
                            if latest_version:
                                package_info = self.get_package_info(package_id, package_data['metadata'], latest_version, repo_url)
                                metadata = package_data['metadata']
                                app_info = {
                                    'repository': repo_dir,
                                    'id': package_id,
                                    'name': name,
                                    'summary': self.get_localized_text(metadata.get('summary', 'N/A')),
                                    'description': self.get_localized_text(metadata.get('description', 'N/A')),
                                    'license': metadata.get('license', 'N/A'),
                                    'categories': metadata.get('categories', []),
                                    'author': metadata.get('author', {}).get('name', 'N/A'),
                                    'web_url': metadata.get('webSite', 'N/A'),
                                    'source_url': metadata.get('sourceCode', 'N/A'),
                                    'tracker_url': metadata.get('issueTracker', 'N/A'),
                                    'changelog_url': metadata.get('changelog', 'N/A'),
                                    'donation_url': metadata.get('donate', 'N/A'),
                                    'added_date': metadata.get('added', 'N/A'),
                                    'last_updated': metadata.get('lastUpdated', 'N/A'),
                                    'package': package_info
                                }
                                results.append(app_info)
                                store_print(f"Search: found app {name}", self.verbose)
                except Exception as e:
                    store_print(f"Error parsing {index_path}: {e}", self.verbose)
                    continue
            return json.dumps(results)
        return await self._queue_task(_search_task)

    async def update_cache(self):
        success = True
        processed_repos = set()
        os.makedirs(CACHE_DIR, exist_ok=True)

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

        # Process all repositories, prioritizing custom directory
        for config_file in all_repo_files:
            # Check custom dir first, then fall back to default
            if os.path.exists(os.path.join(CUSTOM_REPO_CONFIG_DIR, config_file)):
                repo_dir = CUSTOM_REPO_CONFIG_DIR
            else:
                repo_dir = DEFAULT_REPO_CONFIG_DIR

            # Skip if we've already processed this repo
            if config_file in processed_repos:
                continue

            repos = self.read_repo_list(config_file, repo_dir)
            repo_success = False

            for repo_url in repos:
                repo_name = config_file
                store_print(f"Downloading {repo_name} index from {repo_url} (from {repo_dir})", self.verbose)
                if await self.download_index(repo_url, repo_name):
                    store_print(f"Successfully downloaded {repo_name}", self.verbose)
                    repo_success = True
                    processed_repos.add(config_file)
                    break
                else:
                    store_print(f"Failed to download from {repo_url}, trying next mirror...", self.verbose)

            if not repo_success:
                store_print(f"Failed to download {repo_name} from all mirrors", self.verbose)
                success = False

        await self.cleanup_session()
        return success

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
                for repo_dir in os.listdir(CACHE_DIR):
                    index_path = os.path.join(CACHE_DIR, repo_dir, 'index-v2.json')
                    if not os.path.exists(index_path):
                        continue

                    repo_url = self.get_repo_url(repo_dir)
                    if not repo_url:
                        continue

                    if not os.path.exists(index_path):
                        continue

                    config_dir = repo_locations.get(repo_dir, DEFAULT_REPO_CONFIG_DIR)

                    if not os.path.exists(os.path.join(config_dir, repo_dir)):
                        alt_config_dir = CUSTOM_REPO_CONFIG_DIR if config_dir == DEFAULT_REPO_CONFIG_DIR else DEFAULT_REPO_CONFIG_DIR
                        if os.path.exists(os.path.join(alt_config_dir, repo_dir)):
                            config_dir = alt_config_dir
                        else:
                            continue

                    with open(os.path.join(config_dir, repo_dir), 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                repo_url = line
                                break

                    if not repo_url:
                        continue

                    with open(index_path, 'r') as f:
                        index_data = json.load(f)

                    if package_id in index_data['packages']:
                        package_data = index_data['packages'][package_id]
                        latest_version = self.get_latest_version(package_data['versions'])
                        if latest_version:
                            package_info = self.get_package_info(package_id, package_data['metadata'], latest_version, repo_url)
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
                store_print(f"Container session manager is not started", self.verbose)
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
            for repo_dir in os.listdir(CACHE_DIR):
                index_path = os.path.join(CACHE_DIR, repo_dir, 'index-v2.json')
                if not os.path.exists(index_path):
                    continue

                try:
                    repo_url = self.get_repo_url(repo_dir)
                    if not repo_url:
                        continue

                    with open(index_path, 'r') as f:
                        index_data = json.load(f)

                    if package_name in index_data['packages']:
                        package_data = index_data['packages'][package_name]
                        latest_version = self.get_latest_version(package_data['versions'])
                        if latest_version:
                            repo_version = latest_version['manifest']['versionName']
                            if repo_version != current_version:
                                package_info = self.get_package_info(
                                    package_name,
                                    package_data['metadata'],
                                    latest_version,
                                    repo_url
                                )
                                upgradable_info = {
                                    'id': package_name,
                                    'packageInfo': package_info,
                                    'repo_url': repo_url,
                                    'current_version': current_version,
                                    'available_version': repo_version,
                                    'name': self.get_localized_text(package_data['metadata'].get('name', package_name))
                                }
                                upgradable.append(upgradable_info)
                                break
                except Exception as e:
                    store_print(f"Error parsing {index_path}: {e}", self.verbose)
                    continue
        return upgradable

    @method()
    async def UpgradePackages(self, packages: 'as') -> 'b':
        async def _upgrade_packages_task():
            store_print(f"Upgrading packages {packages}", self.verbose)
            upgradable = await self.get_upgradable_packages()

            ping = await self.ping_session_manager()
            if not ping:
                store_print("Container session manager is not started", self.verbose)
                return False

            if not packages:
                packages = [pkg['id'] for pkg in upgradable]
                store_print(f"Upgrading all available packages: {packages}", self.verbose)

            os.makedirs(DOWNLOAD_CACHE_DIR, exist_ok=True)
            await self.ensure_session()
            for package in packages:
                for pkg in upgradable:
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
        return await self._queue_task(_upgrade_packages_task)

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

    async def setup(self):
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()

        self.fdroid_interface = FDroidInterface(verbose=self.verbose)
        self.bus.export('/fdroid', self.fdroid_interface)

        await self.bus.request_name('io.FuriOS.AndroidStore')

        try:
            await self.bus.wait_for_disconnect()
        except:
            print("Session bus disconnected, exiting")
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
