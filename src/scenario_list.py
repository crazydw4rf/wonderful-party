import curses
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .constants import (
    PATCHES_DIR,
    SCENALIST_FILENAME,
    SPEAKERS_FILENAME,
    STATUS_MACHINE_TRANSLATED,
    STATUS_PROOFREAD,
    STATUS_UNTRANSLATED,
    SUPPORTED_LANGUAGES,
)


def parse_file_stats(filepath: str, is_scenelist: bool = False) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if is_scenelist:
        titles = data.get("titles", {})
        choices = data.get("choices", {})
        total = len(titles) + len(choices)
        translated = sum(1 for t in titles.values() if t.get("translation", "").strip())
        translated += sum(
            1 for c in choices.values() if c.get("translation", "").strip()
        )
        proofread = sum(
            1
            for t in titles.values()
            if t.get("status") == STATUS_PROOFREAD and t.get("translation", "").strip()
        )
        proofread += sum(
            1
            for c in choices.values()
            if c.get("status") == STATUS_PROOFREAD and c.get("translation", "").strip()
        )
        mtl = sum(
            1
            for t in titles.values()
            if t.get("status") == STATUS_MACHINE_TRANSLATED
            and t.get("translation", "").strip()
        )
        mtl += sum(
            1
            for c in choices.values()
            if c.get("status") == STATUS_MACHINE_TRANSLATED
            and c.get("translation", "").strip()
        )
        untranslated = total - translated
        pct = (translated / total * 100.0) if total > 0 else 0.0
        pf_pct = (proofread / total * 100.0) if total > 0 else 0.0
        return {
            "total": total,
            "translated": translated,
            "proofread": proofread,
            "mtl": mtl,
            "untranslated": untranslated,
            "percent": pct,
            "percent_proofread": pf_pct,
            "choices_total": len(choices),
            "choices_translated": sum(
                1 for c in choices.values() if c.get("translation", "").strip()
            ),
            "prompts_total": 0,
            "prompts_translated": 0,
        }

    total = 0
    proofread = 0
    mtl = 0
    untranslated = 0
    choices_total = 0
    choices_trans = 0
    prompts_total = 0
    prompts_trans = 0

    for scene in data.get("scenes", {}).values():
        for text in scene.get("texts", {}).values():
            total += 1
            st = text.get("status", STATUS_UNTRANSLATED)
            tr = text.get("translation", "").strip()
            if not tr:
                untranslated += 1
            elif st == STATUS_PROOFREAD:
                proofread += 1
            elif st == STATUS_MACHINE_TRANSLATED:
                mtl += 1
            else:
                untranslated += 1

        prompt = scene.get("select_prompt")
        if prompt:
            prompts_total += 1
            if prompt.get("translation", "").strip():
                prompts_trans += 1

        for choice in scene.get("choices", {}).values():
            choices_total += 1
            if choice.get("translation", "").strip():
                choices_trans += 1

    translated = proofread + mtl
    pct = (translated / total * 100.0) if total > 0 else 0.0
    pf_pct = (proofread / total * 100.0) if total > 0 else 0.0

    return {
        "total": total,
        "translated": translated,
        "proofread": proofread,
        "mtl": mtl,
        "untranslated": untranslated,
        "percent": pct,
        "percent_proofread": pf_pct,
        "choices_total": choices_total,
        "choices_translated": choices_trans,
        "prompts_total": prompts_total,
        "prompts_translated": prompts_trans,
    }


def get_all_scenarios_stats() -> List[Dict[str, Any]]:
    en_dir = os.path.join(PATCHES_DIR, "en")
    id_dir = os.path.join(PATCHES_DIR, "id")

    files = sorted(
        f for f in os.listdir(en_dir) if f.endswith(".json") and f != SPEAKERS_FILENAME
    )

    stats_list = []
    for fname in files:
        is_scenelist = fname in ("scenelist.scn.json", SCENALIST_FILENAME)
        scenario_id = fname.replace(".json", "")

        en_path = os.path.join(en_dir, fname)
        en_stats = (
            parse_file_stats(en_path, is_scenelist) if os.path.exists(en_path) else None
        )

        id_path = os.path.join(id_dir, fname)
        id_stats = (
            parse_file_stats(id_path, is_scenelist) if os.path.exists(id_path) else None
        )

        if "_" in fname:
            route = fname.split("_")[0]
        elif is_scenelist or ".ks." in fname:
            route = "system"
        else:
            route = "other"

        stats_list.append(
            {
                "filename": fname,
                "scenario_id": scenario_id,
                "route": route,
                "is_scenelist": is_scenelist,
                "en": en_stats,
                "id": id_stats,
            }
        )

    return stats_list


