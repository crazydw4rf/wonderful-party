# Contributing to Wonderful Party Translation Project

Thank you for your interest in translating *Gochuumon wa Usagi Desu ka?? Wonderful Party!* into English or Bahasa Indonesia!

## Prerequisites

- **Python**: Version 3.10+ (tested with Python 3.13)
- **.NET SDK / Runtime**: Required for FreeMote tool execution (typically pre-installed on modern systems or easily installed via your package manager)
- **Git**

## Quick Start (Bootstrap Workspace)

Clone the repository and set up your local workspace:

```bash
git clone https://github.com/crazydw4rf/wonderful-party.git
cd wonderful-party

# Automatically downloads FreeMote tools and extracts game scenario binaries
python cli.py setup
```

The `setup` command downloads the game binaries into `./workspace/` (which is gitignored) and decompiles the 501 scenario scripts.

## How to Translate

1. **Pick a scenario file or route**:
   Scenario patches live in `patches/{lang}/`:
   - `patches/en/` for English
   - `patches/id/` for Bahasa Indonesia

   File prefixes indicate routes:
   - `all_*.scn.json`: Common route
   - `chino_*.scn.json`: Chino route
   - `cocoa_*.scn.json`: Cocoa route
   - `rize_*.scn.json`: Rize route
   - `chiya_*.scn.json`: Chiya route
   - `syaro_*.scn.json`: Syaro route
   - `flyer_*.scn.json`: Flyer distribution events
   - `visit_*.scn.json`: Visiting events
   - `pajamas_*.scn.json`: Pajama party events

2. **Edit the patch file**:
   Open any scenario patch file (e.g. `patches/en/chino_a01.txt.scn.json`).
   Fill in the `"translation"` string and update the `"status"`:

   ```json
   "0": {
     "speaker": "ココア",
     "original": "う～ん……。",
     "translation": "Hmm......",
     "status": "proofread"
   }
   ```

   - Set `"status": "proofread"` if reviewed by a human.
   - Set `"status": "machine_translated"` if using DeepL/ChatGPT/LLM.
   - Do NOT edit the `"original"` or `"speaker"` fields.

3. **Validate your changes**:
   Run the validator to verify syntax and text integrity:

   ```bash
   python cli.py validate en
   ```

4. **Test-build your patch (Optional but Recommended)**:
   You can build the patched game binaries locally:

   ```bash
   python cli.py build en --repatch
   ```

   This produces:
   - `workspace/build/en/wonderful-party-repatch-en.zip` (for PS Vita `rePatch`)
   - `workspace/build/en/wonderful-party-binaries-en.zip` (standalone)

5. **Update progress stats**:
   ```bash
   python cli.py progress
   ```

6. **Submit a Pull Request**:
   Commit only your updated files in `patches/{lang}/` (and `badges/` if updated):

   ```bash
   git add patches/en/
   git commit -m "feat(translation): translate chino_a01 route to english"
   git push origin my-translation-branch
   ```

   Open a Pull Request on GitHub. Reviewers will see the clean side-by-side diff of your translations!
