"""
DownloadManager - Handle Fabric installer and Minecraft server.jar downloads.
Uses the Fabric Meta API for versions and installer, and the Mojang version
manifest API for the vanilla server.jar.
"""

import threading
from collections.abc import Callable
from pathlib import Path

import requests

from hosty.shared.utils.constants import (
    CACHE_DIR,
    FABRIC_GAME_VERSIONS_URL,
    FABRIC_INSTALLER_VERSIONS_URL,
    FABRIC_LOADER_VERSIONS_URL,
    FORGE_MAVEN_BASE,
    FORGE_PROMOTIONS_URL,
    HTTP_USER_AGENT,
    LOADER_FABRIC,
    LOADER_FORGE,
    LOADER_NEOFORGE,
    LOADER_PAPER,
    LOADER_PURPUR,
    LOADER_QUILT,
    LOADER_VANILLA,
    MOJANG_VERSION_MANIFEST_URL,
    NEOFORGE_MAVEN_BASE,
    NEOFORGE_MAVEN_METADATA_URL,
    PAPER_API_BASE,
    PURPUR_API_BASE,
    QUILT_GAME_VERSIONS_URL,
    QUILT_INSTALLER_VERSIONS_URL,
    QUILT_LOADER_VERSIONS_URL,
)
from hosty.shared.utils.subprocess_utils import hidden_subprocess_kwargs


def parse_version_tuple(v: str) -> tuple[int, ...]:
    """Parse version string into a tuple of integers for accurate numerical sorting."""
    try:
        clean = v.split("-")[0]
        return tuple(int(x) for x in clean.split(".") if x.isdigit())
    except Exception:
        return (0,)


def filter_neoforge_versions(neo_vers: list[str], mc_version: str) -> list[str]:
    """Filter NeoForge versions to strictly match the given Minecraft version."""
    if not mc_version:
        return []
    parts = mc_version.split(".")
    if len(parts) < 2:
        return []
    try:
        target_major = int(parts[1])
        target_minor = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return []

    matching = []
    for v in neo_vers:
        v_parts = v.split(".")
        if len(v_parts) >= 2 and v_parts[0].isdigit() and v_parts[1].isdigit():
            v_maj = int(v_parts[0])
            v_min = int(v_parts[1])
            if v_maj == target_major and v_min == target_minor:
                matching.append(v)
    return sorted(matching, key=parse_version_tuple, reverse=True)