def filter_and_sort_scenarios(
    scenarios: List[Dict[str, Any]],
    search_query: str = "",
    sort_by: str = "name",
    lang_mode: Optional[str] = None,
    filter_status: str = "all",
    filter_route: str = "all",
) -> List[Dict[str, Any]]:
    filtered = scenarios

    if filter_route != "all":
        filtered = [s for s in filtered if s["route"] == filter_route]

    if search_query:
        q = search_query.lower()
        filtered = [
            s
            for s in filtered
            if q in s["scenario_id"].lower()
            or q in s["route"].lower()
            or (lang_mode and f"{s.get(lang_mode, {}).get('percent', 0):.0f}%" in q)
        ]

    if filter_status == "untranslated":
        if lang_mode:
            filtered = [s for s in filtered if s[lang_mode]["percent"] < 100.0]
        else:
            filtered = [
                s
                for s in filtered
                if s["en"]["percent"] < 100.0 or s["id"]["percent"] < 100.0
            ]
    elif filter_status == "completed":
        if lang_mode:
            filtered = [s for s in filtered if s[lang_mode]["percent"] >= 100.0]
        else:
            filtered = [
                s
                for s in filtered
                if s["en"]["percent"] >= 100.0 and s["id"]["percent"] >= 100.0
            ]

    if sort_by == "progress-desc":
        key_fn = lambda s: (
            s[lang_mode]["percent"]
            if lang_mode
            else max(s["en"]["percent"], s["id"]["percent"])
        )
        filtered = sorted(filtered, key=key_fn, reverse=True)
    elif sort_by == "progress-asc":
        key_fn = lambda s: (
            s[lang_mode]["percent"]
            if lang_mode
            else min(s["en"]["percent"], s["id"]["percent"])
        )
        filtered = sorted(filtered, key=key_fn)
    elif sort_by == "lines-desc":
        key_fn = lambda s: (
            s[lang_mode]["total"]
            if lang_mode
            else max(s["en"]["total"], s["id"]["total"])
        )
        filtered = sorted(filtered, key=key_fn, reverse=True)
    else:
        filtered = sorted(filtered, key=lambda s: s["scenario_id"])

    return filtered


def colorize_pct(pct: float, text: str, use_ansi: bool = True) -> str:
    if not use_ansi:
        return text
    if pct >= 100.0:
        return f"\033[92m{text}\033[0m"  # Green
    if pct >= 50.0:
        return f"\033[93m{text}\033[0m"  # Yellow
    if pct > 0.0:
        return f"\033[33m{text}\033[0m"  # Orange/Dark Yellow
    return f"\033[90m{text}\033[0m"  # Dim / Gray


