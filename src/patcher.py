from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import shutil
import subprocess
import zipfile
from typing import Any, Dict, List, Optional

DEFAULT_MAX_COMPILE_WORKERS = 5
PSBUILD_MEM_MB_PER_WORKER = 160
SYSTEM_MEM_RESERVE_MB = 256

from .constants import (
    BUILD_DIR,
    MDF_KEY,
    MDF_KEY_LEN,
    MOTION_MAIN_FILENAME,
    MOTION_MAIN_PATH,
    PATCH_BODY_FILENAME,
    PATCH_INFOPSB_FILENAME,
    PATCHES_DIR,
    RAW_DIR,
    SCENALIST_FILENAME,
    SCENARIO_BODY_FILENAME,
    SCENARIO_EXTRACTED_DIR,
    SCENARIO_INFOPSB_FILENAME,
    SCRIPT_BODY_FILENAME,
    SCRIPT_BODY_PATH,
    SCRIPT_INFOPSB_FILENAME,
    SCRIPT_INFOPSB_PATH,
    SPEAKERS_FILENAME,
    TITLE_ID,
)
from .utils import ensure_game_binaries, get_psbuild_path


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


def _patch_has_translations(patch: Dict[str, Any]) -> bool:
    for p_scene in patch.get("scenes", {}).values():
        if any(entry.get("translation") for entry in p_scene.get("texts", {}).values()):
            return True
        if p_scene.get("select_prompt", {}).get("translation"):
            return True
        if any(entry.get("translation") for entry in p_scene.get("choices", {}).values()):
            return True
    return False


def _get_available_memory_mb() -> Optional[int]:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None


