# Anki Speedup

[![Status](https://img.shields.io/badge/status-WIP-yellow?style=flat-square)](#status)
[![AI](https://img.shields.io/badge/AI-assisted-red?style=flat-square)](#development)
[![Quality gate](https://img.shields.io/sonar/quality_gate/sebb7y_anki-speedup?server=https%3A%2F%2Fsonarcloud.io&style=flat-square)](https://sonarcloud.io/project/overview?id=sebb7y_anki-speedup)

A modern reimplementation of [Speed Focus Mode](https://github.com/glutanimate/speed-focus-mode)
for current Anki versions (built against Anki 26.09).

Speedup keeps you moving by running granular, per-card timers during review,
with optional local analytics for timing recommendations.

## Status

WIP and still buggy. The timer engine, per-class timings, countdown and
more-time controls are the stable core. Analytics, slow/fast badges,
recommendations and adaptive speed-up are newer and should be treated as
experimental.

Known limitations:

- Analytics only covers reviews recorded after it is enabled.
- Per-deck overrides live inside Anki's deck-config presets, so they follow the
  deck rather than the add-on config.
- The statistics dialog needs local analytics data for the per-card charts;
  the deck/overall totals still come from Anki's revlog.

## Features

- Per-card question timers: alert, reveal and auto-rate/bury.
- Answer-side timers: alert and auto-rate.
- Four settings classes: new, learning, review and relearning, with optional
  collapsing into New/Review.
- Movable countdown overlay with a clickable stop control; drag the ⠿ handle
  to place it anywhere, and the position is remembered.
- Optional "More time" button and a configurable reviewer hotkey.
- Stop timers while typing a type-in answer.
- Suppress Anki's built-in Auto Advance while Speedup timers are active.
- Per-deck overrides in the deck options screen.
- Local, opt-in analytics with slow/fast marking, a statistics dialog and
  timing recommendations.

## Settings

- **Global settings**: click the add-on's *Config* button, or open
  **Tools → Speedup → Options…**. Documented in
  [`src/speedup/config.md`](src/speedup/config.md).
- **Per-deck settings**: open a deck's options screen; Speedup adds its own
  section. Per-deck values override the global defaults and are stored with the
  deck's config preset.
- **Statistics**: **Tools → Speedup → Statistics…**, or the deck browser's
  right-click menu. If analytics is off, the dialog offers a one-click way to
  enable it.

## Development

Requires Anki 24.04+ and Python 3.9+ for tooling.

```sh
make link     # symlink src/speedup into Anki's addons21 folder
make test     # run unit tests
make build    # produce dist/speedup.ankiaddon
make lint     # ruff (+ mypy)
```

Restart Anki after `make link`. Use `make unlink` to remove the symlink.

The pure logic (settings normalization/merging, card classification,
recommendations) lives in `settings_schema.py` and is unit tested without Anki.

## License

AGPL-3.0-or-later. Derived from Speed Focus Mode, Copyright (C) 2017-2022
Aristotelis P. (Glutanimate). See [LICENSE](LICENSE).
