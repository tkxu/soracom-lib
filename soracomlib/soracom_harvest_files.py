#!/usr/bin/env python3
"""
SORACOM Harvest Files utility library.

Provides authentication, file listing, download, upload,
and related helper functions for the SORACOM Harvest Files API.

Copyright (c) 2025-2026 tkxu

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

History:
    Rev. 0.80  2025-03-23
    Rev. 0.90  2026-06-06
"""

from __future__ import annotations

import json
import logging
import mimetypes
import netrc
import os
import shutil
import tempfile
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator

import requests

__all__ = [
    # Constants
    "API_BASE",
    "NETRC_HOST",
    "NETRC_PATHS",
    "LEVEL_INFO",
    "LEVEL_WARN",
    "LEVEL_ERROR",
    # Data classes
    "AuthInfo",
    # Core helpers
    "read_auth_keys",
    "authenticate",
    "get_with_auth",
    "delete_with_auth",
    "list_files_iterative",
    "download_and_save",
    "upload_file_to_soracom",
    "is_recent",
]

# ---------------------------------------------
# Constants
# ---------------------------------------------

API_BASE = "https://g.api.soracom.io/v1"
NETRC_HOST = "api.soracom.io"
NETRC_PATHS = (
    os.path.expanduser("~/.netrc"),
)

LEVEL_INFO = "INFO"
LEVEL_WARN = "WARN"
LEVEL_ERROR = "ERROR"

# ---------------------------------------------
# Logging
# ---------------------------------------------

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def log_status(message: str, level: str = LEVEL_INFO) -> None:
    """Simple, centralized logging wrapper."""
    if level == LEVEL_ERROR:
        logger.error(message)
    elif level == LEVEL_WARN:
        logger.warning(message)
    else:
        logger.info(message)


# ---------------------------------------------
# Data classes
# ---------------------------------------------

@dataclass(frozen=True)
class AuthInfo:
    """Authentication information loaded from netrc or other sources."""

    api_key: str
    api_token: str


# ---------------------------------------------
# Authentication helpers
# ---------------------------------------------

def read_auth_keys(base_dir: str | None = None) -> AuthInfo:
    """
    Read SORACOM API key and token from a .netrc file.

    The machine name used is NETRC_HOST. If base_dir is given, it is checked
    first; otherwise, standard NETRC_PATHS are searched.
    """
    candidates: list[str] = []

    if base_dir is not None:
        candidates.append(os.path.join(base_dir, ".netrc"))

    candidates.extend(NETRC_PATHS)

    for path in candidates:
        if not os.path.exists(path):
            continue

        try:
            log_status(f"Trying netrc file: {path}", LEVEL_INFO)
            auth = netrc.netrc(path)
            login, _, password = auth.authenticators(NETRC_HOST)  # type: ignore[arg-type]
            if not login or not password:
                raise ValueError("Missing login or password in netrc entry")

            # Convention: login = apiKey, password = apiToken
            return AuthInfo(api_key=login, api_token=password)
        except (OSError, netrc.NetrcParseError, ValueError) as exc:
            log_status(f"Failed to read netrc {path}: {exc}", LEVEL_WARN)

    raise RuntimeError("No valid SORACOM credentials found in netrc files")


def authenticate(auth: AuthInfo) -> dict:
    """
    Build an authentication token dict from AuthInfo.

    For Harvest Files, the API key and token are usually passed directly
    as headers, so this function simply wraps them in a dict.
    """
    token = {
        "apiKey": auth.api_key,
        "token": auth.api_token,
    }
    log_status("Authentication info prepared", LEVEL_INFO)
    return token


def _auth_headers(token: dict) -> dict[str, str]:
    """Build HTTP headers for SORACOM API calls."""
    api_key = token.get("apiKey") or token.get("api_key")
    api_token = token.get("token") or token.get("api_token")

    if not api_key or not api_token:
        raise ValueError("Token dict must contain 'apiKey' and 'token'")

    return {
        "X-Soracom-API-Key": str(api_key),
        "X-Soracom-Token": str(api_token),
    }


# ---------------------------------------------
# HTTP helpers
# ---------------------------------------------

def _safe_request(method: str, url: str, **kwargs) -> requests.Response | None:
    """
    Unified HTTP request handler with logging and basic error handling.

    Returns:
        Response object on success (status < 400), or None on error.
    """
    try:
        res = requests.request(method, url, **kwargs)
        if res.status_code >= 400:
            snippet = res.text[:200].replace("\n", " ")
            log_status(
                f"{method} {url} -> {res.status_code} {snippet}",
                LEVEL_ERROR,
            )
            return None
        return res
    except requests.exceptions.RequestException as exc:
        log_status(f"{method} {url} failed: {exc}", LEVEL_ERROR)
        return None


def get_with_auth(url: str, token: dict) -> requests.Response | None:
    """GET wrapper with authentication headers."""
    return _safe_request("GET", url, headers=_auth_headers(token))


def delete_with_auth(url: str, token: dict) -> requests.Response | None:
    """DELETE wrapper with authentication headers."""
    return _safe_request("DELETE", url, headers=_auth_headers(token))


# ---------------------------------------------
# Harvest Files listing
# ---------------------------------------------