def _resolve_compile_workers(jobs: Optional[int], task_count: int) -> int:
    if task_count <= 0:
        return 1
    if jobs is not None:
        return max(1, min(jobs, task_count))

    workers = min(DEFAULT_MAX_COMPILE_WORKERS, max(1, os.cpu_count() or 4))
    avail_mb = _get_available_memory_mb()
    if avail_mb is not None:
        mem_cap = max(1, (avail_mb - SYSTEM_MEM_RESERVE_MB) // PSBUILD_MEM_MB_PER_WORKER)
        workers = min(workers, mem_cap)
    return max(1, min(workers, task_count))


def _compile_scenario_slice(psbuild: str, patch_scn_dir: str, build_scn_dir: str, m_file: str) -> str:
    json_path = os.path.join(patch_scn_dir, m_file)
    compiled_m_path = json_path[:-5]

    cmd = [psbuild, json_path, "-o", compiled_m_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        raise RuntimeError(f"Failed to compile '{m_file}':\n{err}")

    if os.path.exists(json_path):
        os.remove(json_path)
    resx_path = json_path[:-5] + ".resx.json"
    if os.path.exists(resx_path):
        os.remove(resx_path)

    slice_name = m_file[:-11] if m_file.endswith(".scn.m.json") else m_file[:-5]
    shutil.copy2(compiled_m_path, os.path.join(build_scn_dir, slice_name))

    raw_json_in_scn = os.path.join(build_scn_dir, m_file)
    if os.path.exists(raw_json_in_scn):
        os.remove(raw_json_in_scn)
    raw_resx_in_scn = raw_json_in_scn[:-5] + ".resx.json"
    if os.path.exists(raw_resx_in_scn):
        os.remove(raw_resx_in_scn)
    return m_file


def apply_patches(lang: str, pretty: bool = True) -> List[str]:
    lang_patch_dir = os.path.join(PATCHES_DIR, lang)
    if not os.path.exists(lang_patch_dir):
        raise FileNotFoundError(f"Patches directory '{lang_patch_dir}' does not exist.")

    build_lang_dir = os.path.join(BUILD_DIR, lang)
    build_scn_dir = os.path.join(build_lang_dir, "scenario")
    patch_scn_dir = os.path.join(build_lang_dir, "patch", "scenario")

    if os.path.exists(build_lang_dir):
        shutil.rmtree(build_lang_dir)
    os.makedirs(build_scn_dir, exist_ok=True)
    os.makedirs(patch_scn_dir, exist_ok=True)

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
        if not identity or not _patch_has_translations(patch):
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
            if speaker_map:
                for scene in scenario_data.get("scenes", []):
                    if "texts" in scene:
                        for entry in scene["texts"]:
                            if isinstance(entry, list):
                                for spk_idx in (0, 1):
                                    if len(entry) > spk_idx and entry[spk_idx]:
                                        orig_spk = entry[spk_idx]
                                        translated_spk = translate_speaker(orig_spk, speaker_map)
                                        if translated_spk and translated_spk != orig_spk:
                                            entry[spk_idx] = translated_spk

                    if "selectInfo" in scene and scene["selectInfo"]:
                        orig_spk = scene["selectInfo"].get("name")
                        if orig_spk:
                            translated_spk = translate_speaker(orig_spk, speaker_map)
                            if translated_spk and translated_spk != orig_spk:
                                scene["selectInfo"]["name"] = translated_spk

            target_build_json = os.path.join(build_scn_dir, raw_json_name)
            with open(target_build_json, "w", encoding="utf-8") as out_f:
                if pretty:
                    json.dump(scenario_data, out_f, ensure_ascii=False, indent=2)
                else:
                    json.dump(scenario_data, out_f, ensure_ascii=False, separators=(",", ":"))

            src_resx = os.path.join(SCENARIO_EXTRACTED_DIR, f"{identity}.m.resx.json")
            if os.path.exists(src_resx):
                shutil.copy2(src_resx, os.path.join(build_scn_dir, f"{identity}.m.resx.json"))

            # Also copy to patch directory
            shutil.copy2(target_build_json, os.path.join(patch_scn_dir, raw_json_name))
            if os.path.exists(src_resx):
                shutil.copy2(src_resx, os.path.join(patch_scn_dir, f"{identity}.m.resx.json"))

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
                if pretty:
                    json.dump(sl_data, sf, ensure_ascii=False, indent=2)
                else:
                    json.dump(sl_data, sf, ensure_ascii=False, separators=(",", ":"))

            src_sl_resx = os.path.join(SCENARIO_EXTRACTED_DIR, f"{SCENALIST_FILENAME[:-5]}.resx.json")
            if os.path.exists(src_sl_resx):
                shutil.copy2(src_sl_resx, os.path.join(build_scn_dir, f"{SCENALIST_FILENAME[:-5]}.resx.json"))

            # Also copy to patch directory
            shutil.copy2(target_sl_json, os.path.join(patch_scn_dir, SCENALIST_FILENAME))
            if os.path.exists(src_sl_resx):
                shutil.copy2(src_sl_resx, os.path.join(patch_scn_dir, f"{SCENALIST_FILENAME[:-5]}.resx.json"))

            modified_files.append(SCENALIST_FILENAME)

    print(f"Applied patches for '{lang}': {len(modified_files)} scenario files modified.")
    return modified_files


def build_binaries(lang: str, repatch: bool = False, jobs: Optional[int] = None) -> Dict[str, str]:
    psbuild = get_psbuild_path()
    build_lang_dir = os.path.join(BUILD_DIR, lang)
    build_scn_dir = os.path.join(build_lang_dir, "scenario")
    patch_scn_dir = os.path.join(build_lang_dir, "patch", "scenario")

    modified_files = apply_patches(lang, pretty=False)
    total = len(modified_files)
    worker_count = _resolve_compile_workers(jobs, total)

    print(f"Compiling {total} modified scenario JSONs to binary slices (workers: {worker_count})...")
    if modified_files:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_compile_scenario_slice, psbuild, patch_scn_dir, build_scn_dir, m_file): m_file
                for m_file in modified_files
            }
            completed = 0
            try:
                for future in as_completed(futures):
                    future.result()
                    completed += 1
                    if completed % 50 == 0 or completed == total:
                        print(f"  Compiled {completed}/{total} scenarios...")
            except Exception:
                executor.shutdown(wait=False, cancel_futures=True)
                raise

    ensure_game_binaries()
    patch_motion_dir = os.path.join(build_lang_dir, "patch", "motion")
    os.makedirs(patch_motion_dir, exist_ok=True)
    shutil.copy2(MOTION_MAIN_PATH, os.path.join(patch_motion_dir, MOTION_MAIN_FILENAME))

    print("Building patch archive (patch_info.psb.m & patch_body.bin)...")
    patch_info_json = {
        "expire_suffix_list": [".psb.m"],
        "file_info": {},
    }
    patch_info_resx = {
        "PsbVersion": 2,
        "PsbType": "ArchiveInfo",
        "Platform": "none",
        "CryptKey": None,
        "ExternalTextures": False,
        "Context": {
            "MdfKeyLength": MDF_KEY_LEN,
            "FileName": PATCH_INFOPSB_FILENAME,
            "MdfKey": f"{MDF_KEY}{PATCH_INFOPSB_FILENAME}",
            "PsbZlibFastCompress": False,
            "PsbShellType": "MDF",
            "ArchiveSource": ["patch"],
            "MdfMtKey": MDF_KEY,
            "ArchiveItemFileNames": [],
            "BodyBinName": PATCH_BODY_FILENAME,
        },
        "Resources": None,
    }

    patch_info_json_path = os.path.join(build_lang_dir, f"{PATCH_INFOPSB_FILENAME}.json")
    patch_info_resx_path = os.path.join(build_lang_dir, f"{PATCH_INFOPSB_FILENAME}.resx.json")
    with open(patch_info_json_path, "w", encoding="utf-8") as f:
        json.dump(patch_info_json, f, indent=2)
    with open(patch_info_resx_path, "w", encoding="utf-8") as f:
        json.dump(patch_info_resx, f, indent=2)

    pack_patch_cmd = [
        psbuild,
        "info-psb",
        "-k",
        MDF_KEY,
        "-l",
        str(MDF_KEY_LEN),
        "-b",
        PATCH_BODY_FILENAME,
        "-o",
        build_lang_dir,
        patch_info_json_path,
    ]
    pack_res = subprocess.run(pack_patch_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if pack_res.returncode != 0:
        raise RuntimeError(f"Failed to pack patch archive:\n{pack_res.stderr}")

    out_patch_body = os.path.join(build_lang_dir, PATCH_BODY_FILENAME)
    out_patch_info = os.path.join(build_lang_dir, PATCH_INFOPSB_FILENAME)

    if not os.path.exists(out_patch_body) or not os.path.exists(out_patch_info):
        raise FileNotFoundError(f"Expected patch binaries not found in {build_lang_dir}")

    out_script_body = os.path.join(build_lang_dir, SCRIPT_BODY_FILENAME)
    out_script_info = os.path.join(build_lang_dir, SCRIPT_INFOPSB_FILENAME)
    shutil.copy2(SCRIPT_BODY_PATH, out_script_body)
    shutil.copy2(SCRIPT_INFOPSB_PATH, out_script_info)

    artifacts = {
        "patch_body": out_patch_body,
        "patch_info": out_patch_info,
        "script_body": out_script_body,
        "script_info": out_script_info,
    }

    # Standalone patch zip (contains patch_* and script_*)
    patch_zip_path = os.path.join(build_lang_dir, f"wonderful-party-patch-{lang}.zip")
    with zipfile.ZipFile(patch_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_patch_body, PATCH_BODY_FILENAME)
        zf.write(out_patch_info, PATCH_INFOPSB_FILENAME)
        zf.write(out_script_body, SCRIPT_BODY_FILENAME)
        zf.write(out_script_info, SCRIPT_INFOPSB_FILENAME)
    artifacts["zip_patch"] = patch_zip_path

    # rePatch zip (Option B: full scenario_body.bin & scenario_info.psb.m)
    if repatch:
        print("Repacking full scenario archive for rePatch (scenario_info.psb.m & scenario_body.bin)...")
        info_json_path = os.path.join(build_lang_dir, f"{SCENARIO_INFOPSB_FILENAME}.json")
        pack_scenario_cmd = [
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
        pack_res = subprocess.run(pack_scenario_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if pack_res.returncode != 0:
            raise RuntimeError(f"Failed to pack scenario archive:\n{pack_res.stderr}")

        out_scenario_body = os.path.join(build_lang_dir, SCENARIO_BODY_FILENAME)
        out_scenario_info = os.path.join(build_lang_dir, SCENARIO_INFOPSB_FILENAME)
        artifacts["scenario_body"] = out_scenario_body
        artifacts["scenario_info"] = out_scenario_info

        repatch_zip_path = os.path.join(build_lang_dir, f"wonderful-party-repatch-{lang}.zip")
        with zipfile.ZipFile(repatch_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            arc_body = f"rePatch/{TITLE_ID}/{SCENARIO_BODY_FILENAME}"
            arc_info = f"rePatch/{TITLE_ID}/{SCENARIO_INFOPSB_FILENAME}"
            zf.write(out_scenario_body, arc_body)
            zf.write(out_scenario_info, arc_info)
        artifacts["zip_repatch"] = repatch_zip_path

    print(f"Build complete for '{lang}'!")
    for k, v in artifacts.items():
        print(f"  {k}: {v} ({os.path.getsize(v):,} bytes)")

    return artifacts
