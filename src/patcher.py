import json
import os
import re
import shutil
import subprocess
import zipfile
from typing import Any, Dict, List, Optional

from .constants import (
    BUILD_DIR,
    MDF_KEY,
    MDF_KEY_LEN,
    PATCHES_DIR,
    RAW_DIR,
    SCENALIST_FILENAME,
    SCENARIO_BODY_FILENAME,
    SCENARIO_EXTRACTED_DIR,
    SCENARIO_INFOPSB_FILENAME,
    SPEAKERS_FILENAME,
    TITLE_ID,
)
from .utils import get_psbuild_path


def translate_speaker(orig_spk: Optional[str], speaker_map: Dict[str, Any]) -> Optional[str]:
    if not orig_spk or not speaker_map:
        return orig_spk

    # 1. Exact match in glossary
    if orig_spk in speaker_map:
        val = speaker_map[orig_spk]
        trans = val if isinstance(val, str) else val.get("translation", "")
        if trans:
            return trans

    # 2. Compound resolution (e.g. 'ココア＆チノ' -> 'Cocoa & Chino')
    if "＆" in orig_spk:
        parts = orig_spk.split("＆")
        translated_parts = []
        all_matched = True
        for p in parts:
            if p in speaker_map:
                val = speaker_map[p]
                p_trans = val if isinstance(val, str) else val.get("translation", "")
                if p_trans:
                    translated_parts.append(p_trans)
                else:
                    all_matched = False
                    break
            else:
                all_matched = False
                break
        if all_matched:
            return " & ".join(translated_parts)

    return orig_spk