def format_table(
    scenarios: List[Dict[str, Any]],
    lang_mode: Optional[str] = None,
    use_ansi: bool = True,
    search_query: str = "",
    sort_by: str = "name",
) -> str:
    lines = []
    bold = "\033[1m" if use_ansi else ""
    reset = "\033[0m" if use_ansi else ""
    cyan = "\033[96m" if use_ansi else ""

    total_scenarios = len(scenarios)
    tot_lines = sum(s["en"]["total"] for s in scenarios)

    if lang_mode is None:
        header = f"{bold}{'SCENARIO':<28} {'LANG':<5} {'TOTAL':>6}   {'DONE':>5}   {'%':>6}    {'PR':>5}   {'MTL':>5}   {'UNTRANSLATED':>7}{reset}"
        sep = f"{'-' * 28} {'-' * 5} {'-' * 6}   {'-' * 5}   {'-' * 6}    {'-' * 5}   {'-' * 5}   {'-' * 7}"
        lines.append(header)
        lines.append(sep)

        for s in scenarios:
            for l_code in ("en", "id"):
                st = s[l_code]
                pct = st["percent"]
                pct_str = f"{pct:5.1f}%"
                pct_colored = colorize_pct(pct, pct_str, use_ansi)
                l_colored = f"{bold}{l_code}{reset}" if use_ansi else l_code

                row = (
                    f"{cyan}{s['scenario_id']:<28}{reset} "
                    f"{l_colored:<5} "
                    f"{st['total']:>6}   "
                    f"{st['translated']:>5}   "
                    f"{pct_colored}    "
                    f"{st['proofread']:>5}   "
                    f"{st['mtl']:>5}   "
                    f"{st['untranslated']:>7}"
                )
                lines.append(row)

        lines.append(sep)
        for l_code in ("en", "id"):
            tot_done = sum(s[l_code]["translated"] for s in scenarios)
            tot_pr = sum(s[l_code]["proofread"] for s in scenarios)
            tot_mtl = sum(s[l_code]["mtl"] for s in scenarios)
            tot_untrans = sum(s[l_code]["untranslated"] for s in scenarios)
            tot_pct = (tot_done / tot_lines * 100.0) if tot_lines > 0 else 0.0

            l_colored = f"{bold}{l_code}{reset}" if use_ansi else l_code
            tot_str = f"{tot_pct:5.1f}%"
            tot_colored = colorize_pct(tot_pct, tot_str, use_ansi)

            summary_row = (
                f"{bold}{'TOTAL (' + str(total_scenarios) + ' files)':<28} {reset}"
                f"{l_colored:<5} "
                f"{tot_lines:>6}   "
                f"{tot_done:>5}   "
                f"{tot_colored}    "
                f"{tot_pr:>5}   "
                f"{tot_mtl:>5}   "
                f"{tot_untrans:>7}"
            )
            lines.append(summary_row)

    else:
        lm = lang_mode.lower()
        header = f"{bold}{'SCENARIO':<30} {'TOTAL':>6}   {'DONE':>5}   {'%':>6}    {'PR':>5}   {'MTL':>5}   {'UNTRANSLATED':>7}{reset}"
        sep = f"{'-' * 30} {'-' * 6}   {'-' * 5}   {'-' * 6}    {'-' * 5}   {'-' * 5}   {'-' * 7}"
        lines.append(header)
        lines.append(sep)

        for s in scenarios:
            st = s[lm]
            pct = st["percent"]
            pct_str = f"{pct:5.1f}%"
            pct_colored = colorize_pct(pct, pct_str, use_ansi)

            row = (
                f"{cyan}{s['scenario_id']:<30}{reset} "
                f"{st['total']:>6}   "
                f"{st['translated']:>5}   "
                f"{pct_colored}    "
                f"{st['proofread']:>5}   "
                f"{st['mtl']:>5}   "
                f"{st['untranslated']:>7}"
            )
            lines.append(row)

        lines.append(sep)
        tot_done = sum(s[lm]["translated"] for s in scenarios)
        tot_pr = sum(s[lm]["proofread"] for s in scenarios)
        tot_mtl = sum(s[lm]["mtl"] for s in scenarios)
        tot_untrans = sum(s[lm]["untranslated"] for s in scenarios)
        tot_pct = (tot_done / tot_lines * 100.0) if tot_lines > 0 else 0.0

        tot_str = f"{tot_pct:5.1f}%"
        tot_colored = colorize_pct(tot_pct, tot_str, use_ansi)

        summary_row = (
            f"{bold}{'TOTAL (' + str(total_scenarios) + ' files)':<30} {reset}"
            f"{tot_lines:>6}   "
            f"{tot_done:>5}   "
            f"{tot_colored}    "
            f"{tot_pr:>5}   "
            f"{tot_mtl:>5}   "
            f"{tot_untrans:>7}"
        )
        lines.append(summary_row)

    return "\n".join(lines)


def run_pager(text: str):
    is_interactive = sys.stdout.isatty() and os.environ.get("TERM", "") not in (
        "dumb",
        "",
    )
    less_path = shutil.which("less")
    if is_interactive and less_path:
        try:
            subprocess.run(
                [less_path, "-R", "-i", "-M", "-S"], input=text.encode("utf-8")
            )
            return
        except Exception:
            pass

    if is_interactive:
        try:
            import pydoc

            pydoc.pager(text)
            return
        except Exception:
            pass

    print(text)


