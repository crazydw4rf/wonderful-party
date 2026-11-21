import json
import os
from typing import Any, Dict, Optional

from .constants import (
    PATCHES_DIR,
    SCENALIST_FILENAME,
    SCENARIO_EXTRACTED_DIR,
    STATUS_UNTRANSLATED,
    SUPPORTED_LANGUAGES,
)


def has_japanese_text(text: Optional[str]) -> bool:
    if not text:
        return False
    return any(
        "\u3040" <= c <= "\u30ff"  # Hiragana, Katakana
        or "\u4e00" <= c <= "\u9fff"  # CJK Unified Ideographs (Kanji)
        or "\u3000" <= c <= "\u303f"  # CJK Symbols and Punctuation
        for c in text
    )


def get_scenario_identity(filename: str) -> str:
    if filename.endswith(".m.json"):
        return filename[:-7]
    if filename.endswith(".json"):
        return filename[:-5]
    return filename


def extract_scenario_file(json_path: str, existing_patch: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    filename = os.path.basename(json_path)
    identity = get_scenario_identity(filename)

    scenes_data = data.get("scenes", [])
    if not scenes_data:
        return None

    patch_scenes: Dict[str, Any] = {}
    total_translatable = 0

    existing_scenes = (existing_patch or {}).get("scenes", {})

    for s_idx, scene in enumerate(scenes_data):
        label = scene.get("label", f"__scene_{s_idx}")
        scene_patch: Dict[str, Any] = {}
        existing_scene = existing_scenes.get(label, {})

        texts = scene.get("texts", [])
        if texts:
            patch_texts: Dict[str, Any] = {}
            existing_texts = existing_scene.get("texts", {})
            for t_idx, entry in enumerate(texts):
                if isinstance(entry, list) and len(entry) >= 3:
                    spk = entry[0]
                    orig = entry[2] or ""

                    ext = existing_texts.get(str(t_idx), {})
                    patch_texts[str(t_idx)] = {
                        "speaker": spk,
                        "original": orig,
                        "translation": ext.get("translation", ""),
                        "status": ext.get("status", STATUS_UNTRANSLATED),
                    }
                    total_translatable += 1
            if patch_texts:
                scene_patch["texts"] = patch_texts

        select_info = scene.get("selectInfo")
        if select_info and isinstance(select_info, dict):
            existing_prompt = existing_scene.get("select_prompt", {})
            prompt_msg = select_info.get("message") or ""
            prompt_spk = select_info.get("name")
            if prompt_msg:
                scene_patch["select_prompt"] = {
                    "speaker": prompt_spk,
                    "original": prompt_msg,
                    "translation": existing_prompt.get("translation", ""),
                    "status": existing_prompt.get("status", STATUS_UNTRANSLATED),
                }
                total_translatable += 1

            choices = select_info.get("select", [])
            existing_choices = existing_scene.get("choices", {})
            if choices:
                patch_choices: Dict[str, Any] = {}
                for c_idx, choice in enumerate(choices):
                    target = choice.get("target", f"choice_{c_idx}")
                    orig_choice = choice.get("text") or ""
                    ext_c = existing_choices.get(target, {})
                    patch_choices[target] = {
                        "original": orig_choice,
                        "translation": ext_c.get("translation", ""),
                        "status": ext_c.get("status", STATUS_UNTRANSLATED),
                    }
                    total_translatable += 1
                if patch_choices:
                    scene_patch["choices"] = patch_choices

        if scene_patch:
            patch_scenes[label] = scene_patch

    if total_translatable == 0:
        return None

    return {
        "identity": identity,
        "scenes": patch_scenes,
    }


def extract_scenelist_file(json_path: str, existing_patch: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_titles = (existing_patch or {}).get("titles", {})
    existing_choices = (existing_patch or {}).get("choices", {})

    patch_titles: Dict[str, Any] = {}
    patch_choices: Dict[str, Any] = {}

    for item in data.get("list", []):
        storage = item.get("storage", "")
        target = item.get("target", "")
        title = item.get("title", "")

        key = f"{storage}#{target}" if target else storage

        if has_japanese_text(title):
            ext_t = existing_titles.get(key, {})
            patch_titles[key] = {
                "original": title,
                "translation": ext_t.get("translation", ""),
                "status": ext_t.get("status", STATUS_UNTRANSLATED),
            }

        selects = item.get("selects")
        if selects and isinstance(selects, list):
            for sel in selects:
                sel_target = sel.get("target", "")
                sel_text = sel.get("text", "")
                choice_key = f"{storage}#{sel_target}"
                ext_c = existing_choices.get(choice_key, {})
                patch_choices[choice_key] = {
                    "original": sel_text,
                    "translation": ext_c.get("translation", ""),
                    "status": ext_c.get("status", STATUS_UNTRANSLATED),
                }

    return {
        "identity": "scenelist.scn",
        "titles": patch_titles,
        "choices": patch_choices,
    }


def extract_all_patches(lang: str) -> int:
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language '{lang}'. Choose from: {list(SUPPORTED_LANGUAGES.keys())}")

    lang_dir = os.path.join(PATCHES_DIR, lang)
    os.makedirs(lang_dir, exist_ok=True)

    if not os.path.exists(SCENARIO_EXTRACTED_DIR):
        raise FileNotFoundError(f"Scenario directory '{SCENARIO_EXTRACTED_DIR}' does not exist. Run 'setup' first.")

    files = sorted(os.listdir(SCENARIO_EXTRACTED_DIR))
    extracted_count = 0

    for fname in files:
        if not fname.endswith(".scn.m.json"):
            continue

        full_path = os.path.join(SCENARIO_EXTRACTED_DIR, fname)
        identity = get_scenario_identity(fname)
        patch_filename = f"{identity}.json"
        patch_path = os.path.join(lang_dir, patch_filename)

        existing_patch = None
        if os.path.exists(patch_path):
            try:
                with open(patch_path, "r", encoding="utf-8") as pf:
                    existing_patch = json.load(pf)
            except Exception:
                existing_patch = None

        if fname == SCENALIST_FILENAME:
            patch_data = extract_scenelist_file(full_path, existing_patch)
        else:
            patch_data = extract_scenario_file(full_path, existing_patch)

        if patch_data:
            with open(patch_path, "w", encoding="utf-8") as out:
                json.dump(patch_data, out, ensure_ascii=False, indent=2)
            extracted_count += 1

    print(f"Extracted {extracted_count} patch templates for language '{lang}' into '{lang_dir}'.")
    return extracted_count