def apply_patches(lang: str) -> List[str]:
    lang_patch_dir = os.path.join(PATCHES_DIR, lang)
    if not os.path.exists(lang_patch_dir):
        raise FileNotFoundError(f"Patches directory '{lang_patch_dir}' does not exist.")

    build_lang_dir = os.path.join(BUILD_DIR, lang)
    build_scn_dir = os.path.join(build_lang_dir, "scenario")

    if os.path.exists(build_lang_dir):
        shutil.rmtree(build_lang_dir)
    os.makedirs(build_scn_dir, exist_ok=True)

    # Copy raw scenario slices as base
    raw_scenario_dir = os.path.join(RAW_DIR, "scenario")
    for f in os.listdir(raw_scenario_dir):
        shutil.copy2(os.path.join(raw_scenario_dir, f), os.path.join(build_scn_dir, f))

    # Copy info PSB json & resx
    shutil.copy2(
        os.path.join(RAW_DIR, f"{SCENARIO_INFOPSB_FILENAME}.json"),
        os.path.join(build_lang_dir, f"{SCENARIO_INFOPSB_FILENAME}.json"),
    )
    shutil.copy2(
        os.path.join(RAW_DIR, f"{SCENARIO_INFOPSB_FILENAME}.resx.json"),
        os.path.join(build_lang_dir, f"{SCENARIO_INFOPSB_FILENAME}.resx.json"),
    )

    modified_files: List[str] = []
    patch_files = {f: os.path.join(lang_patch_dir, f) for f in os.listdir(lang_patch_dir) if f.endswith(".json")}
    choice_sync_map: Dict[str, str] = {}

    speakers_patch_path = os.path.join(lang_patch_dir, SPEAKERS_FILENAME)
    speaker_map: Dict[str, Any] = {}
    if os.path.exists(speakers_patch_path):
        try:
            with open(speakers_patch_path, "r", encoding="utf-8") as sf:
                speaker_map = json.load(sf)
        except Exception:
            speaker_map = {}

    for patch_fname, patch_path in patch_files.items():
        if patch_fname in ("scenelist.scn.json", f"{SCENALIST_FILENAME[:-7]}.json", SPEAKERS_FILENAME):
            continue

        with open(patch_path, "r", encoding="utf-8") as pf:
            patch = json.load(pf)

        identity = patch.get("identity")
        if not identity:
            continue

        raw_json_name = f"{identity}.m.json"
        raw_json_path = os.path.join(SCENARIO_EXTRACTED_DIR, raw_json_name)
        if not os.path.exists(raw_json_path):
            continue

        with open(raw_json_path, "r", encoding="utf-8") as rf:
            scenario_data = json.load(rf)

        has_modifications = False
        patch_scenes = patch.get("scenes", {})

        for scene in scenario_data.get("scenes", []):
            # Translate speakers in dialogue and selectInfo
            if speaker_map:
                if "texts" in scene:
                    for entry in scene["texts"]:
                        if isinstance(entry, list) and len(entry) >= 1 and entry[0]:
                            orig_spk = entry[0]
                            translated_spk = translate_speaker(orig_spk, speaker_map)
                            if translated_spk and translated_spk != orig_spk:
                                entry[0] = translated_spk
                                has_modifications = True

                if "selectInfo" in scene and scene["selectInfo"]:
                    orig_spk = scene["selectInfo"].get("name")
                    if orig_spk:
                        translated_spk = translate_speaker(orig_spk, speaker_map)
                        if translated_spk and translated_spk != orig_spk:
                            scene["selectInfo"]["name"] = translated_spk
                            has_modifications = True

            label = scene.get("label")
            if not label or label not in patch_scenes:
                continue

            p_scene = patch_scenes[label]

            # 1. Dialogues
            p_texts = p_scene.get("texts", {})
            if p_texts and "texts" in scene:
                for idx_str, entry in p_texts.items():
                    trans = entry.get("translation")
                    if trans:
                        t_idx = int(idx_str)
                        if t_idx < len(scene["texts"]):
                            scene["texts"][t_idx][2] = trans
                            has_modifications = True

            # 2. Select prompt
            p_prompt = p_scene.get("select_prompt")
            if p_prompt and p_prompt.get("translation") and "selectInfo" in scene and scene["selectInfo"]:
                scene["selectInfo"]["message"] = p_prompt["translation"]
                has_modifications = True

            # 3. Choices
            p_choices = p_scene.get("choices", {})
            if p_choices:
                for target, c_entry in p_choices.items():
                    c_trans = c_entry.get("translation")
                    if not c_trans:
                        continue

                    storage_name = scenario_data.get("name", "")
                    if storage_name:
                        choice_sync_map[f"{storage_name}#{target}"] = c_trans

                    if "selectInfo" in scene and scene["selectInfo"]:
                        for sel in scene["selectInfo"].get("select", []):
                            if sel.get("target") == target:
                                sel["text"] = c_trans
                                if "runLineStr" in sel:
                                    sel["runLineStr"] = re.sub(
                                        r'text=".*?"', f'text="{c_trans}"', sel["runLineStr"]
                                    )
                                has_modifications = True

                    if "selects" in scene and scene["selects"]:
                        for sel in scene["selects"]:
                            if sel.get("target") == target:
                                sel["text"] = c_trans
                                has_modifications = True

        if has_modifications:
            target_build_json = os.path.join(build_scn_dir, raw_json_name)
            with open(target_build_json, "w", encoding="utf-8") as out_f:
                json.dump(scenario_data, out_f, ensure_ascii=False, indent=2)

            src_resx = os.path.join(SCENARIO_EXTRACTED_DIR, f"{identity}.m.resx.json")
            if os.path.exists(src_resx):
                shutil.copy2(src_resx, os.path.join(build_scn_dir, f"{identity}.m.resx.json"))

            modified_files.append(raw_json_name)

    # Process scenelist patch
    scenelist_patch_path = os.path.join(lang_patch_dir, "scenelist.scn.json")
    if os.path.exists(scenelist_patch_path) or choice_sync_map:
        raw_sl_path = os.path.join(SCENARIO_EXTRACTED_DIR, SCENALIST_FILENAME)
        with open(raw_sl_path, "r", encoding="utf-8") as sf:
            sl_data = json.load(sf)

        sl_patch = {}
        if os.path.exists(scenelist_patch_path):
            with open(scenelist_patch_path, "r", encoding="utf-8") as sf:
                sl_patch = json.load(sf)

        patch_titles = sl_patch.get("titles", {})
        patch_choices = sl_patch.get("choices", {})

        sl_modified = False
        for item in sl_data.get("list", []):
            storage = item.get("storage", "")
            target = item.get("target", "")
            key = f"{storage}#{target}" if target else storage

            if key in patch_titles and patch_titles[key].get("translation"):
                item["title"] = patch_titles[key]["translation"]
                sl_modified = True

            if item.get("selects"):
                for sel in item["selects"]:
                    sel_key = f"{storage}#{sel.get('target', '')}"
                    trans = ""
                    if sel_key in patch_choices and patch_choices[sel_key].get("translation"):
                        trans = patch_choices[sel_key]["translation"]
                    elif sel_key in choice_sync_map:
                        trans = choice_sync_map[sel_key]

                    if trans:
                        sel["text"] = trans
                        sl_modified = True

        if sl_modified:
            target_sl_json = os.path.join(build_scn_dir, SCENALIST_FILENAME)
            with open(target_sl_json, "w", encoding="utf-8") as sf:
                json.dump(sl_data, sf, ensure_ascii=False, indent=2)

            src_sl_resx = os.path.join(SCENARIO_EXTRACTED_DIR, f"{SCENALIST_FILENAME[:-5]}.resx.json")
            if os.path.exists(src_sl_resx):
                shutil.copy2(src_sl_resx, os.path.join(build_scn_dir, f"{SCENALIST_FILENAME[:-5]}.resx.json"))

            modified_files.append(SCENALIST_FILENAME)

    print(f"Applied patches for '{lang}': {len(modified_files)} scenario files modified.")
    return modified_files