def safe_addstr(win, y: int, x: int, text: str, attr: int = 0):
    max_y, max_x = win.getmaxyx()
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    text = text[: max_x - x]
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def run_curses_tui(
    scenarios: List[Dict[str, Any]],
    initial_lang: Optional[str] = None,
    initial_search: str = "",
    initial_sort: str = "name",
):
    def tui_loop(stdscr):
        curses.curs_set(0)
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Header
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Subheader / Status
        curses.init_pair(3, curses.COLOR_GREEN, -1)  # 100% complete
        curses.init_pair(4, curses.COLOR_YELLOW, -1)  # In progress
        curses.init_pair(
            5, curses.COLOR_WHITE, curses.COLOR_BLACK
        )  # Untranslated / Dim
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected row
        curses.init_pair(7, curses.COLOR_CYAN, -1)  # Scenario name
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_YELLOW)  # Search input

        lang_modes = [None, "en", "id"]
        lang_idx = 0
        if initial_lang == "en":
            lang_idx = 1
        elif initial_lang == "id":
            lang_idx = 2

        sort_options = ["name", "progress-desc", "progress-asc", "lines-desc"]
        sort_idx = (
            sort_options.index(initial_sort) if initial_sort in sort_options else 0
        )

        search_query = initial_search
        searching = False
        search_buffer = ""

        cursor_idx = 0
        scroll_offset = 0

        while True:
            max_y, max_x = stdscr.getmaxyx()
            stdscr.clear()

            if max_y < 8 or max_x < 65:
                safe_addstr(
                    stdscr,
                    1,
                    2,
                    "Window too small! Resize to at least 65x8.",
                    curses.A_BOLD,
                )
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord("q"), 27):
                    break
                continue

            current_lang = lang_modes[lang_idx]
            current_sort = sort_options[sort_idx]

            view_scenarios = filter_and_sort_scenarios(
                scenarios,
                search_query=search_query,
                sort_by=current_sort,
                lang_mode=current_lang,
            )

            rows = []
            if current_lang is None:
                for s in view_scenarios:
                    rows.append((s, "en"))
                    rows.append((s, "id"))
            else:
                for s in view_scenarios:
                    rows.append((s, current_lang))

            total_rows = len(rows)
            if cursor_idx >= total_rows:
                cursor_idx = max(0, total_rows - 1)

            # Minimalist Top Bar (1 line)
            lang_label = current_lang.upper() if current_lang else "ID/EN"
            filter_text = f" | Filter: '{search_query}'" if search_query else ""
            title_text = f" Wonderful Party | View: [{lang_label}] (Tab) | Sort: [{current_sort}] (s){filter_text} | Scenarios: {len(view_scenarios)} "
            safe_addstr(
                stdscr,
                0,
                0,
                title_text.ljust(max_x),
                curses.color_pair(1) | curses.A_BOLD,
            )

            # Table Header (line 1)
            if current_lang is None:
                th = f" {'SCENARIO':<28} {'LANG':<5} {'TOTAL':>6}   {'DONE':>5}   {'%':>6}    {'PR':>5}   {'MTL':>5}   {'UNTRANSLATED':>7}"
            else:
                th = f" {'SCENARIO':<30} {'TOTAL':>6}   {'DONE':>5}   {'%':>6}    {'PR':>5}   {'MTL':>5}   {'UNTRANSLATED':>7}"
            safe_addstr(stdscr, 1, 0, th.ljust(max_x), curses.A_REVERSE | curses.A_BOLD)

            table_start_y = 2
            visible_rows = max_y - table_start_y - 1

            if cursor_idx < scroll_offset:
                scroll_offset = cursor_idx
            elif cursor_idx >= scroll_offset + visible_rows:
                scroll_offset = cursor_idx - visible_rows + 1

            for row_i in range(visible_rows):
                item_idx = scroll_offset + row_i
                if item_idx >= total_rows:
                    break

                s, l_code = rows[item_idx]
                is_selected = item_idx == cursor_idx
                y_pos = table_start_y + row_i

                st = s[l_code]
                pct = st["percent"]
                pct_str = f"{pct:5.1f}%"

                if pct >= 100.0:
                    row_color = curses.color_pair(3)
                elif pct > 0.0:
                    row_color = curses.color_pair(4)
                else:
                    row_color = curses.color_pair(5)

                if current_lang is None:
                    line_str = (
                        f" {s['scenario_id']:<28} "
                        f"{l_code:<5} "
                        f"{st['total']:>6}   "
                        f"{st['translated']:>5}   "
                        f"{pct_str}    "
                        f"{st['proofread']:>5}   "
                        f"{st['mtl']:>5}   "
                        f"{st['untranslated']:>7}"
                    )
                else:
                    line_str = (
                        f" {s['scenario_id']:<30} "
                        f"{st['total']:>6}   "
                        f"{st['translated']:>5}   "
                        f"{pct_str}    "
                        f"{st['proofread']:>5}   "
                        f"{st['mtl']:>5}   "
                        f"{st['untranslated']:>7}"
                    )

                attr = (
                    curses.color_pair(6) | curses.A_BOLD if is_selected else row_color
                )
                safe_addstr(stdscr, y_pos, 0, line_str.ljust(max_x), attr)

            # Minimalist Footer (line max_y - 1)
            footer_y = max_y - 1
            if searching:
                prompt_str = f" Search: {search_buffer}_ (Enter: apply, Esc: cancel)"
                safe_addstr(
                    stdscr,
                    footer_y,
                    0,
                    prompt_str.ljust(max_x),
                    curses.color_pair(8) | curses.A_BOLD,
                )
            else:
                footer_str = " [↑/↓/j/k] Nav  [/] Search  [Tab] View  [s] Sort  [c] Clear  [p] Pager  [q] Quit"
                safe_addstr(
                    stdscr, footer_y, 0, footer_str.ljust(max_x), curses.color_pair(1)
                )

            stdscr.refresh()

            key = stdscr.getch()

            if searching:
                if key in (10, 13):  # Enter
                    search_query = search_buffer
                    searching = False
                    cursor_idx = 0
                    scroll_offset = 0
                elif key in (27,):  # Escape
                    searching = False
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    search_buffer = search_buffer[:-1]
                    search_query = search_buffer
                elif 32 <= key <= 126:
                    search_buffer += chr(key)
                    search_query = search_buffer
                continue

            if key in (ord("q"), 27):
                break
            elif key in (curses.KEY_UP, ord("k")):
                if cursor_idx > 0:
                    cursor_idx -= 1
            elif key in (curses.KEY_DOWN, ord("j")):
                if cursor_idx < total_rows - 1:
                    cursor_idx += 1
            elif key in (curses.KEY_PPAGE, 21):
                cursor_idx = max(0, cursor_idx - visible_rows)
            elif key in (curses.KEY_NPAGE, 4):
                cursor_idx = min(max(0, total_rows - 1), cursor_idx + visible_rows)
            elif key in (curses.KEY_HOME, ord("g")):
                cursor_idx = 0
            elif key in (curses.KEY_END, ord("G")):
                cursor_idx = max(0, total_rows - 1)
            elif key == ord("\t"):
                lang_idx = (lang_idx + 1) % len(lang_modes)
                cursor_idx = 0
                scroll_offset = 0
            elif key == ord("s"):
                sort_idx = (sort_idx + 1) % len(sort_options)
            elif key == ord("/"):
                searching = True
                search_buffer = search_query
            elif key == ord("c"):
                search_query = ""
                search_buffer = ""
                cursor_idx = 0
                scroll_offset = 0
            elif key == ord("p"):
                curses.endwin()
                tbl_text = format_table(
                    view_scenarios,
                    lang_mode=current_lang,
                    use_ansi=True,
                    search_query=search_query,
                    sort_by=current_sort,
                )
                run_pager(tbl_text)
                stdscr.clear()

    try:
        curses.wrapper(tui_loop)
    except Exception:
        tbl_text = format_table(
            scenarios,
            lang_mode=initial_lang,
            use_ansi=True,
            search_query=initial_search,
            sort_by=initial_sort,
        )
        run_pager(tbl_text)


def show_scenario_progress(
    lang: Optional[str] = None,
    search: str = "",
    sort: str = "name",
    mode: str = "auto",
):
    scenarios = get_all_scenarios_stats()
    filtered = filter_and_sort_scenarios(
        scenarios, search_query=search, sort_by=sort, lang_mode=lang
    )

    is_interactive = sys.stdout.isatty() and os.environ.get("TERM", "") not in (
        "dumb",
        "",
    )

    if mode == "plain" or (mode == "auto" and not is_interactive):
        output = format_table(
            filtered,
            lang_mode=lang,
            use_ansi=sys.stdout.isatty(),
            search_query=search,
            sort_by=sort,
        )
        print(output)
    elif mode == "pager":
        output = format_table(
            filtered, lang_mode=lang, use_ansi=True, search_query=search, sort_by=sort
        )
        run_pager(output)
    elif mode == "tui" or (mode == "auto" and is_interactive):
        try:
            run_curses_tui(
                scenarios, initial_lang=lang, initial_search=search, initial_sort=sort
            )
        except Exception:
            output = format_table(
                filtered,
                lang_mode=lang,
                use_ansi=True,
                search_query=search,
                sort_by=sort,
            )
            run_pager(output)
