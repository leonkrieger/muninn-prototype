# muninn-prototype
A Python software prototype for the Delta Suit Spacesuit Simulator of the Austrian Space Forum (ÖWF)

# Installation
## Pin configuration
Connect the button between physical pin 36 (BCM GPIO 16) and physical pin 34
(ground). Pressing it clears the four-character display.

The push-to-talk button is connected between physical pin 37 (BCM GPIO 26)
and physical pin 39 (ground). This must match the `txptt` setting in
[config/talkkonnect-delta.xml.example](config/talkkonnect-delta.xml.example).

## I2C Configuration
To install and run the software:

In `raspi-config`, enable I2C under Interface Options, then reboot.

Then from the project folder:

```bash
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/muninn
```

## Installing Talkkonnect

Muninn uses [Talkkonnect](https://www.talkkonnect.com/) for communication.
It needs to be installed separately. 
The default Muninn configuration expects:

```text
executable at /opt/talkkonnect/dist/talkkonnect
the configuration to be at /home/admin/.config/talkkonnect-delta.xml
```

Change `[communications]` in `config/defaults.toml` if the executable or XML
file is elsewhere. Set the PC's LAN address, Mumble port (normally 64738),
username, password/certificate, channel, and audio device settings in the
Talkkonnect XML file. Permit the Mumble TCP and UDP port through the PC
firewall and verify the Pi can reach the PC before starting Muninn.

The repository includes [config/talkkonnect-delta.xml.example](config/talkkonnect-delta.xml.example).
Fill out and adjust according to setup.

# ZeroMQ collector

To test connection, you can run the developer collector on a PC that can reach the suit's publisher. 
It is kept in the repository's top-level `tools` directory and is not part of the
Muninn runtime deployed to the Pi:

```bash
python -m pip install .
python tools/zeromq_collector.py --endpoint tcp://IP:PORT --output ./collected-data
```
Telemetry is appended to `telemetry.jsonl`; image messages are written under
`images/YYYY-MM-DD`. By default all topic prefixes are collected. Use
`--subscribe delta-01/readings` (repeatable) to limit subscriptions. The
collector accepts raw JPEG/PNG/WebP/GIF payloads and JSON image envelopes with
an `image` or `data` base64 field.

# License & Usage
This repository is strictly for internal sharing and development.
- No license is currently assigned to this project
- Usage and distribution are not permitted
- This code is for internal use only
