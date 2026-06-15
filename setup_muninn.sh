#!/bin/bash
set -e

# Create virtual enviroment
python3 -m venv .venv --clear

# Install requirements
.venv/bin/pip install .

echo "Muninn setup completed!"