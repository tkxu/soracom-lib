# soracom_lib

A lightweight Python client library for [SORACOM Harvest Files](https://developers.soracom.io/en/docs/harvest/).

Provides authentication, recursive file listing, download, upload, and related helpers.  
All functionality lives in `soracom_harvest_files.py`; `soracom_lib.py` re-exports everything for a clean top-level import.

No dependencies beyond the standard library and `requests`.

---

## Features

- Credential loading from `_netrc` / `.netrc` (no credentials in source code)
- Session-token authentication via SORACOM SAM user
- Recursive directory listing with optional time-range filter and pagination
- Resumable bulk download with per-IMSI subdirectory layout and size limit
- File upload with automatic `Content-Type` detection
- Recency helper for filtering by last-modified time

---

## Requirements

| | |
|---|---|
| Python | 3.11 + |
| [requests](https://pypi.org/project/requests/) | any recent version |

---

## Installation

No package installation is needed. Copy the two files into your project:

```
your_project/
├── soracom_lib.py
└── soracom_harvest_files.py
```

Install the only external dependency:

```bash
pip install requests
```

---

## Credentials setup

`soracom_lib` never reads credentials from source code or environment variables.  
It uses the standard `netrc` mechanism so secrets stay out of your repository.

### 1. Create a SORACOM SAM user

Generate an **Auth Key** in the [SORACOM User Console](https://console.soracom.io/) under **Security → SAM Users**.

### 2. Write the netrc file

**Windows** — create `%USERPROFILE%\_netrc`:

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
_netrc
.netrc
```

---

## Quick start

```python
import soracom_lib as sl

# Load credentials and authenticate
auth_id, auth_key = sl.read_auth_keys()
token = sl.authenticate(auth_id, auth_key)

# List all files under a path
files = sl.list_files_recursive("logs/44010XXXXXXXXXXX/", token)
print(files)

# Download files
sl.download_and_save(
    file_names=files,
    save_dir="./download",
    imsi="44010XXXXXXXXXXX",
    limit_size_to_files=200 * 1024 * 1024,  # 200 MB
    delete_after_download=False,
    token=token,
)

# Upload a file
sl.upload_file_to_soracom(
    file_path="./results/output.pos",
    upload_path="logs/44010XXXXXXXXXXX/pos/output.pos",
    token=token,
)
```

---

## API reference

### `read_auth_keys(base_dir=None) -> tuple[str | None, str | None]`

Load `authKeyId` and `authKey` from `_netrc` or `.netrc`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `base_dir` | `str \| None` | When provided, also searches for netrc files in this directory (takes priority over the home directory). |

Returns `(auth_key_id, auth_key)` on success, `(None, None)` on failure.

---

### `authenticate(auth_key_id, auth_key) -> dict`

Authenticate with the SORACOM API and return a session token.

Raises `RuntimeError` if authentication fails (non-200 response or network error).

The returned `dict` contains `apiKey` and `token` and must be passed to every subsequent call.

---

### `list_files_recursive(base_path, token, *, limit_num_to_list=None, limit_num_to_list_per_req=10, last_key=None, start_time=None, end_time=None) -> list[str]`

Recursively list all files under `base_path` in Harvest Files.

| Parameter | Type | Description |
|-----------|------|-------------|
| `base_path` | `str` | Root path in Harvest Files, e.g. `"logs/44010.../"` |
| `token` | `dict` | Session token from `authenticate()` |
| `limit_num_to_list` | `int \| None` | Cap on total results; `None` = no limit |
| `limit_num_to_list_per_req` | `int` | Page size for each API request (default `10`) |
| `last_key` | `str \| None` | Pagination cursor to resume a previous call |
| `start_time` | `datetime \| None` | Exclude files modified before this time. Naive datetimes are treated as UTC. |
| `end_time` | `datetime \| None` | Exclude files modified after this time. Naive datetimes are treated as UTC. |

Returns a list of full file path strings.

---

### `download_and_save(file_names, save_dir, imsi, limit_size_to_files, delete_after_download, token) -> None`

Download a list of Harvest Files paths to local disk.

Files are saved under `<save_dir>/<imsi>/`.  
Files that already exist on disk are skipped automatically.  
Downloads stop once cumulative bytes reach `limit_size_to_files`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_names` | `list[str]` | Remote file paths (output of `list_files_recursive`) |
| `save_dir` | `str` | Local root directory |
| `imsi` | `str` | Used as the subdirectory name under `save_dir` |
| `limit_size_to_files` | `int` | Maximum cumulative download size in bytes |
| `delete_after_download` | `bool` | Delete each file from Harvest Files after saving |
| `token` | `dict` | Session token from `authenticate()` |

---

### `upload_file_to_soracom(file_path, upload_path, token) -> bool`

Upload a local file to Harvest Files via HTTP PUT.  
`Content-Type` is detected automatically from the file extension; falls back to `application/octet-stream`.

Returns `True` on success, `False` on failure.

---

### `get_with_auth(url, token) -> requests.Response | None`

Authenticated GET. Returns the response object, or `None` on non-200.

---

### `delete_with_auth(url, token) -> requests.Response`

Authenticated DELETE. Returns the raw response (status check is the caller's responsibility).

---

### `is_recent(last_modified_ms, days) -> bool`

Return `True` if `last_modified_ms` (milliseconds since epoch, as returned by the Harvest Files API) falls within the past `days` days.

```python
if sl.is_recent(entry["lastModifiedTime"], days=7):
    print("Modified within the last week")
```

---

## Directory layout (download)

```
save_dir/
└── <imsi>/
    ├── <imsi>_2025-08-20-00_1724112000.log
    ├── <imsi>_2025-08-20-01_1724115600.log
    └── ...
```

---

## Logging

`soracom_harvest_files` uses Python's standard `logging` module under the logger name `soracom_harvest_files`.  
By default a `StreamHandler` is attached so messages appear on stderr.  
To suppress output or integrate with your own logging config:

```python
import logging

# Suppress all output from this library
logging.getLogger("soracom_harvest_files").setLevel(logging.CRITICAL)

# Or hand off to your application's root logger (remove the default handler)
logging.getLogger("soracom_harvest_files").handlers.clear()
logging.getLogger("soracom_harvest_files").propagate = True
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
