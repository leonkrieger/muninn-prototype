#!/bin/bash

# Create virtual enviroment
python3 -m venv .venv

# Activate venv
source .venv/bin/activate

:: Install requirements
python3 -m pip install .

echo "Virtual Enviroment setup completed"