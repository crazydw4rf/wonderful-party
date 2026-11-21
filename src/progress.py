import json
import os
from typing import Any, Dict

from .constants import (
    BADGES_DIR,
    PATCHES_DIR,
    PROGRESS_FILE,
    SCENALIST_FILENAME,
    SPEAKERS_FILENAME,
    STATUS_MACHINE_TRANSLATED,
    STATUS_PROOFREAD,
    STATUS_UNTRANSLATED,
    SUPPORTED_LANGUAGES,
)


def get_badge_color(percentage: float) -> str:
    if percentage >= 100.0:
        return "brightgreen"
    if percentage >= 80.0:
        return "green"
    if percentage >= 60.0:
        return "yellowgreen"
    if percentage >= 40.0:
        return "yellow"
    if percentage >= 20.0:
        return "orange"
    return "red"


def analyze_language_progress(lang: str) -> Dict[str, Any]:
    lang_dir = os.path.join(PATCHES_DIR, lang)
    if not os.path.exists(lang_dir):
        return {}

    total_dialogues = 0
    dialogues_proofread = 0
    dialogues_mtl = 0
    dialogues_untranslated = 0

    total_choices = 0
    choices_translated = 0

    total_prompts = 0
    prompts_translated = 0

    total_titles = 0
    titles_translated = 0

    route_stats: Dict[str, Dict[str, int]] = {}

    files = sorted(os.listdir(lang_dir))
    for fname in files:
        if not fname.endswith(".json"):
            continue

        fpath = os.path.join(lang_dir, fname)
        with open(fpath, "r", encoding="utf-8") as pf:
            data = json.load(pf)

        if fname == SPEAKERS_FILENAME:
            continue

        if fname in ("scenelist.scn.json", f"{SCENALIST_FILENAME[:-7]}.json"):
            for t_info in data.get("titles", {}).values():
                total_titles += 1
                if t_info.get("translation"):
                    titles_translated += 1
            for c_info in data.get("choices", {}).values():
                total_choices += 1
                if c_info.get("translation"):
                    choices_translated += 1
            continue

        prefix = fname.split("_")[0] if "_" in fname else "other"
        if prefix not in route_stats:
            route_stats[prefix] = {
                "total_dialogues": 0,
                "proofread": 0,
                "mtl": 0,
                "untranslated": 0,
            }

        for scene in data.get("scenes", {}).values():
            texts = scene.get("texts", {})
            for t_entry in texts.values():
                total_dialogues += 1
                route_stats[prefix]["total_dialogues"] += 1
                status = t_entry.get("status", STATUS_UNTRANSLATED)
                trans = t_entry.get("translation", "").strip()

                if not trans:
                    dialogues_untranslated += 1
                    route_stats[prefix]["untranslated"] += 1
                elif status == STATUS_PROOFREAD:
                    dialogues_proofread += 1
                    route_stats[prefix]["proofread"] += 1
                elif status == STATUS_MACHINE_TRANSLATED:
                    dialogues_mtl += 1
                    route_stats[prefix]["mtl"] += 1
                else:
                    dialogues_untranslated += 1
                    route_stats[prefix]["untranslated"] += 1

            prompt = scene.get("select_prompt")
            if prompt:
                total_prompts += 1
                if prompt.get("translation"):
                    prompts_translated += 1

            choices = scene.get("choices", {})
            for c_entry in choices.values():
                total_choices += 1
                if c_entry.get("translation"):
                    choices_translated += 1

    speakers_file = os.path.join(lang_dir, SPEAKERS_FILENAME)
    total_speakers = 0
    speakers_translated = 0
    if os.path.exists(speakers_file):
        try:
            with open(speakers_file, "r", encoding="utf-8") as f:
                spk_data = json.load(f)
            total_speakers = len(spk_data)
            speakers_translated = sum(
                1 for v in spk_data.values() if (v if isinstance(v, str) else v.get("translation", "")).strip()
            )
        except Exception:
            pass

    translated_dialogues = dialogues_proofread + dialogues_mtl
    dialogue_percent = (translated_dialogues / total_dialogues * 100.0) if total_dialogues > 0 else 0.0
    proofread_percent = (dialogues_proofread / total_dialogues * 100.0) if total_dialogues > 0 else 0.0

    return {
        "language": lang,
        "language_name": SUPPORTED_LANGUAGES.get(lang, lang),
        "dialogues": {
            "total": total_dialogues,
            "translated": translated_dialogues,
            "proofread": dialogues_proofread,
            "machine_translated": dialogues_mtl,
            "untranslated": dialogues_untranslated,
            "percent_translated": round(dialogue_percent, 2),
            "percent_proofread": round(proofread_percent, 2),
        },
        "choices": {
            "total": total_choices,
            "translated": choices_translated,
        },
        "prompts": {
            "total": total_prompts,
            "translated": prompts_translated,
        },
        "titles": {
            "total": total_titles,
            "translated": titles_translated,
        },
        "speakers": {
            "total": total_speakers,
            "translated": speakers_translated,
        },
        "routes": route_stats,
    }


