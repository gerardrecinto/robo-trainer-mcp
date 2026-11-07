"""Small built-in exercise library used by the plan tools.

Limitation tags only mark exercises that are commonly listed as awkward for that body area.
They are a simple filter, not advice. Ask a qualified professional about any injury.
"""
from __future__ import annotations

from dataclasses import dataclass

EQUIPMENT = (
    "bodyweight", "dumbbells", "barbell", "kettlebell", "resistance_bands", "machines",
    "cables", "pull_up_bar", "bench", "cardio_machine", "jump_rope",
)
DIFFICULTIES = ("beginner", "intermediate", "advanced")
COMPOUND_PATTERNS = (
    "squat", "hinge", "lunge", "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
)
# Words people are likely to type, mapped to the tag used in the library.
LIMITATION_ALIASES = {
    "knees": "knee", "low_back": "lower_back", "back": "lower_back", "lumbar": "lower_back",
    "shoulders": "shoulder", "wrists": "wrist", "elbows": "elbow", "hips": "hip", "ankles": "ankle",
}


@dataclass(frozen=True)
class Exercise:
    name: str
    pattern: str
    muscles: tuple[str, ...]
    equipment: tuple[str, ...]
    difficulty: str
    limitations: tuple[str, ...]
    alternatives: tuple[str, ...]
    unit: str = "reps"

    @property
    def compound(self) -> bool:
        return self.pattern in COMPOUND_PATTERNS

    def as_dict(self) -> dict:
        return {
            "name": self.name, "pattern": self.pattern, "muscles": list(self.muscles),
            "equipment": list(self.equipment), "difficulty": self.difficulty,
            "limitation_tags": list(self.limitations), "alternatives": list(self.alternatives),
            "unit": self.unit,
        }


def _e(name, pattern, muscles, equipment, difficulty, limitations, alternatives, unit="reps"):
    return Exercise(name, pattern, tuple(muscles.split()), tuple(equipment.split()), difficulty,
                    tuple(limitations.split()), tuple(a.strip() for a in alternatives.split(",") if a.strip()), unit)


_B, _I, _A = DIFFICULTIES

