# robo-trainer-mcp

An MCP server that turns Claude into a full-stack personal trainer: nutrition coaching, strength programming, powerlifting analytics, strongman event tracking, recovery monitoring, and mental performance analysis, all from a single privacy-first local server.

## The Problem It Solves

Every fitness app works in isolation. Your food tracker knows your macros. Your training log knows your lifts. Your sleep tracker knows your HRV. None of them talk to each other, and none of them can tell you *why* you're stuck.

robo-trainer-mcp connects everything. Claude can pull training volume, sleep trends, nutrition, and mood all at once: then reason across them like a real coach.

## Demo

### Diagnosing a Plateau

```
You: "My squat hasn't moved in 5 weeks and I feel exhausted. What's wrong?"

Claude calls:
  training_get_volume_trend("squat", weeks=6)
  recovery_get_sleep_trend(days=42)
  nutrition_get_weekly_macros()
  mental_get_mood_trend(days=42)

─────────────────────────────────────────────────────────────
Training — squat volume (6 weeks):
  Week 1   12,400 kg
  Week 2   13,100 kg  +6%
  Week 3   14,200 kg  +15%
  Week 4   14,800 kg  +19%
  Week 5   15,300 kg  +23%   ← no deload recorded
  Week 6   15,100 kg

Recovery — sleep trend:
  Hours:    8.1h → 6.3h   ▼ 22%
  Quality:  7.8  → 5.4    ▼ 31%
  HRV:      63ms → 49ms   ▼ 22%

Nutrition — 7-day avg:
  Calories:  2,150 kcal   goal 2,600   deficit −450 kcal/day
  Protein:   168 g        goal 210 g   shortfall −42 g/day

Mood — 6-week trend:
  Energy:  7.4 → 5.0   ▼ 32%
  Stress:  3.2 → 6.1   ▲ 91%

─────────────────────────────────────────────────────────────
Diagnosis: Classic overreaching. Volume crept 23% over 6 weeks
with no deload. Sleep dropped 22%, calories are 450 below
maintenance, and protein is 20% under target. Four recovery
systems degraded simultaneously.

Plan:
  1. Deload this week — cut sets 40%, hold intensity ≥80% 1RM.
  2. Calories to maintenance (2,600 kcal) for 10 days.
  3. Hit 210 g protein and 8+ hours sleep nightly.
  4. Reassess in 2 weeks. Based on your pre-overreaching rate
     of progress, expect a squat PR within 3 weeks of recovery.
─────────────────────────────────────────────────────────────
```

### Powerlifting Meet Prep

```
You: "I squat 200 kg, bench 130 kg, deadlift 240 kg at 93 kg bodyweight."

Claude calls:
  pl_calculate_wilks(93, 570, "m")
  pl_calculate_dots(93, 570, "m")
  pl_analyze_sbd_ratio(200, 130, 240)
  pl_predict_attempts(200, 130, 240)

  Wilks 2020:  358.4   (Advanced)
  DOTS:        347.1   (Advanced)

  Lift proportions vs. elite average (raw):
    Squat   35.1%   elite avg 37.0%   ▼ 1.9%
    Bench   22.8%   elite avg 26.0%   ▼ 3.2%   ← biggest gap
    Dead    42.1%   elite avg 37.0%   ▲ 5.1%

  Weakest lift: Bench. Recommendation: prioritize hypertrophy
  and technique work on bench press to close the 3.2% gap.

  Competition attempts:
    Squat    180 / 195 / 207.5
    Bench    117.5 / 127.5 / 135
    Dead     215 / 235 / 250
    Projected total: 625 kg
```

### Strongman Standards Check

```
You: "Is my 130 kg log press competitive?"

Claude calls strongman_competition_standards("log_press", 130)

  Your best: 130 kg
  Standards:
    Novice:   80 kg   ✓
    Regional: 120 kg  ✓
    National: 150 kg  − 20 kg away
    Pro:      180 kg  − 50 kg away

  Current level: Regional. You are 20 kg from national standard.
```

### Readiness Score Before a Heavy Session

```
You: "I slept 6 hours, quality 5/10, soreness 7/10, stress 7/10. Should I train heavy?"

Claude calls recovery_calculate_readiness(6.0, 5, 7, 7)

  Readiness score: 41 / 100
  Recommendation: Low readiness — light technique session
  or active recovery recommended. Heavy singles today carry
  elevated injury risk.
```

## Architecture

