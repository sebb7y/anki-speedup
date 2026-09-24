# Anki Speedup

## Warning: WIP & Still very buggy


A modern reimplementation of [Speed Focus Mode](https://github.com/glutanimate/speed-focus-mode)
for current Anki versions (built against Anki 26.09).

Speedup keeps you moving by running granular, per-card timers during review:

- Play an alert sound after a configurable, **fractional** number of seconds.
- Automatically reveal the answer.
- Automatically rate/bury the card.
- Show a live countdown with a "More time" button/hotkey.
- Use **different timings for new, learning, review and relearning** cards
  (optionally collapsed into two classes).
- Display average time per card, deck totals and overall totals.
- Opt-in per-card front/back analytics, slow/fast marking, adaptive speed-up and
  distribution charts.

## Settings

- **Global settings**: click the add-on's *Config* button (or Tools → Add-ons →
  Speedup → Config). Documented in [`src/speedup/config.md`](src/speedup/config.md).
- **Per-deck settings**: open a deck's options screen; Speedup adds its own
  section. Per-deck values override the global defaults and are stored with the
  deck's config preset.

## Development

Requires Anki 24.04+ and Python 3.9+ for tooling.

```sh
make link     # symlink src/speedup into Anki's addons21 folder
make test     # run unit tests
make build    # produce dist/speedup.ankiaddon
make lint     # ruff (+ mypy)
```

Restart Anki after `make link`. Use `make unlink` to remove the symlink.

The pure logic (settings merging, card classification, recommendations) lives in
`settings_schema.py` and is unit tested without Anki.

## License

AGPL-3.0-or-later. Derived from Speed Focus Mode, Copyright (C) 2017-2022
Aristotelis P. (Glutanimate). See [LICENSE](LICENSE).
