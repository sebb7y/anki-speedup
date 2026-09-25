# Speedup global configuration

Speedup has two layers of settings:

- **Global settings** (this file / the dialog opened from the add-on's *Config*
  button): behaviour and the default timings for each card class.
- **Per-deck settings**: overrides that live inside Anki's deck options screen
  (see the "Speedup" section there). These are stored per deck-config preset.

Timings are in seconds and may be fractional, e.g. `2.7`.

### `enabled`

(true/false): Master switch for Speedup's timers. Default: `true`.

### `moreTime.showButton`

(true/false): Show the "More time" button and countdown in the reviewer.
Default: `false`.

### `moreTime.hotkey`

(text): Hotkey that cancels the current timers. Default: `p`.

### `stopTimersWhenTyping`

(true/false): Stop active timers when you start typing an answer. Default:
`true`.

### `suppressBuiltInAutoAdvance`

(true/false): Disable Anki's built-in Auto Advance while Speedup timers are
active for the current card, to avoid two systems firing at once. Default:
`true`.

### `alertSound`

(text): `default` uses the bundled sound. Any other value is treated as a
filename inside the add-on's `user_files` folder. Default: `default`.

### `grouping`

- `collapseNewLearning` (true/false): use the **New** settings for learning
  cards too.
- `collapseReviewRelearning` (true/false): use the **Review** settings for
  relearning cards too.

### `defaults`

Per card class (`new`, `learning`, `review`, `relearning`). Each class has a
`question` and an `answer` phase:

- `question.alertAfter`: play the alert sound after this many seconds.
- `question.revealAfter`: reveal the answer after this many seconds.
- `question.autoAction`: `{ after, action, skipAnswer }` — automatically perform
  `action` (`again`/`hard`/`good`/`easy`/`bury`) after `after` seconds. When
  `skipAnswer` is true the countdown starts on the question side.
- `answer.alertAfter`: play the alert sound after the answer is shown.
- `answer.autoAction`: `{ after, action }` — automatically perform `action`
  after `after` seconds on the answer side.

A value of `0` disables that timer.

### `ui`

- `showCountdown`, `showAverage`, `showDeckTotal`, `showOverallTotal`
  (true/false): which values to display in the reviewer overlay.
- `totalPeriod`: `today` or `all` — applies to the deck/overall totals.
- `averagePeriod`: `today` or `all` — applies to the average time per card.
  `today` matches Anki's "studied today" figure (scoped to the deck you are
  reviewing).
- `overlayPosition`: where the reviewer overlay is anchored —
  `top-right`, `top-left`, `bottom-right` or `bottom-left`.
- `overlayFontSize`: overlay text size in pixels (8–48).

### `analytics`

- `enabled` (true/false): opt in to recording per-card front/back times in a
  local database (`user_files/speedup.db`). This data is not synced.
- `markSlowFast` (true/false): highlight slow/fast cards in the reviewer.
- `slowPercentile` / `fastPercentile`: thresholds for slow/fast classification.

### `adaptive`

- `enabled` (true/false): gradually tighten timers based on your recent
  averages.
- `factor`: multiplier applied to your recent averages (e.g. `0.97`).
- `windowDays`: rolling window used to compute averages.
- `floor`: minimum time (seconds) that adaptive timers will not go below.
