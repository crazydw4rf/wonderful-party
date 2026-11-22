# Wonderful Party Translation Project

A fan translation patch project for the PlayStation Vita game:
[Gochuumon wa Usagi Desu ka?? Wonderful Party!](https://vndb.org/v18457) (ご注文はうさぎですか？？ Wonderful Party!).

## Translation Progress

| Language | Status Badge | Progress |
| :--- | :--- | :--- |
| **English** | [![English Translation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/crazydw4rf/wonderful-party/main/badges/en.json)](https://github.com/crazydw4rf/wonderful-party) | Dialogue & Choices |
| **Bahasa Indonesia** | [![Indonesian Translation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/crazydw4rf/wonderful-party/main/badges/id.json)](https://github.com/crazydw4rf/wonderful-party) | Dialogue & Choices |

> [!NOTE]
> Translations are managed via compact, Git-friendly JSON patch files. Both machine translation and human proofreading are tracked.

---

## Playing with Translation Patch (PS Vita)

### Method 1: Game Directory Patch (Vita / Vita3K)
1. Download the latest `wonderful-party-patch-{lang}.zip` from the [Releases](https://github.com/crazydw4rf/wonderful-party/releases) page.
2. Extract the files (`patch_body.bin`, `patch_info.psb.m`, `script_body.bin`, `script_info.psb.m`) directly into your game directory:
   - On PS Vita: `ux0:app/PCSG00786/`
   - On Vita3K: `<Vita3K-pref-path>/ux0/app/PCSG00786/`
3. Launch the game.

### Method 2: Using rePatch
1. Ensure your PS Vita is running Henkaku/Enso with the [rePatch reLoaded](https://github.com/SonicMastr/rePatch-reLoaded) plugin installed.
2. Download the latest `wonderful-party-repatch-{lang}.zip` from the [Releases](https://github.com/crazydw4rf/wonderful-party/releases) page.
3. Extract the zip archive directly to the root of your Vita storage (`ux0:`).
   The files will extract to:
   ```text
   ux0:rePatch/PCSG00786/scenario_body.bin
   ux0:rePatch/PCSG00786/scenario_info.psb.m
   ```
4. Launch the game from LiveArea.

---

## Contributing to Translations

Anyone is welcome to contribute translations! The project is designed so that multiple people can work on different routes without Git merge conflicts.

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/crazydw4rf/wonderful-party.git
cd wonderful-party

# 2. Bootstrap the workspace (downloads tools and extracts scenarios)
python cli.py setup

# 3. Edit translation patches in patches/en/ or patches/id/
# Open any scenario patch (e.g. patches/en/chino_a01.txt.scn.json)

# 4. Validate your patch
python cli.py validate en

# 5. Test build locally (produces runnable binaries in workspace/build/en/)
python cli.py build en --repatch

# 6. Update progress statistics
python cli.py progress
```

For complete contributor details, see [CONTRIBUTING.md](CONTRIBUTING.md).
For agentic contributors and LLMs, see [AGENTS.md](AGENTS.md).

---

## CLI Reference

```text
usage: cli.py [-h] {setup,extract,validate,apply,build,progress,list} ...

Available subcommands:
  setup               Bootstrap workspace tools and extract game binaries
  extract <lang>      Extract/sync patch templates from scenario data
  validate [lang]     Validate patch syntax, schema, and original text integrity
  apply <lang>        Apply patch files to staging workspace
  build <lang>        Build patched binaries (and optional --repatch zip)
  progress            Calculate progress statistics and update Shields.io badges
  list [lang]         List per-scenario translation progress (interactive TUI/pager)
```

---

## Credits

Thanks to [UlyssesWu/FreeMote](https://github.com/UlyssesWu/FreeMote), which makes
PSB archive manipulation and this project possible.
