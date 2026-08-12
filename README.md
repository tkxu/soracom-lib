# soracom-lib

A lightweight Python client library for [SORACOM Harvest Files](https://developers.soracom.io/en/docs/harvest/).

Provides authentication, iterative file listing, download, upload, and related helpers.  
Core implementation lives in `soracomlib/soracom_harvest_files.py`; the top-level `soracomlib` package re-exports everything, so you only need `import soracomlib`.

No dependencies beyond the standard library and `requests`.

---

## Features

- Credential loading from `.netrc` (no credentials in source code)
- Authentication via SORACOM SAM user — calls `POST /auth` and returns a reusable token dict
- Iterative directory traversal with optional time-range filter and pagination
- Per-file download with skip-existing and overwrite options
- File upload with automatic `Content-Type` detection
- Recency helper for filtering by last-modified time

---

## Requirements

| | |
|---|---|
| Python | 3.8 + |
| [requests](https://pypi.org/project/requests/) | >= 2.28 |

---

## Installation

Install from PyPI:

```bash
pip install soracom-lib
```

---

## Credentials setup

`soracomlib` never reads credentials from source code or environment variables.  
It uses the standard `netrc` mechanism so secrets stay out of your repository.

### 1. Create a SORACOM SAM user

Generate an **Auth Key** in the [SORACOM User Console](https://console.soracom.io/) under **Security → SAM Users**.

### 2. Write the netrc file

**Windows** — create `%USERPROFILE%\.netrc`:

```
machine api.soracom.io
login   keyId-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
password secret-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Linux / macOS** — create `~/.netrc` and restrict permissions:

```bash
cat >> ~/.netrc << 'EOF'
machine api.soracom.io
login   keyId-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
password secret-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
EOF
chmod 600 ~/.netrc
```

### 3. Add netrc to .gitignore

```
.netrc
```

---

## Quick start

```python
import soracomlib as sl

# Load credentials (returns AuthInfo; raises RuntimeError on failure)
auth_info = sl.read_auth_keys()

# Call POST /auth and get a session token dict
token = sl.authenticate(auth_info)

# List all files under a path (returns list[FileEntry])
files = sl.list_files_iterative("logs/XXXXXXXXXXXXXXXXX/", token)
print([e.path for e in files])

# Download each file individually
import os
for entry in files:
    local_path = os.path.join("./download", os.path.basename(entry.path))
    sl.download_and_save(entry.path, local_path, token)

# Upload a file
sl.upload_file_to_soracom(
    file_path="./results/output.log",
    upload_path="logs/XXXXXXXXXXXXXXXX/output.log",
    token=token,
)
```

---

## API reference

### Constants

| Name | Value | Description |
|------|-------|--------------|
| `API_BASE` | `"https://api.soracom.io/v1"` | Base URL for all API calls |
| `NETRC_HOST` | `"api.soracom.io"` | `machine` name looked up in `.netrc` |
| `NETRC_PATHS` | `(os.path.expanduser("~/.netrc"),)` | Default netrc search paths |
| `LEVEL_INFO` / `LEVEL_WARN` / `LEVEL_ERROR` | `"INFO"` / `"WARN"` / `"ERROR"` | Log level constants used internally by `log_status()`; can also be passed directly when calling it |

---

### `read_auth_keys(base_dir=None) -> AuthInfo`

Load credentials from `.netrc` and return an `AuthInfo` object.

| Parameter | Type | Description |
|-----------|------|-------------|
| `base_dir` | `str \| None` | When provided, also searches for `.netrc` in this directory (takes priority over the home directory). |

Raises `RuntimeError` if no valid credentials are found.

---

### `AuthInfo`

Frozen dataclass holding the loaded credentials.

```python
@dataclass(frozen=True)
class AuthInfo:
    api_key: str    # authKeyId from netrc login field
    api_token: str  # authKey from netrc password field
```

---

### `authenticate(auth: AuthInfo) -> dict`

Call `POST /auth` with the credentials in `auth` and return the session token dict issued by the server.

```python
token = sl.authenticate(auth_info)
# → {"apiKey": "...", "token": "..."}
```

Raises `RuntimeError` if the request fails or the server returns a non-200 status.

---

### `list_files_iterative(base_path, token, limit=None, page_size=100, start_time=None, end_time=None) -> list[FileEntry]`

Iteratively traverse directories and list all files under `base_path` in Harvest Files.

| Parameter | Type | Description |
|-----------|------|-------------|
| `base_path` | `str` | Root path in Harvest Files, e.g. `"logs/XXXXX.../"` |
| `token` | `dict` | Token dict from `authenticate()` |
| `limit` | `int \| None` | Cap on total results; `None` = no limit |
| `page_size` | `int` | Number of entries per API request (default `100`, max `100`) |
| `start_time` | `datetime \| None` | Exclude files modified before this time. Naive datetimes are treated as UTC. |
| `end_time` | `datetime \| None` | Exclude files modified after this time. Naive datetimes are treated as UTC. |

Returns a list of `FileEntry` objects. Each entry has a `path` attribute (full remote path string) and a `last_modified` attribute (UTC-aware `datetime`, or `None` when absent from the API response).

---

### `download_and_save(remote_path, local_path, token, overwrite=False, chunk_size=1048576) -> bool`

Download a single file from Harvest Files and save it to the local filesystem.

| Parameter | Type | Description |
|-----------|------|-------------|
| `remote_path` | `str` | File path in Harvest Files (e.g. `"logs/XXXXX.../file.log"`) |
| `local_path` | `str` | Destination path on local filesystem |
| `token` | `dict` | Token dict from `authenticate()` |
| `overwrite` | `bool` | If `False` (default) and the local file already exists, the download is skipped and `True` is returned |
| `chunk_size` | `int` | Streaming chunk size in bytes (default 1 MiB) |

Returns `True` on success (including skip), `False` on failure.  
Parent directories are created automatically.

---

### `upload_file_to_soracom(file_path, upload_path, token) -> bool`

Upload a local file to Harvest Files via HTTP PUT.  
`Content-Type` is detected automatically from the file extension; falls back to `application/octet-stream`.

Returns `True` on success (HTTP 200 or 204), `False` on failure.

---

### `get_with_auth(url, token) -> requests.Response | None`

Authenticated GET. Returns the response object on success (status < 400), or `None` on error.

---

### `delete_with_auth(url, token) -> requests.Response | None`

Authenticated DELETE. Returns the response object on success (status < 400), or `None` on error.

---

### `is_recent(last_modified_ms, within_seconds, now=None) -> bool`

Return `True` if `last_modified_ms` (milliseconds since epoch, as returned by the Harvest Files API) falls within the past `within_seconds` seconds.

| Parameter | Type | Description |
|-----------|------|-------------|
| `last_modified_ms` | `int` | Milliseconds since epoch |
| `within_seconds` | `int` | Threshold in seconds |
| `now` | `datetime \| None` | Reference time (UTC). Defaults to `datetime.now(timezone.utc)` |

```python
if sl.is_recent(entry["lastModifiedTime"], within_seconds=7 * 86_400):
    print("Modified within the last week")
```

---

### `resolve_entry_timestamp(entry: FileEntry, tz=timezone.utc) -> datetime | None`

Resolve the best available timestamp for a `FileEntry`. Currently returns `entry.last_modified` converted to `tz`, or `None` if it is absent.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entry` | `FileEntry` | An entry returned by `list_files_iterative()` |
| `tz` | `timezone` | Timezone for the returned datetime (default: UTC) |

---

## Bulk download pattern

`download_and_save()` operates on one file at a time, giving you full control over size limits, delete-after-download, and error handling per file.

```python
import os
import soracomlib as sl

auth_info = sl.read_auth_keys()
token = sl.authenticate(auth_info)

files = sl.list_files_iterative("logs/XXXXXXXXXXXXXXXX/", token)
save_dir = "./download/XXXXXXXXXXXXXXXX"
os.makedirs(save_dir, exist_ok=True)

LIMIT_BYTES = 200 * 1024 * 1024  # 200 MB
downloaded_bytes = 0

for entry in sorted(files, key=lambda e: e.path):
    if downloaded_bytes >= LIMIT_BYTES:
        break

    local_path = os.path.join(save_dir, os.path.basename(entry.path))
    ok = sl.download_and_save(entry.path, local_path, token)

    if ok:
        downloaded_bytes += os.path.getsize(local_path)
        # Optionally delete from Harvest Files after download:
        # sl.delete_with_auth(f"{sl.API_BASE}/files/private/{entry.path}", token)
```

---

## Logging

The library uses Python's standard `logging` module under the logger name `soracomlib.soracom_harvest_files`.  
By default a `NullHandler` is attached, so no output appears unless your application configures logging.  
To integrate with your own logging config:

```python
import logging

# Show INFO and above from this library on stderr
logging.basicConfig(level=logging.INFO)
logging.getLogger("soracomlib.soracom_harvest_files").propagate = True

# Or suppress all output from this library
logging.getLogger("soracomlib.soracom_harvest_files").setLevel(logging.CRITICAL)
```

---

## License

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
