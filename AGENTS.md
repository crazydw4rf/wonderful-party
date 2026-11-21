# AGENTS.md

## Project Overview

Fan translation project for *Gochuumon wa Usagi Desu ka?? Wonderful Party!* (PS Vita, Title ID: `PCSG00786`).
The game uses M2's E-mote / PSB engine with MDF (Mersenne Twister encrypted Zlib) shell compression.

## Architecture

- **Game Archive**: `scenario_body.bin` (data payload) and `scenario_info.psb.m` (archive catalog).
- **Tools**: FreeMote (`PsbDecompile` and `PsBuild`) in `workspace/tools/`.
- **Extraction**:
  - `workspace/extracted/scenario/` contains 501 decompiled AST JSON files (`*.scn.m.json`) and `.resx.json` sidecars.
  - `workspace/raw/scenario/` contains 501 pre-extracted binary slices used for ultra-fast incremental repacking.
- **Patches**: Small, semantic JSON patches stored in `patches/{lang}/{scenario_id}.scn.json`.
- **Build Output**: Patched game binaries in `workspace/build/{lang}/` and rePatch zip bundles.

## Key Constants

- **Title ID**: `PCSG00786`
- **MDF Key**: `a23e898ef1032`
- **MDF Key Length**: `131`
- **Total Dialogues**: 17,569 lines
- **Total Choices**: 471 choices across 131 prompts
- **Scenelist Titles**: 1,012 translatable story titles

## Patch File Schema

Each scenario patch file is named `{scenario_id}.json` (e.g. `chiya_a08.txt.scn.json`):

```json
{
  "identity": "chiya_a08.txt.scn",
  "scenes": {
    "*dummy1": {
      "texts": {
        "0": {
          "speaker": "ココア",
          "original": "う～ん……。",
          "translation": "Hmm......",
          "status": "proofread"
        }
      },
      "select_prompt": {
        "speaker": "チノ",
        "original": "prompt text",
        "translation": "translated prompt",
        "status": "machine_translated"
      },
      "choices": {
        "*sel_0101": {
          "original": "choice text",
          "translation": "translated choice",
          "status": "proofread"
        }
      }
    }
  }
}
```

### Valid Status Values
- `untranslated`: Default, translation is empty or not yet reviewed.
- `machine_translated`: Translated via automated translation (MTL).
- `proofread`: Reviewed and verified by a human translator.

## Scenelist Patch (`scenelist.scn.json`)

Stores story chapter titles and choice mirrors:
- `titles`: Keyed by `storage#target` (e.g. `all_a01.txt#*branch_0101`).
- `choices`: Keyed by `storage#target` (e.g. `all_a01.txt#*sel_0101`).
Choice translations in scenario files are automatically synchronized into `scenelist` during `cli.py apply` and `cli.py build`.

## CLI Commands

```bash
python cli.py setup                 # Bootstrap FreeMote tools and extract scenario data
python cli.py extract <lang>        # Extract or sync patch templates from extracted JSONs
python cli.py validate [lang]       # Validate patch syntax and original text integrity
python cli.py apply <lang>          # Overlay patches onto staging workspace
python cli.py build <lang> [--repatch] # Compile modified scenarios and pack release archives
python cli.py progress              # Recalculate translation stats and update badges
```

## Agent Guidelines

1. **Never commit game binaries or workspace files**: Only files in `patches/`, `badges/`, `src/`, or root docs should be committed.
2. **Preserve the `original` field**: The validator verifies that `original` matches the decompiled Japanese script.
3. **Keep `status` accurate**: When adding translations, mark them as `machine_translated` or `proofread`.
4. **Never edit `.resx.json` files directly**: FreeMote uses these sidecars for crypto keys and compression flags.
5. **Always validate before committing**: Run `python cli.py validate` to ensure zero syntax or schema regressions.
