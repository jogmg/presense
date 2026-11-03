"""Pytest configuration and local compatibility shims.

`genlayer-test` 0.29.2 predates two upstream changes:

1. GenVM 0.3.0 renamed its runner bundle from ``genvm-universal.tar.xz`` to
   ``genvm-runners-all.tar.xz``. The direct loader still asks for the old
   asset name and gets a 404 from the newest release.
2. The direct loader writes the contract message to a temp file, dup2s it onto
   stdin, then unlinks it. POSIX permits unlinking an open file; Windows raises
   ``WinError 32`` instead.

Both shims are narrow and can be removed once the toolchain handles these
cases. Set ``PRESENSE_SKIP_TOOLCHAIN_SHIMS=1`` to disable them.
"""

from __future__ import annotations

import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


def _shims_enabled() -> bool:
    return os.environ.get("PRESENSE_SKIP_TOOLCHAIN_SHIMS") != "1"


def _patch_runner_bundle_fallback() -> None:
    """Teach the direct loader about GenVM's renamed runner bundle."""
    from gltest.direct import sdk_loader

    original = sdk_loader.download_artifacts
    if getattr(original, "_presense_bundle_fallback", False):
        return

    def download_artifacts(version: str) -> Path:
        tarball = sdk_loader.CACHE_DIR / f"genvm-universal-{version}.tar.xz"
        if tarball.exists():
            return tarball

        try:
            return original(version)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise

        url = (
            f"{sdk_loader.GITHUB_RELEASES_URL}/download/{version}/"
            "genvm-runners-all.tar.xz"
        )
        request = urllib.request.Request(url)
        request.add_header("User-Agent", "gltest-direct")

        sdk_loader.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(request, timeout=300) as response:
            with tempfile.NamedTemporaryFile(
                delete=False, dir=sdk_loader.CACHE_DIR
            ) as tmp:
                tmp_path = Path(tmp.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    tmp.write(chunk)

        os.replace(tmp_path, tarball)
        return tarball

    download_artifacts._presense_bundle_fallback = True
    sdk_loader.download_artifacts = download_artifacts


def _patch_windows_stdin_cleanup() -> None:
    """Swallow only the Windows error raised while fd 0 holds the temp file."""
    from gltest.direct import loader

    original = loader._inject_message_to_fd0
    if getattr(original, "_presense_windows_safe", False):
        return

    def _windows_safe_inject(vm) -> None:
        real_unlink = os.unlink

        def safe_unlink(path, *args, **kwargs):
            try:
                real_unlink(path, *args, **kwargs)
            except PermissionError:
                # fd 0 still holds the file open; the OS reclaims it later.
                pass

        os.unlink = safe_unlink
        try:
            original(vm)
        finally:
            os.unlink = real_unlink

    _windows_safe_inject._presense_windows_safe = True
    loader._inject_message_to_fd0 = _windows_safe_inject


def pytest_configure(config) -> None:
    if not _shims_enabled():
        return

    _patch_runner_bundle_fallback()

    if sys.platform == "win32":
        _patch_windows_stdin_cleanup()
