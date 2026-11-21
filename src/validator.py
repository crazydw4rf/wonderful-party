import json
import os
from typing import List, Tuple

from .constants import (
    PATCHES_DIR,
    SCENALIST_FILENAME,
    SCENARIO_EXTRACTED_DIR,
    SUPPORTED_LANGUAGES,
    VALID_STATUSES,
)


def validate_language_patches(lang: str) -> Tuple[bool, List[str]]:
    lang_dir = os.path.join(PATCHES_DIR, lang)
    if not os.path.exists(lang_dir):
        return False, [f"Language directory '{lang_dir}' does not exist."]

    errors: List[str] = []
    files = sorted(os.listdir(lang_dir))

    for fname in files:
        if not fname.endswith(".json"):
            continue

        fpath = os.path.join(lang_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as pf:
                data = json.load(pf)
        except json.JSONDecodeError as e:
            errors.append(f"{fname}: Invalid JSON syntax - {e}")
            continue

        identity = data.get("identity")
        if not identity:
            errors.append(f"{fname}: Missing 'identity' field")
            continue

        if fname in ("scenelist.scn.json", f"{SCENALIST_FILENAME[:-7]}.json"):
            for key, t_info in data.get("titles", {}).items():
                status = t_info.get("status")
                if status not in VALID_STATUSES:
                    errors.append(f"{fname} title '{key}': Invalid status '{status}'")
            for key, c_info in data.get("choices", {}).items():
                status = c_info.get("status")
                if status not in VALID_STATUSES:
                    errors.append(f"{fname} choice '{key}': Invalid status '{status}'")
            continue

        # Check against base scenario if available
        base_json_path = os.path.join(SCENARIO_EXTRACTED_DIR, f"{identity}.m.json")
        base_data = None
        if os.path.exists(base_json_path):
            with open(base_json_path, "r", encoding="utf-8") as bf:
                base_data = json.load(bf)
            base_scenes = {s.get("label"): s for s in base_data.get("scenes", [])}
        else:
            base_scenes = {}

        scenes = data.get("scenes", {})
        if not isinstance(scenes, dict):
            errors.append(f"{fname}: 'scenes' must be a dictionary")
            continue

        for label, scene in scenes.items():
            base_scene = base_scenes.get(label) if base_scenes else None

            # Validate texts
            texts = scene.get("texts", {})
            for idx_str, t_entry in texts.items():
                status = t_entry.get("status")
                if status not in VALID_STATUSES:
                    errors.append(f"{fname} [{label}] text '{idx_str}': Invalid status '{status}'")

                if base_scene and "texts" in base_scene:
                    try:
                        t_idx = int(idx_str)
                        if t_idx < len(base_scene["texts"]):
                            expected_orig = base_scene["texts"][t_idx][2] or ""
                            actual_orig = t_entry.get("original", "")
                            if expected_orig != actual_orig:
                                errors.append(
                                    f"{fname} [{label}] text '{idx_str}': Original text mismatch. "
                                    f"Expected: {repr(expected_orig[:30])}, Got: {repr(actual_orig[:30])}"
                                )
                    except ValueError:
                        errors.append(f"{fname} [{label}]: Text index '{idx_str}' is not an integer")

            # Validate prompt
            prompt = scene.get("select_prompt")
            if prompt:
                status = prompt.get("status")
                if status not in VALID_STATUSES:
                    errors.append(f"{fname} [{label}] select_prompt: Invalid status '{status}'")

            # Validate choices
            choices = scene.get("choices", {})
            for target, c_entry in choices.items():
                status = c_entry.get("status")
                if status not in VALID_STATUSES:
                    errors.append(f"{fname} [{label}] choice '{target}': Invalid status '{status}'")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_all(lang: str = None) -> bool:
    targets = [lang] if lang else list(SUPPORTED_LANGUAGES.keys())
    all_ok = True

    for l in targets:
        print(f"Validating patches for language '{l}'...")
        is_ok, errs = validate_language_patches(l)
        if not is_ok:
            all_ok = False
            print(f"FAILED validation for '{l}' with {len(errs)} error(s):")
            for err in errs[:20]:
                print(f"  - {err}")
            if len(errs) > 20:
                print(f"  ... and {len(errs) - 20} more errors.")
        else:
            print(f"PASSED validation for '{l}'.")

    return all_ok
