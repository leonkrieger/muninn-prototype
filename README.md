# muninn-prototype
A Python software prototype for the Delta Suit Spacesuit Simulator of the Austrian Space Forum (ÖWF)

## Installation
To install and run the software:

In `raspi-config`, enable I2C under Interface Options, then reboot.

Then from the project folder:

```bash
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/muninn
```

## ZeroMQ collector

Run the developer collector on a PC that can reach the suit's publisher. It is
kept in the repository's top-level `tools` directory and is not part of the
Muninn runtime deployed to the Pi:

```bash
python -m pip install .
python tools/zeromq_collector.py --endpoint tcp://192.168.178.125:5555 --output ./collected-data
```

Telemetry is appended to `telemetry.jsonl`; image messages are written under
`images/YYYY-MM-DD`. By default all topic prefixes are collected. Use
`--subscribe delta-01/readings` (repeatable) to limit subscriptions. The
collector accepts raw JPEG/PNG/WebP/GIF payloads and JSON image envelopes with
an `image` or `data` base64 field.

## License & Usage
This repository is strictly for internal sharing and development.
- No license is currently assigned to this project
- Usage and distribution are not permitted
- This code is for internal use only
