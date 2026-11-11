"""Feature schema for blinded extraction. Version it: any change to the schema or prompt is a new version."""

from __future__ import annotations

SCHEMA_VERSION = "features-v1"

SHAPES = ["point_of_light", "orb_or_sphere", "disc", "triangle", "cylinder_or_cigar", "rectangle", "chevron_or_boomerang",
          "diamond", "oval_or_egg", "fireball", "formation_of_lights", "changing_shape", "other", "not_stated"]
MOTIONS = ["stationary", "hovered_then_moved", "straight_steady", "slow_drift", "erratic", "sharp_turn",
           "sudden_acceleration", "vanished_instantly", "split_or_merged", "ascended", "descended", "followed_observer",
           "moved_in_formation", "not_stated"]
CONVENTIONAL = ["aircraft", "helicopter", "drone", "satellite", "starlink_train", "planet_or_star", "meteor", "sky_lantern",
                "balloon", "rocket_launch", "fireworks", "bird_or_insect", "searchlight_or_laser", "other_known"]

TOOL = {
    "name": "record_features",
    "description": "Record what the sighting report says. Use only what the text states; use not_stated or null otherwise.",
    "input_schema": {
        "type": "object",
        "properties": {
            "object_count": {"type": ["integer", "null"], "description": "Number of objects, null if not stated"},
            "shapes": {"type": "array", "items": {"type": "string", "enum": SHAPES}},
            "colours": {"type": "array", "items": {"type": "string"}, "description": "Colours named in the text"},
            "light_pattern": {"type": "string", "enum": ["steady", "blinking_regular", "flashing_irregular",
                                                          "changing_colour", "no_lights", "not_stated"]},
            "motions": {"type": "array", "items": {"type": "string", "enum": MOTIONS}},
            "speed": {"type": "string", "enum": ["stationary", "slow", "moderate", "fast", "extremely_fast", "not_stated"]},
            "sound": {"type": "string", "enum": ["silent", "engine_or_rotor", "other_sound", "not_stated"]},
            "apparent_distance": {"type": "string", "enum": ["very_close", "near", "far", "very_high", "not_stated"]},
            "witness_count": {"type": ["integer", "null"]},
            "evidence": {"type": "array", "items": {"type": "string", "enum": ["photo", "video", "radar", "none_stated"]}},
            "physical_effects": {"type": "array", "items": {"type": "string", "enum": [
                "electrical_interference", "animal_reaction", "physiological", "ground_traces", "none_stated"]}},
            "conventional_likelihood": {
                "type": "object", "description": "Probability 0-1 that a person seeing each of these would write this report",
                "properties": {k: {"type": "number", "minimum": 0, "maximum": 1} for k in CONVENTIONAL},
                "required": CONVENTIONAL,
            },
            "detail": {"type": "string", "enum": ["vague", "some_detail", "detailed"]},
        },
        "required": ["object_count", "shapes", "colours", "light_pattern", "motions", "speed", "sound",
                     "apparent_distance", "witness_count", "evidence", "physical_effects", "conventional_likelihood",
                     "detail"],
    },
}

SYSTEM = (
    "You read short UFO sighting summaries and record their observable features with the record_features tool. "
    "Record only what the text states or directly implies; do not add details. You are not told when or where the "
    "sighting happened. For conventional_likelihood, estimate for each listed ordinary cause how likely it is that "
    "someone seeing that cause would have written this summary; the numbers need not sum to one. Treat claims of "
    "unusual motion as reported, without judging whether they are true."
)


def user_message(text: str, duration_s: float | None) -> str:
    dur = "not stated" if duration_s is None or duration_s != duration_s else f"{int(duration_s)} seconds"
    return f"Reported duration: {dur}\nSummary: {text}"
