#!/bin/bash
set -e

# Picamera2 and libcamera are supplied by Raspberry Pi OS.  Allow the venv
# to see those system Python bindings (notably the `libcamera` module).
python3 -m venv .venv --clear --system-site-packages

# Install requirements
.venv/bin/pip install .

echo "Muninn setup completed!"