def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def list_files_iterative(
    base_path: str,
    token: dict,
    limit: int | None = None,
    page_size: int = 100,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[str]:
    """
    List files under base_path using an iterative (non-recursive) traversal.

    Args:
        base_path: Root path in Harvest Files (e.g. "device-id/").
        token: Authentication token dict.
        limit: Maximum number of files to return (None for unlimited).
        page_size: Number of entries per API call.
        start_time: Only include files modified at or after this time.
        end_time: Only include files modified at or before this time.

    Returns:
        List of file paths (strings).
    """
    results: list[str] = []
    stack: list[tuple[str, str | None]] = [(base_path, None)]

    start_time = _normalize_dt(start_time)
    end_time = _normalize_dt(end_time)

    while stack:
        path, last_key = stack.pop()

        params: dict[str, str | int] = {"limit": page_size}
        if last_key:
            params["last_evaluated_key"] = last_key

        encoded_path = urllib.parse.quote(path, safe="/")
        url = f"{API_BASE}/files/private/{encoded_path}"

        res = _safe_request("GET", url, headers=_auth_headers(token), params=params)
        if res is None:
            continue

        try:
            entries: Iterable[dict] = res.json()
        except json.JSONDecodeError as exc:
            log_status(f"Invalid JSON from {url}: {exc}", LEVEL_ERROR)
            continue

        for entry in entries:
            filename = entry.get("filename", "")
            last_modified_ms = entry.get("lastModifiedTime")

            # Directory entry
            if not filename or filename.endswith("/"):
                if not filename:
                    # Some APIs may return an empty entry for the directory itself
                    continue
                sub_path = path.rstrip("/") + "/" + filename.rstrip("/") + "/"
                stack.append((sub_path, None))
                continue

            # Time filter
            if last_modified_ms is not None:
                ts = datetime.fromtimestamp(last_modified_ms / 1000, tz=timezone.utc)
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue

            full_path = path.rstrip("/") + "/" + filename
            results.append(full_path)

            if limit is not None and len(results) >= limit:
                return results[:limit]

        # Pagination
        next_key = res.headers.get("X-Soracom-Next-Key")
        if next_key:
            stack.append((path, next_key))

    return results


# ---------------------------------------------
# Download helpers
# ---------------------------------------------

def _iter_content(res: requests.Response, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    for chunk in res.iter_content(chunk_size=chunk_size):
        if chunk:
            yield chunk


def download_and_save(
    remote_path: str,
    local_path: str,
    token: dict,
    overwrite: bool = False,
    chunk_size: int = 1024 * 1024,
) -> bool:
    """
    Download a file from Harvest Files and save it locally.

    Args:
        remote_path: Path in Harvest Files (e.g. "device-id/file.txt").
        local_path: Destination path on local filesystem.
        token: Authentication token dict.
        overwrite: If False and file exists, download is skipped.
        chunk_size: Streaming chunk size in bytes.

    Returns:
        True on success, False on failure.
    """
    if os.path.exists(local_path) and not overwrite:
        log_status(f"File already exists, skipping: {local_path}", LEVEL_WARN)
        return True

    encoded_path = urllib.parse.quote(remote_path, safe="/")
    url = f"{API_BASE}/files/private/{encoded_path}"

    res = _safe_request(
        "GET",
        url,
        headers=_auth_headers(token),
        stream=True,
    )
    if res is None:
        return False

    dest_dir = os.path.dirname(local_path) or "."
    try:
        os.makedirs(dest_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dest_dir)
        try:
            with os.fdopen(fd, "wb") as f:
                for chunk in _iter_content(res, chunk_size=chunk_size):
                    f.write(chunk)
            shutil.move(tmp_path, local_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        log_status(f"Downloaded: {remote_path} -> {local_path}", LEVEL_INFO)
        return True
    except OSError as exc:
        log_status(f"Failed to save {local_path}: {exc}", LEVEL_ERROR)
        return False


# ---------------------------------------------
# Upload helpers
# ---------------------------------------------

def upload_file_to_soracom(
    file_path: str,
    upload_path: str,
    token: dict,
) -> bool:
    """
    Upload a local file to SORACOM Harvest Files.

    Args:
        file_path: Local file path.
        upload_path: Destination path in Harvest Files.
        token: Authentication token dict.

    Returns:
        True on success (HTTP 200/204), False otherwise.
    """
    url = f"{API_BASE}/files/private/{urllib.parse.quote(upload_path, safe='/')}"
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    headers = {
        **_auth_headers(token),
        "Content-Type": content_type,
    }

    try:
        with open(file_path, "rb") as f:
            res = _safe_request("PUT", url, headers=headers, data=f)
            if res and res.status_code in (200, 204):
                log_status(f"Upload OK: {file_path} -> {upload_path}", LEVEL_INFO)
                return True
            return False
    except OSError as exc:
        log_status(f"Upload failed (cannot read file): {file_path} -> {exc}", LEVEL_ERROR)
        return False


# ---------------------------------------------
# Misc helpers
# ---------------------------------------------

def is_recent(
    last_modified_ms: int,
    within_seconds: int,
    now: datetime | None = None,
) -> bool:
    """
    Check if a timestamp (milliseconds since epoch) is within given seconds from now.

    Args:
        last_modified_ms: Milliseconds since epoch.
        within_seconds: Threshold in seconds.
        now: Optional reference time (UTC). If None, current UTC time is used.

    Returns:
        True if within the threshold, False otherwise.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    ts = datetime.fromtimestamp(last_modified_ms / 1000, tz=timezone.utc)
    delta = now - ts
    return 0 <= delta.total_seconds() <= within_seconds