LIBRARY: tuple[Exercise, ...] = (
    _e("Back Squat", "squat", "quads glutes core", "barbell", _I, "knee lower_back", "Goblet Squat, Leg Press"),
    _e("Goblet Squat", "squat", "quads glutes core", "dumbbells", _B, "knee", "Bodyweight Squat, Leg Press"),
    _e("Leg Press", "squat", "quads glutes", "machines", _B, "knee", "Goblet Squat, Bodyweight Squat"),
    _e("Bodyweight Squat", "squat", "quads glutes", "bodyweight", _B, "knee", "Goblet Squat, Glute Bridge"),
    _e("Conventional Deadlift", "hinge", "hamstrings glutes back", "barbell", _A, "lower_back", "Romanian Deadlift, Kettlebell Deadlift"),
    _e("Romanian Deadlift", "hinge", "hamstrings glutes back", "barbell", _I, "lower_back", "Dumbbell Romanian Deadlift, Hip Thrust"),
    _e("Dumbbell Romanian Deadlift", "hinge", "hamstrings glutes back", "dumbbells", _B, "lower_back", "Kettlebell Deadlift, Glute Bridge"),
    _e("Kettlebell Deadlift", "hinge", "hamstrings glutes back", "kettlebell", _B, "lower_back", "Dumbbell Romanian Deadlift, Glute Bridge"),
    _e("Hip Thrust", "hinge", "glutes hamstrings", "barbell bench", _I, "", "Glute Bridge, Band Pull-Through"),
    _e("Glute Bridge", "hinge", "glutes hamstrings", "bodyweight", _B, "", "Hip Thrust, Band Pull-Through"),
    _e("Band Pull-Through", "hinge", "glutes hamstrings", "resistance_bands", _B, "", "Glute Bridge, Hip Thrust"),
    _e("Walking Lunge", "lunge", "quads glutes", "dumbbells", _I, "knee", "Step-Up, Reverse Lunge"),
    _e("Bulgarian Split Squat", "lunge", "quads glutes", "dumbbells bench", _I, "knee", "Step-Up, Reverse Lunge"),
    _e("Step-Up", "lunge", "quads glutes", "dumbbells bench", _B, "knee", "Reverse Lunge, Bulgarian Split Squat"),
    _e("Reverse Lunge", "lunge", "quads glutes", "bodyweight", _B, "knee", "Step-Up, Glute Bridge"),
    _e("Barbell Bench Press", "horizontal_push", "chest triceps shoulders", "barbell bench", _I, "shoulder wrist", "Dumbbell Bench Press, Push-Up"),
    _e("Dumbbell Bench Press", "horizontal_push", "chest triceps shoulders", "dumbbells bench", _B, "shoulder", "Push-Up, Machine Chest Press"),
    _e("Machine Chest Press", "horizontal_push", "chest triceps", "machines", _B, "shoulder", "Push-Up, Band Chest Press"),
    _e("Push-Up", "horizontal_push", "chest triceps shoulders", "bodyweight", _B, "wrist shoulder", "Band Chest Press, Dumbbell Bench Press"),
    _e("Band Chest Press", "horizontal_push", "chest triceps", "resistance_bands", _B, "shoulder", "Push-Up, Machine Chest Press"),
    _e("Overhead Press", "vertical_push", "shoulders triceps", "barbell", _I, "shoulder lower_back", "Dumbbell Shoulder Press, Machine Shoulder Press"),
    _e("Dumbbell Shoulder Press", "vertical_push", "shoulders triceps", "dumbbells", _B, "shoulder", "Machine Shoulder Press, Pike Push-Up"),
    _e("Machine Shoulder Press", "vertical_push", "shoulders triceps", "machines", _B, "shoulder", "Dumbbell Shoulder Press, Pike Push-Up"),
    _e("Pike Push-Up", "vertical_push", "shoulders triceps", "bodyweight", _I, "shoulder wrist", "Dumbbell Shoulder Press, Machine Shoulder Press"),
    _e("Barbell Row", "horizontal_pull", "back biceps", "barbell", _I, "lower_back", "One-Arm Dumbbell Row, Seated Cable Row"),
    _e("One-Arm Dumbbell Row", "horizontal_pull", "back biceps", "dumbbells", _B, "", "Seated Cable Row, Band Row"),
    _e("Seated Cable Row", "horizontal_pull", "back biceps", "cables", _B, "", "One-Arm Dumbbell Row, Band Row"),
    _e("Band Row", "horizontal_pull", "back biceps", "resistance_bands", _B, "", "One-Arm Dumbbell Row, Inverted Row"),
    _e("Inverted Row", "horizontal_pull", "back biceps", "pull_up_bar", _I, "", "Seated Cable Row, Band Row"),
    _e("Pull-Up", "vertical_pull", "back biceps", "pull_up_bar", _A, "shoulder elbow", "Chin-Up, Lat Pulldown"),
    _e("Chin-Up", "vertical_pull", "back biceps", "pull_up_bar", _I, "elbow", "Lat Pulldown, Pull-Up"),
    _e("Lat Pulldown", "vertical_pull", "back biceps", "cables", _B, "shoulder", "Chin-Up, Band Row"),
    _e("Dumbbell Curl", "arms_biceps", "biceps", "dumbbells", _B, "elbow", "Band Curl, Cable Curl"),
    _e("Cable Curl", "arms_biceps", "biceps", "cables", _B, "elbow", "Dumbbell Curl, Band Curl"),
    _e("Band Curl", "arms_biceps", "biceps", "resistance_bands", _B, "elbow", "Dumbbell Curl, Cable Curl"),
    _e("Triceps Pushdown", "arms_triceps", "triceps", "cables", _B, "elbow", "Band Triceps Extension, Bench Dip"),
    _e("Overhead Dumbbell Triceps Extension", "arms_triceps", "triceps", "dumbbells", _B, "elbow shoulder", "Triceps Pushdown, Band Triceps Extension"),
    _e("Band Triceps Extension", "arms_triceps", "triceps", "resistance_bands", _B, "elbow", "Triceps Pushdown, Bench Dip"),
    _e("Bench Dip", "arms_triceps", "triceps chest", "bench", _I, "shoulder wrist", "Triceps Pushdown, Band Triceps Extension"),
    _e("Dumbbell Lateral Raise", "shoulders_iso", "shoulders", "dumbbells", _B, "shoulder", "Cable Face Pull, Band Pull-Apart"),
    _e("Cable Face Pull", "shoulders_iso", "shoulders back", "cables", _B, "", "Band Pull-Apart, Dumbbell Lateral Raise"),
    _e("Band Pull-Apart", "shoulders_iso", "shoulders back", "resistance_bands", _B, "", "Cable Face Pull, Dumbbell Lateral Raise"),
    _e("Standing Calf Raise", "calves", "calves", "bodyweight", _B, "ankle", "Dumbbell Calf Raise"),
    _e("Dumbbell Calf Raise", "calves", "calves", "dumbbells", _B, "ankle", "Standing Calf Raise"),
    _e("Dead Bug", "core", "core", "bodyweight", _B, "", "Plank, Pallof Press"),
    _e("Plank", "core", "core", "bodyweight", _B, "wrist", "Dead Bug, Pallof Press", "seconds"),
    _e("Side Plank", "core", "core", "bodyweight", _I, "shoulder wrist", "Dead Bug, Plank", "seconds"),
    _e("Pallof Press", "core", "core", "resistance_bands", _B, "", "Dead Bug, Plank"),
    _e("Hanging Knee Raise", "core", "core", "pull_up_bar", _I, "shoulder", "Dead Bug, Plank"),
    _e("Brisk Walk", "cardio", "full_body", "bodyweight", _B, "", "Stationary Bike, Easy Jog", "minutes"),
    _e("Stationary Bike", "cardio", "quads full_body", "cardio_machine", _B, "", "Brisk Walk, Rowing Machine", "minutes"),
    _e("Easy Jog", "cardio", "full_body", "bodyweight", _B, "knee ankle", "Brisk Walk, Stationary Bike", "minutes"),
    _e("Rowing Machine", "cardio", "back quads full_body", "cardio_machine", _B, "lower_back", "Stationary Bike, Brisk Walk", "minutes"),
    _e("Jump Rope", "cardio", "calves full_body", "jump_rope", _I, "ankle knee", "Brisk Walk, Stationary Bike", "minutes"),
    _e("Cat-Cow", "mobility", "spine", "bodyweight", _B, "wrist", "Thoracic Rotation, Child's Pose", "seconds"),
    _e("Thoracic Rotation", "mobility", "spine shoulders", "bodyweight", _B, "", "Cat-Cow, Band Shoulder Dislocate", "seconds"),
    _e("Hip Flexor Stretch", "mobility", "hips", "bodyweight", _B, "knee", "90/90 Hip Switch, Hamstring Stretch", "seconds"),
    _e("90/90 Hip Switch", "mobility", "hips", "bodyweight", _I, "knee hip", "Hip Flexor Stretch, Hamstring Stretch", "seconds"),
    _e("Hamstring Stretch", "mobility", "hamstrings", "bodyweight", _B, "", "Hip Flexor Stretch, Child's Pose", "seconds"),
    _e("Ankle Rock", "mobility", "calves ankles", "bodyweight", _B, "ankle", "Hamstring Stretch, Hip Flexor Stretch", "seconds"),
    _e("Child's Pose", "mobility", "spine hips", "bodyweight", _B, "knee", "Cat-Cow, Hamstring Stretch", "seconds"),
    _e("Band Shoulder Dislocate", "mobility", "shoulders", "resistance_bands", _B, "shoulder", "Thoracic Rotation, Cat-Cow", "seconds"),
)

BY_NAME = {e.name: e for e in LIBRARY}
MUSCLES = tuple(sorted({m for e in LIBRARY for m in e.muscles}))
PATTERNS = tuple(dict.fromkeys(e.pattern for e in LIBRARY))
KNOWN_LIMITATIONS = tuple(sorted({t for e in LIBRARY for t in e.limitations}))


def normalize_limitation(text: str) -> str:
    tag = "_".join(text.strip().lower().replace("-", " ").split())
    return LIMITATION_ALIASES.get(tag, tag)


def available(ex: Exercise, equipment: set[str], excluded: set[str], max_difficulty: str = "advanced") -> bool:
    """True when the user owns the equipment, the exercise carries none of the excluded tags, and it is not too hard."""
    return (
        all(item == "bodyweight" or item in equipment for item in ex.equipment)
        and not (set(ex.limitations) & excluded)
        and DIFFICULTIES.index(ex.difficulty) <= DIFFICULTIES.index(max_difficulty)
    )
