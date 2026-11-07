# Changelog

## Unreleased

Added
- Planning tools: `profile_set`, `profile_get`, `exercise_search`, `plan_generate`, `plan_get_today`, `plan_adjust` and `plan_review_progress`. Plans are rule-based and local, with a small built-in exercise library. 36 tools in total.
- Cardio and mobility sessions can appear in a plan but are not loggable with `training_log_set`, so they are left out of progress counts.

Changed
- The package description, README opening and server instructions now describe the plan generator as well as the log and calculators.

## 1.2.0

Fixed
- A clean install no longer crashes on startup. `mcp` is pinned below 2, and the server passes `instructions` to FastMCP.
- DOTS for women used a wrong coefficient. The Wilks tool is labelled as the original 1994 formula, and an unknown sex is now an error instead of being scored as female.
- The readiness score gave 7 hours of sleep only partial credit. Full credit now starts at 7 hours.
- The weekly nutrition average no longer counts days with no logged food as zero.
- The overreaching check no longer compares against the unfinished current week.
- Empty-database results are labelled `sample_data: true`, and the correlation tool reports `insufficient_data` instead of inventing a pattern.
- Bad input such as negative weights, zero reps or RPE above 10 returns a clear error.
- The source package no longer includes local virtual environments, and the repo has a LICENSE file.

Added
- `nutrition_estimate_targets` (Mifflin-St Jeor with evidence-based protein and a safe calorie floor) and `training_estimate_1rm_from_rpe`. Brzycki joins Epley in `training_calculate_1rm`. 29 tools in total.
- `ROBO_TRAINER_HOME` moves the data folder.
- A website with in-browser calculators, tested in Chromium, Firefox and WebKit.
- CI that starts the real server from a built wheel and from the Docker image, a single `CI gate` check, an `:edge` image on every merge to `main`, and tagged releases with provenance.

Changed
- A tool module that fails to load now stops startup instead of being skipped.
- The Docker image runs as a non-root user and keeps data in `/data`.

## 1.1.0

First release.
