import os
import stat
import subprocess
import tarfile
import urllib.request
import zipfile
from sys import platform

from .constants import (
    CACHE_DIR,
    FREEMOTE_DOWNLOAD_URL,
    GAME_SCENARIO_FILE_URL,
    INFOPSB_JSON_PATH,
    MDF_KEY,
    OUT_EXTRACTED_DIR,
    RAW_DIR,
    SCENARIO_BODY_FILENAME,
    SCENARIO_BODY_PATH,
    SCENARIO_EXTRACTED_DIR,
    SCENARIO_INFOPSB_FILENAME,
    SCENARIO_INFOPSB_PATH,
    TOOLS_DIR,
    WORKSPACE_DIR,
)


def get_tool_executable(name: str) -> str:
    ext = ".exe" if platform == "win32" else ""
    return os.path.join(TOOLS_DIR, f"{name}{ext}")


def get_psbuild_path() -> str:
    return get_tool_executable("PsBuild")


def get_psbdecompile_path() -> str:
    return get_tool_executable("PsbDecompile")


def download_file(url: str, file_name: str, out_dir: str = ".") -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, file_name)

    print(f"Downloading '{file_name}' from {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(out_path, "wb") as out_file:
        while chunk := resp.read(65536):
            out_file.write(chunk)

    print(f"Downloaded '{file_name}' ({os.path.getsize(out_path):,} bytes).")
    return out_path


def unpack_archive(archive_path: str, extract_dir: str):
    os.makedirs(extract_dir, exist_ok=True)
    print(f"Extracting '{os.path.basename(archive_path)}' to '{extract_dir}'...")

    if archive_path.endswith(".tar.gz") or archive_path.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)
    elif archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_dir)
    else:
        raise ValueError(f"Unsupported archive format: {archive_path}")


def ensure_freemote_tools():
    psbuild = get_psbuild_path()
    psbdecompile = get_psbdecompile_path()

    if os.path.exists(psbuild) and os.path.exists(psbdecompile):
        return

    os.makedirs(TOOLS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    plat_key = "windows" if platform == "win32" else "linux"
    dl_info = FREEMOTE_DOWNLOAD_URL.get(plat_key, FREEMOTE_DOWNLOAD_URL["linux"])
    cached_archive = os.path.join(CACHE_DIR, dl_info["file_name"])

    if not os.path.exists(cached_archive):
        download_file(dl_info["download_url"], dl_info["file_name"], CACHE_DIR)

    unpack_archive(cached_archive, TOOLS_DIR)

    if platform != "win32":
        for root, _, files in os.walk(TOOLS_DIR):
            for fname in files:
                fpath = os.path.join(root, fname)
                if not fname.endswith(".dll") and not fname.endswith(".json") and not fname.endswith(".config") and not fname.endswith(".txt"):
                    current_mode = os.stat(fpath).st_mode
                    os.chmod(fpath, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ensure_game_binaries():
    os.makedirs(WORKSPACE_DIR, exist_ok=True)

    if not os.path.exists(SCENARIO_BODY_PATH):
        download_file(
            GAME_SCENARIO_FILE_URL[SCENARIO_BODY_FILENAME],
            SCENARIO_BODY_FILENAME,
            WORKSPACE_DIR,
        )

    if not os.path.exists(SCENARIO_INFOPSB_PATH):
        download_file(
            GAME_SCENARIO_FILE_URL[SCENARIO_INFOPSB_FILENAME],
            SCENARIO_INFOPSB_FILENAME,
            WORKSPACE_DIR,
        )


def verify_scenario_decompiled() -> bool:
    if not os.path.exists(INFOPSB_JSON_PATH):
        return False
    if not os.path.exists(SCENARIO_EXTRACTED_DIR):
        return False
    scn_files = [f for f in os.listdir(SCENARIO_EXTRACTED_DIR) if f.endswith(".scn.m.json")]
    return len(scn_files) >= 500


def ensure_raw_binaries_extracted():
    raw_scenario_dir = os.path.join(RAW_DIR, "scenario")
    if os.path.exists(raw_scenario_dir) and len(os.listdir(raw_scenario_dir)) >= 500:
        return

    print("Extracting raw scenario binary slices...")
    psbdecompile = get_psbdecompile_path()
    cmd = [
        psbdecompile,
        "info-psb",
        "-k",
        MDF_KEY,
        "--infer-key-length",
        "-raw",
        SCENARIO_INFOPSB_PATH,
        "-o",
        RAW_DIR,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Raw extraction failed (code {res.returncode}):\n{res.stderr}")


def decompile_scenario():
    print("Decompiling scenario archive with FreeMote...")
    psbdecompile = get_psbdecompile_path()
    cmd = [
        psbdecompile,
        "info-psb",
        "-k",
        MDF_KEY,
        "--infer-key-length",
        "-a",
        SCENARIO_INFOPSB_PATH,
        "-o",
        OUT_EXTRACTED_DIR,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Decompilation failed (code {res.returncode}):\n{res.stderr}")
    print("Decompilation complete.")


def ensure_workspace_setup():
    for d in [WORKSPACE_DIR, TOOLS_DIR, CACHE_DIR, OUT_EXTRACTED_DIR, RAW_DIR]:
        os.makedirs(d, exist_ok=True)

    ensure_freemote_tools()
    ensure_game_binaries()
    ensure_raw_binaries_extracted()

    if not verify_scenario_decompiled():
        decompile_scenario()

    print("Workspace is ready.")