class DownloadManager:
    """Manages downloads of Fabric components and vanilla server JARs."""

    def __init__(self):
        self._game_versions: list[dict] = []
        self._loader_versions: list[dict] = []
        self._installer_url: str | None = None
        self._installer_version: str | None = None
        self._mojang_manifest: dict | None = None

    def fetch_game_versions(self, include_snapshots: bool = False) -> list[str]:
        """
        Fetch available Minecraft game versions from Fabric Meta.
        Returns list of version strings, newest first.
        """
        try:
            resp = requests.get(FABRIC_GAME_VERSIONS_URL, timeout=15)
            resp.raise_for_status()
            self._game_versions = resp.json()

            versions = []
            for v in self._game_versions:
                if include_snapshots or v.get("stable", False):
                    versions.append(v["version"])

            return versions
        except Exception as e:
            print(f"Failed to fetch game versions: {e}")
            return []

    def fetch_loader_versions(self) -> list[str]:
        """Fetch available Fabric loader versions."""
        try:
            resp = requests.get(FABRIC_LOADER_VERSIONS_URL, timeout=15)
            resp.raise_for_status()
            self._loader_versions = resp.json()
            return [v["version"] for v in self._loader_versions]
        except Exception as e:
            print(f"Failed to fetch loader versions: {e}")
            return []

    def fetch_game_versions_for_loader(
        self, loader_type: str = LOADER_FABRIC, include_snapshots: bool = False
    ) -> list[str]:
        """Fetch game versions compatible with the given loader."""
        if loader_type == LOADER_QUILT:
            try:
                resp = requests.get(QUILT_GAME_VERSIONS_URL, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return [v["version"] for v in data if include_snapshots or v.get("stable", False)]
            except Exception as e:
                print(f"Failed to fetch Quilt game versions: {e}")
                return self.fetch_game_versions(include_snapshots)
        elif loader_type == LOADER_PAPER:
            try:
                headers = {"User-Agent": HTTP_USER_AGENT}
                resp = requests.get(PAPER_API_BASE, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                vers_dict = data.get("versions", {})
                all_vers = []
                if isinstance(vers_dict, dict):
                    for group_vers in vers_dict.values():
                        if isinstance(group_vers, list):
                            for v in group_vers:
                                if include_snapshots or not ("-rc" in v or "-pre" in v):
                                    all_vers.append(v)
                all_vers.reverse()
                return all_vers
            except Exception as e:
                print(f"Failed to fetch Paper game versions: {e}")
                return []
        elif loader_type == LOADER_PURPUR:
            try:
                resp = requests.get(PURPUR_API_BASE, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                versions = data.get("versions", [])
                versions.reverse()
                return versions
            except Exception as e:
                print(f"Failed to fetch Purpur game versions: {e}")
                return []
        elif loader_type == LOADER_VANILLA:
            manifest = self._fetch_mojang_manifest()
            if not manifest:
                return []
            versions = []
            for entry in manifest.get("versions", []):
                if include_snapshots or entry.get("type") == "release":
                    versions.append(entry.get("id"))
            return versions
        elif loader_type == LOADER_FORGE:
            promos = self._fetch_forge_promos()
            mc_vers = set()
            for key in promos.keys():
                if "-" in key:
                    mc_vers.add(key.split("-")[0])
            sorted_vers = sorted(list(mc_vers), key=parse_version_tuple, reverse=True)
            return sorted_vers or ["1.20.1", "1.19.2", "1.18.2", "1.16.5"]
        elif loader_type == LOADER_NEOFORGE:
            neo_vers = self._fetch_neoforge_versions()
            mc_vers = set()
            for nv in neo_vers:
                parts = nv.split(".")
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    major = int(parts[0])
                    minor = int(parts[1])
                    if major == 20:
                        mc_vers.add(f"1.20.{minor}" if minor > 0 else "1.20")
                    elif major == 21:
                        sub = f".{minor}" if minor > 0 else ""
                        mc_vers.add(f"1.21{sub}")
            sorted_vers = sorted(list(mc_vers), key=parse_version_tuple, reverse=True)
            return sorted_vers or ["1.21.4", "1.21.1", "1.20.4", "1.20.2"]

        raw = self.fetch_game_versions(include_snapshots)
        return sorted(raw, key=parse_version_tuple, reverse=True)

    def fetch_loader_versions_for_loader(
        self, loader_type: str = LOADER_FABRIC, mc_version: str = ""
    ) -> list[str]:
        """Fetch loader versions/builds for a specific loader and game version."""
        if loader_type == LOADER_QUILT:
            try:
                resp = requests.get(QUILT_LOADER_VERSIONS_URL, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return [v["version"] for v in data]
            except Exception as e:
                print(f"Failed to fetch Quilt loader versions: {e}")
                return []
        elif loader_type == LOADER_PAPER:
            if not mc_version:
                return []
            try:
                headers = {"User-Agent": HTTP_USER_AGENT}
                resp = requests.get(f"{PAPER_API_BASE}/versions/{mc_version}/builds", headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    builds = [str(b.get("id")) for b in data if isinstance(b, dict) and "id" in b]
                    return builds
                return []
            except Exception as e:
                print(f"Failed to fetch Paper builds for {mc_version}: {e}")
                return []
        elif loader_type == LOADER_PURPUR:
            return ["latest"]
        elif loader_type == LOADER_VANILLA:
            return []
        elif loader_type == LOADER_FORGE:
            if not mc_version:
                return []
            promos = self._fetch_forge_promos()
            rec = promos.get(f"{mc_version}-recommended")
            latest = promos.get(f"{mc_version}-latest")
            builds = []
            if latest:
                builds.append(latest)
            if rec and rec != latest:
                builds.append(rec)
            return builds or ["recommended", "latest"]
        elif loader_type == LOADER_NEOFORGE:
            if not mc_version:
                return []
            neo_vers = self._fetch_neoforge_versions()
            matching = filter_neoforge_versions(neo_vers, mc_version)
            return matching if matching else ["latest"]

        return self.fetch_loader_versions()

    def fetch_installer_info(self) -> tuple[str | None, str | None]:
        """
        Fetch the latest Fabric installer URL and version.
        Returns (url, version) tuple.
        """
        try:
            resp = requests.get(FABRIC_INSTALLER_VERSIONS_URL, timeout=15)
            resp.raise_for_status()
            installers = resp.json()

            if installers:
                latest = installers[0]
                self._installer_url = latest.get("url")
                self._installer_version = latest.get("version")
                return self._installer_url, self._installer_version
        except Exception as e:
            print(f"Failed to fetch installer info: {e}")

        return None, None

    def download_installer(self, progress_callback: Callable[[float, str], None] | None = None) -> str | None:
        """
        Download the Fabric installer JAR. Returns path to the downloaded file.
        Uses cache if already downloaded.
        """
        url, version = self.fetch_installer_info()
        if not url:
            return None

        # Check cache
        cached_jar = CACHE_DIR / f"fabric-installer-{version}.jar"
        if cached_jar.exists():
            if progress_callback:
                progress_callback(1.0, _("Using cached installer"))
            return str(cached_jar)

        try:
            if progress_callback:
                progress_callback(0.0, _("Downloading Fabric installer..."))

            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(cached_jar, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and progress_callback:
                        frac = downloaded / total
                        progress_callback(frac, _("Downloading installer... {:.0f} KB").format(downloaded / 1024))

            if progress_callback:
                progress_callback(1.0, _("Installer downloaded"))

            return str(cached_jar)

        except Exception as e:
            print(f"Failed to download installer: {e}")
            cached_jar.unlink(missing_ok=True)
            return None

    # ----- Mojang vanilla server.jar download -----

    def _fetch_mojang_manifest(self) -> dict | None:
        """Fetch the Mojang version manifest (cached per session)."""
        if self._mojang_manifest:
            return self._mojang_manifest
        try:
            resp = requests.get(MOJANG_VERSION_MANIFEST_URL, timeout=15)
            resp.raise_for_status()
            self._mojang_manifest = resp.json()
            return self._mojang_manifest
        except Exception as e:
            print(f"Failed to fetch Mojang manifest: {e}")
            return None

    def _get_version_json_url(self, mc_version: str) -> str | None:
        """Get the URL for a specific MC version's metadata JSON."""
        manifest = self._fetch_mojang_manifest()
        if not manifest:
            return None
        for entry in manifest.get("versions", []):
            if entry.get("id") == mc_version:
                return entry.get("url")
        return None

    def download_server_jar(
        self, mc_version: str, server_dir: str, progress_callback: Callable[[float, str], None] | None = None
    ) -> tuple[bool, str]:
        """
        Download the vanilla Minecraft server.jar from Mojang into server_dir.

        This is required because the Fabric installer only installs the loader;
        it expects server.jar to already be present.

        Args:
            mc_version: Minecraft version string (e.g. "1.21.4", "26.1.1")
            server_dir: Path to the server directory
            progress_callback: Optional (fraction, message) callback

        Returns:
            (success, message) tuple
        """
        dest = Path(server_dir) / "server.jar"

        # Skip if already present
        if dest.exists() and dest.stat().st_size > 1000:
            if progress_callback:
                progress_callback(1.0, _("server.jar already present"))
            return True, _("server.jar already present")

        try:
            # Step 1: Get version JSON URL from manifest
            if progress_callback:
                progress_callback(0.05, _("Fetching MC {} metadata...").format(mc_version))

            version_url = self._get_version_json_url(mc_version)
            if not version_url:
                return False, _("Minecraft version {} not found in Mojang manifest").format(mc_version)

            # Step 2: Fetch version JSON
            if progress_callback:
                progress_callback(0.1, _("Reading version details..."))

            resp = requests.get(version_url, timeout=15)
            resp.raise_for_status()
            version_data = resp.json()

            # Step 3: Extract server download URL
            downloads = version_data.get("downloads", {})
            server_info = downloads.get("server")
            if not server_info:
                return False, _("No server download available for MC {}").format(mc_version)

            jar_url = server_info.get("url")
            jar_size = server_info.get("size", 0)

            if not jar_url:
                return False, _("server.jar URL not found in version metadata")

            # Step 4: Download server.jar
            if progress_callback:
                progress_callback(0.15, _("Downloading server.jar..."))

            resp = requests.get(jar_url, stream=True, timeout=120)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", jar_size))
            downloaded = 0

            Path(server_dir).mkdir(parents=True, exist_ok=True)

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and progress_callback:
                        frac = 0.15 + (downloaded / total) * 0.85
                        size_mb = downloaded / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        progress_callback(
                            frac, _("Downloading server.jar... {:.1f}/{:.1f} MB").format(size_mb, total_mb)
                        )

            if progress_callback:
                progress_callback(1.0, _("server.jar downloaded"))

            return True, _("server.jar downloaded successfully")

        except Exception as e:
            # Clean up partial download
            dest.unlink(missing_ok=True)
            return False, _("Failed to download server.jar: {}").format(e)

    # ----- Fabric installation -----

    def install_fabric_server(
        self,
        java_path: str,
        installer_jar: str,
        mc_version: str,
        server_dir: str,
        loader_version: str | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
        """
        Run the Fabric installer to set up a server.

        Args:
            java_path: Path to the java binary.
            installer_jar: Path to the Fabric installer JAR.
            mc_version: Minecraft version string.
            server_dir: Directory to install the server into.
            loader_version: Optional specific loader version.
            progress_callback: Progress callback.

        Returns:
            (success, message) tuple.
        """
        import subprocess

        Path(server_dir).mkdir(parents=True, exist_ok=True)

        cmd = [
            java_path,
            "-jar",
            installer_jar,
            "server",
            "-mcversion",
            mc_version,
            "-dir",
            server_dir,
        ]

        if loader_version:
            cmd.extend(["-loader", loader_version])

        if progress_callback:
            progress_callback(0.5, _("Installing Fabric server for MC {}...").format(mc_version))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=server_dir,
                **hidden_subprocess_kwargs(),
            )

            if result.returncode == 0:
                # Verify the launch jar exists
                launch_jar = Path(server_dir) / "fabric-server-launch.jar"
                if launch_jar.exists():
                    if progress_callback:
                        progress_callback(1.0, _("Fabric server installed successfully"))
                    return True, _("Installation successful")
                else:
                    return False, _("Installation completed but fabric-server-launch.jar not found")
            else:
                error_msg = result.stderr or result.stdout or _("Unknown error")
                return False, _("Installation failed: {}").format(error_msg)

        except subprocess.TimeoutExpired:
            return False, _("Installation timed out (5 minutes)")
        except Exception as e:
            return False, _("Installation error: {}").format(e)

    # ----- Quilt / Paper / Purpur / Vanilla installation -----

    def download_quilt_installer(
        self, progress_callback: Callable[[float, str], None] | None = None
    ) -> str | None:
        """Download latest Quilt installer JAR."""
        try:
            resp = requests.get(QUILT_INSTALLER_VERSIONS_URL, timeout=15)
            resp.raise_for_status()
            installers = resp.json()
            if not installers:
                return None
            latest = installers[0]
            url = latest.get("url")
            version = latest.get("version")
            if not url:
                return None

            cached_jar = CACHE_DIR / f"quilt-installer-{version}.jar"
            if cached_jar.exists():
                if progress_callback:
                    progress_callback(1.0, _("Using cached Quilt installer"))
                return str(cached_jar)

            if progress_callback:
                progress_callback(0.0, _("Downloading Quilt installer..."))

            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()

            with open(cached_jar, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            return str(cached_jar)
        except Exception as e:
            print(f"Failed to download Quilt installer: {e}")
            return None

    def install_quilt_server(
        self,
        java_path: str,
        installer_jar: str,
        mc_version: str,
        server_dir: str,
        loader_version: str | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
        """Run Quilt installer to set up a server."""
        import subprocess

        Path(server_dir).mkdir(parents=True, exist_ok=True)
        cmd = [
            java_path,
            "-jar",
            installer_jar,
            "install",
            "server",
            mc_version,
        ]
        if loader_version:
            cmd.append(loader_version)
        cmd.extend([
            f"--install-dir={server_dir}",
            "--download-server",
        ])

        if progress_callback:
            progress_callback(0.5, _("Installing Quilt server for MC {}...").format(mc_version))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=server_dir,
                **hidden_subprocess_kwargs(),
            )
            if result.returncode == 0:
                if progress_callback:
                    progress_callback(1.0, _("Quilt server installed successfully"))
                return True, _("Installation successful")
            else:
                error_msg = result.stderr or result.stdout or _("Unknown error")
                return False, _("Installation failed: {}").format(error_msg)
        except Exception as e:
            return False, _("Installation error: {}").format(e)

    def install_paper_server(
        self,
        mc_version: str,
        server_dir: str,
        build: str | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
        """Download Paper server JAR from PaperMC v3 API."""
        Path(server_dir).mkdir(parents=True, exist_ok=True)
        dest = Path(server_dir) / "paper.jar"
        headers = {"User-Agent": HTTP_USER_AGENT}
        try:
            build_str = str(build or "").strip()
            if progress_callback:
                progress_callback(0.2, _("Fetching Paper build details for MC {}...").format(mc_version))

            resp = requests.get(f"{PAPER_API_BASE}/versions/{mc_version}/builds", headers=headers, timeout=15)
            resp.raise_for_status()
            builds = resp.json()
            if not isinstance(builds, list) or not builds:
                return False, _("No Paper builds found for MC {}").format(mc_version)

            target_build = None
            if build_str and build_str.isdigit():
                target_build = next((b for b in builds if str(b.get("id")) == build_str), None)
            if not target_build:
                target_build = builds[0]

            downloads = target_build.get("downloads", {})
            server_default = downloads.get("server:default", {})
            download_url = server_default.get("url")
            if not download_url:
                return False, _("Paper download URL not found")

            if progress_callback:
                progress_callback(0.4, _("Downloading Paper JAR..."))

            resp = requests.get(download_url, stream=True, headers=headers, timeout=120)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and progress_callback:
                        frac = 0.4 + (downloaded / total) * 0.6
                        progress_callback(
                            frac, _("Downloading Paper... {:.1f} MB").format(downloaded / (1024 * 1024))
                        )

            if progress_callback:
                progress_callback(1.0, _("Paper installed successfully"))
            return True, _("Paper installed successfully")
        except Exception as e:
            dest.unlink(missing_ok=True)
            return False, _("Failed to download Paper: {}").format(e)

    def _fetch_forge_promos(self) -> dict[str, str]:
        """Fetch Forge promotions slim dictionary."""
        try:
            resp = requests.get(FORGE_PROMOTIONS_URL, timeout=15)
            resp.raise_for_status()
            return resp.json().get("promos", {})
        except Exception as e:
            print(f"Failed to fetch Forge promos: {e}")
            return {}

    def _fetch_neoforge_versions(self) -> list[str]:
        """Fetch NeoForge versions list from maven metadata."""
        import xml.etree.ElementTree as ET

        try:
            resp = requests.get(NEOFORGE_MAVEN_METADATA_URL, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            return [v.text for v in root.findall(".//version") if v.text]
        except Exception as e:
            print(f"Failed to fetch NeoForge versions: {e}")
            return []

    def download_forge_installer(
        self, mc_version: str, forge_version: str, progress_callback: Callable[[float, str], None] | None = None
    ) -> str | None:
        """Download Forge installer JAR."""
        version_str = f"{mc_version}-{forge_version}"
        url = f"{FORGE_MAVEN_BASE}/{version_str}/forge-{version_str}-installer.jar"
        cached_jar = CACHE_DIR / f"forge-installer-{version_str}.jar"
        if cached_jar.exists():
            if progress_callback:
                progress_callback(1.0, _("Using cached Forge installer"))
            return str(cached_jar)

        try:
            if progress_callback:
                progress_callback(0.2, _("Downloading Forge installer..."))
            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()
            with open(cached_jar, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(cached_jar)
        except Exception as e:
            print(f"Failed to download Forge installer: {e}")
            cached_jar.unlink(missing_ok=True)
            return None

    def install_forge_server(
        self,
        java_path: str,
        installer_jar: str,
        server_dir: str,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
        """Run Forge installer to set up a server."""
        import subprocess

        Path(server_dir).mkdir(parents=True, exist_ok=True)
        cmd = [java_path, "-jar", installer_jar, "--installServer", server_dir]
        if progress_callback:
            progress_callback(0.5, _("Installing Forge server..."))
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=400, cwd=server_dir, **hidden_subprocess_kwargs()
            )
            if result.returncode == 0:
                return True, _("Forge installed successfully")
            return False, _("Forge installer failed: {}").format(result.stderr or result.stdout)
        except Exception as e:
            return False, _("Forge install error: {}").format(e)

    def download_neoforge_installer(
        self, neoforge_version: str, progress_callback: Callable[[float, str], None] | None = None
    ) -> str | None:
        """Download NeoForge installer JAR."""
        url = f"{NEOFORGE_MAVEN_BASE}/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"
        cached_jar = CACHE_DIR / f"neoforge-installer-{neoforge_version}.jar"
        if cached_jar.exists():
            if progress_callback:
                progress_callback(1.0, _("Using cached NeoForge installer"))
            return str(cached_jar)

        try:
            if progress_callback:
                progress_callback(0.2, _("Downloading NeoForge installer..."))
            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()
            with open(cached_jar, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(cached_jar)
        except Exception as e:
            print(f"Failed to download NeoForge installer: {e}")
            cached_jar.unlink(missing_ok=True)
            return None

    def install_neoforge_server(
        self,
        java_path: str,
        installer_jar: str,
        server_dir: str,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
        """Run NeoForge installer to set up a server."""
        import subprocess

        Path(server_dir).mkdir(parents=True, exist_ok=True)
        cmd = [java_path, "-jar", installer_jar, "--installServer", server_dir]
        if progress_callback:
            progress_callback(0.5, _("Installing NeoForge server..."))
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=400, cwd=server_dir, **hidden_subprocess_kwargs()
            )
            if result.returncode == 0:
                return True, _("NeoForge installed successfully")
            return False, _("NeoForge installer failed: {}").format(result.stderr or result.stdout)
        except Exception as e:
            return False, _("NeoForge install error: {}").format(e)

    def install_purpur_server(
        self,
        mc_version: str,
        server_dir: str,
        build: str | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
        """Download Purpur server JAR from Purpur API."""
        Path(server_dir).mkdir(parents=True, exist_ok=True)
        dest = Path(server_dir) / "purpur.jar"
        download_url = f"{PURPUR_API_BASE}/{mc_version}/latest/download"
        try:
            if progress_callback:
                progress_callback(0.2, _("Downloading Purpur JAR for MC {}...").format(mc_version))

            resp = requests.get(download_url, stream=True, timeout=120)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and progress_callback:
                        frac = 0.2 + (downloaded / total) * 0.8
                        progress_callback(
                            frac, _("Downloading Purpur... {:.1f} MB").format(downloaded / (1024 * 1024))
                        )

            if progress_callback:
                progress_callback(1.0, _("Purpur installed successfully"))
            return True, _("Purpur installed successfully")
        except Exception as e:
            dest.unlink(missing_ok=True)
            return False, _("Failed to download Purpur: {}").format(e)

    def fetch_all_versions_async(self, callback: Callable[[list[str], list[str]], None]):
        """
        Fetch game and loader versions in a background thread.
        Calls callback(game_versions, loader_versions) when done.
        """

        def _fetch():
            games = self.fetch_game_versions()
            loaders = self.fetch_loader_versions()
            callback(games, loaders)

        thread = threading.Thread(target=_fetch, daemon=True)
        thread.start()
        return thread