```
                 ┌──────────────────────────────────┐
                 │          Claude (LLM)             │
                 │   reasons across all 24 tools     │
                 └─────────────┬────────────────────┘
                               │  MCP Protocol
                 ┌─────────────▼────────────────────┐
                 │        robo-trainer-mcp           │
                 │         (FastMCP server)          │
                 └────────┬─────────────┬────────────┘
                          │             │
             ┌────────────▼──┐  ┌───────▼──────────────┐
             │   SQLite DB   │  │  Open Food Facts API  │
             │ ~/.robo-      │  │  (food search only,   │
             │  trainer/     │  │   no account needed)  │
             │  data.db      │  └──────────────────────┘
             │               │
             │  food_log     │
             │  training_log │
             │  sleep_log    │
             │  mood_log     │
             │  event_log    │
             └───────────────┘
```

All personal data is stored locally in `~/.robo-trainer/data.db`.  
No account required. Nothing leaves your machine.

## Tools — 24 total

### Nutrition
| Tool | Description |
|---|---|
| `nutrition_search_food` | Search 3M+ products via Open Food Facts |
| `nutrition_log_meal` | Log food with calories and macros |
| `nutrition_get_daily_summary` | Daily totals vs. your goals |
| `nutrition_get_weekly_macros` | 7-day rolling average |
| `nutrition_set_goals` | Set calorie and macro targets |

### Strength Training
| Tool | Description |
|---|---|
| `training_log_set` | Log a set: weight, reps, RPE |
| `training_get_prs` | Personal records for every exercise |
| `training_calculate_1rm` | Epley 1RM estimate + full percentage chart |
| `training_get_volume_trend` | Weekly volume trend over N weeks |
| `training_get_session_history` | Session history for an exercise |

### Powerlifting
| Tool | Description |
|---|---|
| `pl_calculate_wilks` | Wilks 2020 score + classification |
| `pl_calculate_dots` | DOTS score + classification |
| `pl_predict_attempts` | Opener, 2nd, and 3rd attempt suggestions |
| `pl_analyze_sbd_ratio` | Identify weakest lift vs. elite proportions |

### Strongman
| Tool | Description |
|---|---|
| `strongman_log_event` | Log: weight, reps, time, or distance |
| `strongman_get_event_prs` | Best performances per event |
| `strongman_get_event_history` | Progress over time |
| `strongman_competition_standards` | Compare to novice → pro benchmarks |

### Recovery
| Tool | Description |
|---|---|
| `recovery_log_sleep` | Log hours, quality (1–10), HRV |
| `recovery_get_sleep_trend` | Sleep metrics over N days |
| `recovery_calculate_readiness` | 0–100 readiness score from 4 inputs |

### Mental Performance
| Tool | Description |
|---|---|
| `mental_log_mood` | Log mood, energy, stress (1–10 each) |
| `mental_get_mood_trend` | Rolling averages over N days |
| `mental_correlate_performance` | Pearson r: energy/stress vs. training output |

## Quick Start

**Install:**
```bash
pip install robo-trainer-mcp
```

**Add to Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "trainer": {
      "command": "robo-trainer-mcp"
    }
  }
}
```

**Or run from source:**
```bash
git clone https://github.com/gerardrecinto/robo-trainer-mcp
cd robo-trainer-mcp
pip install -e .
robo-trainer-mcp
```

**Or run with Docker:**
```bash
docker run -v ~/.robo-trainer:/root/.robo-trainer gerardrecinto/robo-trainer-mcp
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=src/robo_trainer --cov-report=term-missing
```

Expected:
```
tests/test_powerlifting.py::test_wilks_known_value PASSED
tests/test_powerlifting.py::test_dots_known_value PASSED
tests/test_powerlifting.py::test_sbd_ratio_identifies_bench_weakness PASSED
tests/test_powerlifting.py::test_attempt_prediction PASSED
tests/test_training.py::test_epley_1rm_single PASSED
tests/test_training.py::test_epley_1rm_reps PASSED
tests/test_training.py::test_volume_trend_demo_mode PASSED
tests/test_recovery.py::test_readiness_high PASSED
tests/test_recovery.py::test_readiness_low PASSED
tests/test_recovery.py::test_readiness_mid PASSED
tests/test_nutrition.py::test_demo_search_returns_results PASSED

11 passed in 0.38s   coverage: 89%
```

## Data Storage

- Personal data: `~/.robo-trainer/data.db` (SQLite, local only)
- Audit log: `~/.robo-trainer/audit.log` (one JSON line per tool call)
- Food search requires internet (Open Food Facts). Every other tool works fully offline.
