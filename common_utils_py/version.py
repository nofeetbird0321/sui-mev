# coding: utf-8
# Copyright (c) Mysten Labs, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Version information for the build."""

import subprocess
import shlex

_STATIC_VERSION = "unknown-dev-version"

def get_build_version() -> str:
    """
    Retrieves the build version dynamically from git describe.

    Falls back to a static version if git command fails.
    """
    try:
        command = "git describe --tags --dirty --always"
        # Use shlex.split to handle command arguments properly,
        # though for this specific command it's simple.
        process = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            check=True  # Raises CalledProcessError for non-zero exit codes
        )
        return process.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # CalledProcessError for git command errors (e.g., not a git repo)
        # FileNotFoundError if git is not installed
        return _STATIC_VERSION

if __name__ == "__main__":
    # Example usage
    print(get_build_version())