def build_binaries(lang: str, repatch: bool = False) -> Dict[str, str]:
    psbuild = get_psbuild_path()
    build_lang_dir = os.path.join(BUILD_DIR, lang)
    build_scn_dir = os.path.join(build_lang_dir, "scenario")

    modified_files = apply_patches(lang)

    print(f"Compiling {len(modified_files)} modified scenario JSONs to binary slices...")
    for m_file in modified_files:
        json_path = os.path.join(build_scn_dir, m_file)
        compiled_m_path = json_path[:-5]  # strip .json -> .m

        cmd = [psbuild, json_path, "-o", compiled_m_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to compile '{m_file}':\n{res.stderr}")

        # The slice name in archive is filename stripped of .scn.m.json
        slice_name = m_file[:-11]
        target_slice_path = os.path.join(build_scn_dir, slice_name)

        if os.path.exists(compiled_m_path):
            shutil.move(compiled_m_path, target_slice_path)

        # Cleanup source json and resx from build dir so info-psb sees only the binary slice
        if os.path.exists(json_path):
            os.remove(json_path)
        resx_path = json_path[:-5] + ".resx.json"
        if os.path.exists(resx_path):
            os.remove(resx_path)

    print("Repacking scenario archive (info.psb.m & body.bin)...")
    info_json_path = os.path.join(build_lang_dir, f"{SCENARIO_INFOPSB_FILENAME}.json")
    pack_cmd = [
        psbuild,
        "info-psb",
        "-k",
        MDF_KEY,
        "-l",
        str(MDF_KEY_LEN),
        "-b",
        SCENARIO_BODY_FILENAME,
        "-o",
        build_lang_dir,
        info_json_path,
    ]
    pack_res = subprocess.run(pack_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if pack_res.returncode != 0:
        raise RuntimeError(f"Failed to pack archive:\n{pack_res.stderr}")

    out_body = os.path.join(build_lang_dir, SCENARIO_BODY_FILENAME)
    out_info = os.path.join(build_lang_dir, SCENARIO_INFOPSB_FILENAME)

    if not os.path.exists(out_body) or not os.path.exists(out_info):
        raise FileNotFoundError(f"Expected output binaries not found in {build_lang_dir}")

    artifacts = {
        "body": out_body,
        "info": out_info,
    }

    # Standalone zip
    bin_zip_path = os.path.join(build_lang_dir, f"wonderful-party-binaries-{lang}.zip")
    with zipfile.ZipFile(bin_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_body, SCENARIO_BODY_FILENAME)
        zf.write(out_info, SCENARIO_INFOPSB_FILENAME)
    artifacts["zip_binaries"] = bin_zip_path

    # rePatch zip
    if repatch:
        repatch_zip_path = os.path.join(build_lang_dir, f"wonderful-party-repatch-{lang}.zip")
        with zipfile.ZipFile(repatch_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            arc_body = f"rePatch/{TITLE_ID}/data/scenario/{SCENARIO_BODY_FILENAME}"
            arc_info = f"rePatch/{TITLE_ID}/data/scenario/{SCENARIO_INFOPSB_FILENAME}"
            zf.write(out_body, arc_body)
            zf.write(out_info, arc_info)
        artifacts["zip_repatch"] = repatch_zip_path

    print(f"Build complete for '{lang}'!")
    for k, v in artifacts.items():
        print(f"  {k}: {v} ({os.path.getsize(v):,} bytes)")

    return artifacts
