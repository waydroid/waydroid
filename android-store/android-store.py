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

REPO_CONFIG_DIR = "/etc/android-store/repos"
CACHE_DIR = os.path.expanduser("~/.cache/android-store/repo")
DOWNLOAD_CACHE_DIR = os.path.expanduser("~/.cache/android-store/downloads")

class FDroidInterface(ServiceInterface):
    def __init__(self, verbose=False):
        store_print("Initializing F-Droid store daemon", verbose)
        super().__init__('io.FuriOS.AndroidStore.fdroid')
        self.verbose = verbose
        self.session = None

    async def ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def cleanup_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def read_repo_list(self, repo_file):
        try:
            with open(os.path.join(REPO_CONFIG_DIR, repo_file), 'r') as f:
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
                with open(os.path.join(REPO_CONFIG_DIR, repo_dir), 'r') as f:
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

    async def update_cache(self):
        success = True
        processed_repos = set()

        os.makedirs(CACHE_DIR, exist_ok=True)

        for config_file in os.listdir(REPO_CONFIG_DIR):
            if not os.path.isfile(os.path.join(REPO_CONFIG_DIR, config_file)):
                continue

            # skip if we've already successfully processed this repo (don't redownload from a mirror)
            if config_file in processed_repos:
                continue

            repos = self.read_repo_list(config_file)
            repo_success = False

            for repo_url in repos:
                repo_name = config_file
                store_print(f"Downloading {repo_name} index from {repo_url}", self.verbose)

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
        ping = await self.ping_session_manager()
        if not ping:
            store_print("Container session manager is not started", self.verbose)
            return False
        return await self.update_cache()

    @method()
    async def Install(self, package_id: 's') -> 'b':
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
            repo_url = None

            for repo_dir in os.listdir(CACHE_DIR):
                index_path = os.path.join(CACHE_DIR, repo_dir, 'index-v2.json')
                if not os.path.exists(index_path):
                    continue

                with open(os.path.join(REPO_CONFIG_DIR, repo_dir), 'r') as f:
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

    @signal()
    def AppInstalled(self, package_id: 's') -> 's':
        return package_id

    @method()
    async def GetRepositories(self) -> 'a(ss)':
        store_print("Getting repositories", self.verbose)
        repositories = []

        ping = await self.ping_session_manager()
        if not ping:
            store_print(f"Container session manager is not started", self.verbose)
            return repositories

        try:
            for repo_file in os.listdir(REPO_CONFIG_DIR):
                repo_path = os.path.join(REPO_CONFIG_DIR, repo_file)
                if not os.path.isfile(repo_path):
                    continue

                with open(repo_path, 'r') as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    if lines:
                        repositories.append([repo_file, lines[0]])
            return repositories
        except Exception as e:
            store_print(f"Error reading repositories: {e}", self.verbose)
            return []

    @method()
    async def GetUpgradable(self) -> 'aa{sv}':
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
                    repo_url = None
                    with open(os.path.join(REPO_CONFIG_DIR, repo_dir), 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                repo_url = line
                                break

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

    @method()
    async def RemoveRepository(self, repo_id: 's') -> 'b':
        store_print(f"Removing repository {repo_id}", self.verbose)

        ping = await self.ping_session_manager()
        if not ping:
            store_print("Container session manager is not started", self.verbose)
            return False
        return True

    @method()
    async def GetInstalledApps(self) -> 'aa{sv}':
        store_print("Getting installed apps", self.verbose)

        ping = await self.ping_session_manager()
        if not ping:
            store_print("Container session manager is not started", self.verbose)
            return []
        return await self.get_apps_info()

    @method()
    async def UninstallApp(self, package_name: 's') -> 'b':
        store_print(f"Uninstalling app {package_name}", self.verbose)

        ping = await self.ping_session_manager()
        if not ping:
            store_print("Container session manager is not started", self.verbose)
            return False
        return await self.remove_app(package_name)

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

        await self.bus.wait_for_disconnect()

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
