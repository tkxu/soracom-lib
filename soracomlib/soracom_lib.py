#!/usr/bin/env python3
"""
soracom-lib — top-level wrapper package.


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
    Rev. 0.91  2026-06-14  Add FileEntry, resolve_entry_timestamp
"""

from __future__ import annotations

from soracom_harvest_files import (
    API_BASE,
    NETRC_HOST,
    NETRC_PATHS,
    LEVEL_INFO,
    LEVEL_WARN,
    LEVEL_ERROR,
    AuthInfo,
    FileEntry,
    read_auth_keys,
    authenticate,
    get_with_auth,
    delete_with_auth,
    list_files_iterative,
    download_and_save,
    upload_file_to_soracom,
    is_recent,
    resolve_entry_timestamp,
)

__all__ = [
    "API_BASE",
    "NETRC_HOST",
    "NETRC_PATHS",
    "LEVEL_INFO",
    "LEVEL_WARN",
    "LEVEL_ERROR",
    "AuthInfo",
    "FileEntry",
    "read_auth_keys",
    "authenticate",
    "get_with_auth",
    "delete_with_auth",
    "list_files_iterative",
    "download_and_save",
    "upload_file_to_soracom",
    "is_recent",
    "resolve_entry_timestamp",
]
