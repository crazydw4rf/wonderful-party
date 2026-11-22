import os

TITLE_ID = "PCSG00786"
MDF_KEY = "a23e898ef1032"
MDF_KEY_LEN = 131

SCENARIO_BODY_FILENAME = "scenario_body.bin"
SCENARIO_INFOPSB_FILENAME = "scenario_info.psb.m"
PATCH_BODY_FILENAME = "patch_body.bin"
PATCH_INFOPSB_FILENAME = "patch_info.psb.m"
SCRIPT_BODY_FILENAME = "script_body.bin"
SCRIPT_INFOPSB_FILENAME = "script_info.psb.m"
SCENALIST_FILENAME = "scenelist.scn.m.json"
SPEAKERS_FILENAME = "speakers.json"

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.join(ROOT_DIR, "workspace")
TOOLS_DIR = os.path.join(WORKSPACE_DIR, "tools")
CACHE_DIR = os.path.join(WORKSPACE_DIR, "cache")
RAW_DIR = os.path.join(WORKSPACE_DIR, "raw")
OUT_EXTRACTED_DIR = os.path.join(WORKSPACE_DIR, "extracted")
SCENARIO_EXTRACTED_DIR = os.path.join(OUT_EXTRACTED_DIR, "scenario")
BUILD_DIR = os.path.join(WORKSPACE_DIR, "build")

PATCHES_DIR = os.path.join(ROOT_DIR, "patches")
BADGES_DIR = os.path.join(ROOT_DIR, "badges")
PROGRESS_FILE = os.path.join(ROOT_DIR, "progress.json")

SCENARIO_BODY_PATH = os.path.join(WORKSPACE_DIR, SCENARIO_BODY_FILENAME)
SCENARIO_INFOPSB_PATH = os.path.join(WORKSPACE_DIR, SCENARIO_INFOPSB_FILENAME)
SCRIPT_BODY_PATH = os.path.join(WORKSPACE_DIR, SCRIPT_BODY_FILENAME)
SCRIPT_INFOPSB_PATH = os.path.join(WORKSPACE_DIR, SCRIPT_INFOPSB_FILENAME)
INFOPSB_JSON_PATH = os.path.join(OUT_EXTRACTED_DIR, f"{SCENARIO_INFOPSB_FILENAME}.json")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "id": "Bahasa Indonesia",
}

STATUS_UNTRANSLATED = "untranslated"
STATUS_MACHINE_TRANSLATED = "machine_translated"
STATUS_PROOFREAD = "proofread"
VALID_STATUSES = {STATUS_UNTRANSLATED, STATUS_MACHINE_TRANSLATED, STATUS_PROOFREAD}

FREEMOTE_DOWNLOAD_URL = {
    "linux": {
        "file_name": "FreeMote-Linux-x64.zip",
        "download_url": "https://github.com/crazydw4rf/FreeMote/releases/download/v4.9.5/FreeMote-Linux-x64.zip",
    },
    "windows": {
        "file_name": "FreeMote-Windows.zip",
        "download_url": "https://github.com/crazydw4rf/FreeMote/releases/download/v4.9.5/FreeMote-Windows.zip",
    },
}

GAME_SCENARIO_FILE_URL = {
    SCENARIO_BODY_FILENAME: "https://files.catbox.moe/eouffa.bin",
    SCENARIO_INFOPSB_FILENAME: "https://files.catbox.moe/pl12v0.m",
}

GAME_SCRIPT_FILE_URL = {
    SCRIPT_BODY_FILENAME: "https://files.catbox.moe/ipymuw.bin",
    SCRIPT_INFOPSB_FILENAME: "https://files.catbox.moe/tq1dtt.m",
}