def update_progress_and_badges() -> Dict[str, Any]:
    os.makedirs(BADGES_DIR, exist_ok=True)
    all_progress: Dict[str, Any] = {}

    for lang in SUPPORTED_LANGUAGES:
        stats = analyze_language_progress(lang)
        if not stats:
            continue
        all_progress[lang] = stats

        d_stats = stats["dialogues"]
        pct = d_stats["percent_translated"]
        pf_pct = d_stats["percent_proofread"]

        # Shields.io endpoint badge schema
        badge_data = {
            "schemaVersion": 1,
            "label": stats["language_name"],
            "message": f"{pct}% (proofread: {pf_pct}%)",
            "color": get_badge_color(pct),
        }

        badge_path = os.path.join(BADGES_DIR, f"{lang}.json")
        with open(badge_path, "w", encoding="utf-8") as bf:
            json.dump(badge_data, bf, ensure_ascii=False, indent=2)

    with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
        json.dump(all_progress, pf, ensure_ascii=False, indent=2)

    print_progress_report(all_progress)
    return all_progress


def print_progress_report(all_progress: Dict[str, Any]):
    print("\n=======================================================")
    print("        WONDERFUL PARTY TRANSLATION PROGRESS")
    print("=======================================================")

    for lang, stats in all_progress.items():
        d = stats["dialogues"]
        pct = d["percent_translated"]
        bar_len = 30
        filled = int(round(bar_len * pct / 100))
        bar = "#" * filled + "-" * (bar_len - filled)

        print(f"\nLanguage: {stats['language_name']} ({lang})")
        print(f"[{bar}] {pct:.1f}%")
        print(f"  Total Dialogues : {d['total']:,}")
        print(f"  Proofread       : {d['proofread']:,} ({d['percent_proofread']}%)")
        print(f"  Machine Trans   : {d['machine_translated']:,}")
        print(f"  Untranslated    : {d['untranslated']:,}")
        print(f"  Choices Trans   : {stats['choices']['translated']}/{stats['choices']['total']}")
        print(f"  Titles Trans    : {stats['titles']['translated']}/{stats['titles']['total']}")
        print(f"  Speakers Trans  : {stats['speakers']['translated']}/{stats['speakers']['total']}")

        print("\n  Route Breakdown (Dialogues):")
        for r_name, r_stat in sorted(stats.get("routes", {}).items()):
            r_tot = r_stat["total_dialogues"]
            r_done = r_stat["proofread"] + r_stat["mtl"]
            r_pct = (r_done / r_tot * 100) if r_tot > 0 else 0
            print(f"    {r_name:12}: {r_done:5}/{r_tot:5} ({r_pct:5.1f}%) [PR: {r_stat['proofread']}, MTL: {r_stat['mtl']}]")

    print("\n=======================================================\n")
