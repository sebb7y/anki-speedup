# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Add-on-wide constants and paths."""

from __future__ import annotations

import os

from aqt import mw

MODULE_ADDON = __name__.split(".")[0]

DIRECTORY_ADDONS = mw.addonManager.addonsFolder()
PATH_ADDON = os.path.join(DIRECTORY_ADDONS, MODULE_ADDON)
PATH_USERFILES = os.path.join(PATH_ADDON, "user_files")
PATH_SOUNDS = os.path.join(PATH_ADDON, "sounds")
PATH_WEB = os.path.join(PATH_ADDON, "web")

DEFAULT_ALERT_NAME = "alert.mp3"

PYCMD_IDENTIFIER = "speedup"
BRIDGE_PREFIX = f"{PYCMD_IDENTIFIER}:"

CONFIG_NAMESPACE = "speedup"
