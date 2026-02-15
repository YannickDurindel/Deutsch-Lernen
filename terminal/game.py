#!/usr/bin/env python3
"""
DEUTSCH LERNEN - Terminal-based German vocabulary learning game.

A polished, interactive CLI game using the `rich` library for learning
German vocabulary through flashcards, quizzes, typing challenges,
and speed rounds with spaced repetition.

Usage:
    python3 terminal/game.py
"""

import json
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt
    from rich.progress import BarColumn, Progress, TextColumn
    from rich.columns import Columns
    from rich.align import Align
    from rich import box
except ImportError:
    print("Error: The 'rich' library is required.")
    print("Install it with: pip install rich")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
PROGRESS_FILE = Path.home() / ".deutsh_progress.json"

CATEGORIES = [
    "numbers", "days", "months", "verbs", "nouns",
    "adjectives", "adverbs", "phrases", "colors", "greetings", "pronouns",
]

# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------
console = Console()

# ---------------------------------------------------------------------------
# Encouraging / discouraging messages
# ---------------------------------------------------------------------------
CORRECT_MESSAGES = [
    "Sehr gut! \U0001f389",
    "Richtig! \u2713",
    "Perfekt! \u2b50",
    "Wunderbar! \U0001f31f",
    "Genau! \U0001f44d",
    "Toll! \U0001f680",
    "Ausgezeichnet! \U0001f3c6",
    "Fantastisch! \u2728",
]

WRONG_MESSAGES = [
    "Nicht ganz \u2014 weiter so!",
    "Fast! Versuch es nochmal.",
    "Falsch, aber du lernst!",
    "Keine Sorge, das kommt noch!",
    "Nah dran! Bleib dran.",
]

# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------

def load_progress() -> dict:
    """Load progress from disk or return a fresh structure."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure required keys
            data.setdefault("xp", 0)
            data.setdefault("streak", 0)
            data.setdefault("last_played", "")
            data.setdefault("best_speed", 0)
            data.setdefault("words", {})
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"xp": 0, "streak": 0, "last_played": "", "best_speed": 0, "words": {}}


def save_progress(progress: dict) -> None:
    """Persist progress to disk."""
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def update_streak(progress: dict) -> None:
    """Update the daily streak based on last_played date."""
    today = date.today().isoformat()
    last = progress.get("last_played", "")
    if last == today:
        return  # already played today
    if last == (date.today() - timedelta(days=1)).isoformat():
        progress["streak"] += 1
    elif last == "":
        progress["streak"] = 1
    else:
        progress["streak"] = 1
    progress["last_played"] = today


def get_word_key(category: str, de_word: str) -> str:
    return f"{category}:{de_word}"


def get_mastery(progress: dict, category: str, de_word: str) -> int:
    key = get_word_key(category, de_word)
    return progress["words"].get(key, {}).get("mastery", 0)


def record_answer(progress: dict, category: str, de_word: str, correct: bool) -> None:
    key = get_word_key(category, de_word)
    entry = progress["words"].setdefault(key, {"mastery": 0, "correct": 0, "wrong": 0})
    if correct:
        entry["correct"] += 1
        entry["mastery"] = min(entry["mastery"] + 1, 5)
    else:
        entry["wrong"] += 1
        entry["mastery"] = max(entry["mastery"] - 1, 0)

# ---------------------------------------------------------------------------
# Vocabulary helpers
# ---------------------------------------------------------------------------

def load_category(name: str) -> list[dict]:
    """Load a single category JSON file."""
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_vocab() -> dict[str, list[dict]]:
    """Load all categories into a dict keyed by category name."""
    vocab: dict[str, list[dict]] = {}
    for cat in CATEGORIES:
        data = load_category(cat)
        if data:
            vocab[cat] = data
    return vocab


def category_completion(progress: dict, category: str, words: list[dict]) -> float:
    """Return 0.0-1.0 fraction of words at mastery >= 3."""
    if not words:
        return 0.0
    learned = sum(
        1 for w in words if get_mastery(progress, category, w["de"]) >= 3
    )
    return learned / len(words)


def words_learned_count(progress: dict) -> int:
    """Total number of words at mastery >= 3."""
    return sum(1 for entry in progress["words"].values() if entry.get("mastery", 0) >= 3)

# ---------------------------------------------------------------------------
# Spaced repetition: weighted word selection
# ---------------------------------------------------------------------------

def weighted_sample(progress: dict, category: str, words: list[dict], n: int) -> list[dict]:
    """Pick up to n words weighted by inverse mastery (lower mastery = more likely)."""
    if not words:
        return []
    weights = []
    for w in words:
        m = get_mastery(progress, category, w["de"])
        weights.append(5 - m + 1)  # mastery 0 → weight 6, mastery 5 → weight 1
    total = sum(weights)
    probs = [w / total for w in weights]
    n = min(n, len(words))
    chosen_indices: set[int] = set()
    result: list[dict] = []
    attempts = 0
    while len(result) < n and attempts < n * 20:
        idx = random.choices(range(len(words)), weights=probs, k=1)[0]
        if idx not in chosen_indices:
            chosen_indices.add(idx)
            result.append(words[idx])
        attempts += 1
    # If weighted sampling couldn't fill, pad with random remaining
    if len(result) < n:
        remaining = [w for i, w in enumerate(words) if i not in chosen_indices]
        random.shuffle(remaining)
        result.extend(remaining[: n - len(result)])
    return result

# ---------------------------------------------------------------------------
# Umlaut-lenient matching
# ---------------------------------------------------------------------------

def normalize_german(text: str) -> str:
    """Normalize for lenient comparison: lowercase and replace umlauts."""
    t = text.lower().strip()
    t = t.replace("\u00fc", "u").replace("\u00f6", "o").replace("\u00e4", "a")
    t = t.replace("\u00dc", "u").replace("\u00d6", "o").replace("\u00c4", "a")
    t = t.replace("\u00df", "ss")
    return t

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def clear_screen() -> None:
    console.clear()


def press_enter_to_continue() -> None:
    console.print()
    Prompt.ask("[dim]Press Enter to continue[/dim]", default="")


def show_title_banner() -> None:
    title = Text("DEUTSCH LERNEN", style="bold bright_white on blue", justify="center")
    subtitle = Text("Terminal Vocabulary Trainer", style="italic cyan", justify="center")
    content = Text.assemble(title, "\n", subtitle)
    panel = Panel(
        Align.center(content),
        border_style="bright_blue",
        box=box.DOUBLE,
        padding=(1, 4),
    )
    console.print(panel)
    console.print()

# ---------------------------------------------------------------------------
# Main Menu
# ---------------------------------------------------------------------------

def main_menu(progress: dict, vocab: dict[str, list[dict]]) -> str | None:
    """Display the main menu and return user choice."""
    clear_screen()
    show_title_banner()

    # Stats row
    xp = progress["xp"]
    streak = progress["streak"]
    learned = words_learned_count(progress)
    stats_table = Table(show_header=False, box=None, padding=(0, 3))
    stats_table.add_column(justify="center")
    stats_table.add_column(justify="center")
    stats_table.add_column(justify="center")
    stats_table.add_row(
        f"[bold yellow]\u2b50 XP:[/bold yellow] [white]{xp}[/white]",
        f"[bold red]\U0001f525 Streak:[/bold red] [white]{streak} day{'s' if streak != 1 else ''}[/white]",
        f"[bold green]\U0001f4d6 Learned:[/bold green] [white]{learned} word{'s' if learned != 1 else ''}[/white]",
    )
    console.print(Align.center(stats_table))
    console.print()

    # Category list
    cat_table = Table(
        title="[bold]Categories[/bold]",
        box=box.ROUNDED,
        border_style="bright_cyan",
        title_style="bold bright_cyan",
        show_lines=False,
        padding=(0, 1),
    )
    cat_table.add_column("#", style="bold cyan", justify="right", width=4)
    cat_table.add_column("Category", style="white", min_width=14)
    cat_table.add_column("Words", justify="center", width=7)
    cat_table.add_column("Progress", min_width=22)
    cat_table.add_column("%", justify="right", width=6)

    for i, cat in enumerate(CATEGORIES, 1):
        words = vocab.get(cat, [])
        comp = category_completion(progress, cat, words)
        pct = int(comp * 100)
        filled = int(comp * 15)
        bar = "[green]" + "\u2588" * filled + "[/green]" + "[dim]\u2591[/dim]" * (15 - filled)
        color = "green" if pct == 100 else "yellow" if pct >= 50 else "white"
        cat_table.add_row(
            str(i),
            cat.capitalize(),
            str(len(words)),
            bar,
            f"[{color}]{pct}%[/{color}]",
        )

    console.print(Align.center(cat_table))
    console.print()
    console.print(
        Align.center(
            Text.from_markup(
                "[bold cyan][1-11][/bold cyan] Select category    "
                "[bold cyan][A][/bold cyan] All categories    "
                "[bold cyan][Q][/bold cyan] Quit"
            )
        )
    )
    console.print()

    choice = Prompt.ask("[bold bright_white]Choose[/bold bright_white]", default="q").strip().lower()
    if choice == "q":
        return None
    if choice == "a":
        return "all"
    try:
        idx = int(choice)
        if 1 <= idx <= len(CATEGORIES):
            return CATEGORIES[idx - 1]
    except ValueError:
        pass
    return "__invalid__"

# ---------------------------------------------------------------------------
# Mode Selection
# ---------------------------------------------------------------------------

def mode_menu(category_label: str) -> str | None:
    """Select game mode. Returns mode string or None to go back."""
    clear_screen()
    show_title_banner()

    panel = Panel(
        Align.center(
            Text.from_markup(
                f"[bold white]Category:[/bold white] [bold bright_yellow]{category_label}[/bold bright_yellow]\n\n"
                "[bold cyan][1][/bold cyan] Learn (Flashcards)\n"
                "[bold cyan][2][/bold cyan] Quiz (Multiple Choice)\n"
                "[bold cyan][3][/bold cyan] Type It\n"
                "[bold cyan][4][/bold cyan] Speed Round\n\n"
                "[bold cyan][B][/bold cyan] Back"
            )
        ),
        title="[bold]Select Mode[/bold]",
        border_style="bright_cyan",
        box=box.ROUNDED,
        padding=(1, 4),
    )
    console.print(Align.center(panel))
    console.print()

    choice = Prompt.ask("[bold bright_white]Choose[/bold bright_white]", default="b").strip().lower()
    mode_map = {"1": "learn", "2": "quiz", "3": "type", "4": "speed", "b": None}
    return mode_map.get(choice, "__invalid__")

# ---------------------------------------------------------------------------
# Learn Mode (Flashcards)
# ---------------------------------------------------------------------------

def learn_mode(progress: dict, category: str, words: list[dict]) -> None:
    if not words:
        console.print("[red]No words in this category.[/red]")
        press_enter_to_continue()
        return

    # Start with a weighted selection order, but allow browsing
    ordered = weighted_sample(progress, category, words, len(words))
    idx = 0
    revealed = False

    while True:
        clear_screen()
        word = ordered[idx]
        de = word["de"]
        en = word["en"]
        mastery = get_mastery(progress, category, de)
        mastery_stars = "\u2b50" * mastery + "\u2606" * (5 - mastery)

        # Card front
        card_content = Text.from_markup(
            f"[bold bright_white on blue]  {de}  [/bold bright_white on blue]"
        )
        card = Panel(
            Align.center(card_content),
            title=f"[dim]Card {idx + 1}/{len(ordered)}[/dim]",
            subtitle=f"[dim]Mastery: {mastery_stars}[/dim]",
            border_style="bright_yellow",
            box=box.DOUBLE,
            padding=(2, 6),
        )
        console.print(Align.center(card))
        console.print()

        if revealed:
            # Show translation
            reveal_parts = [f"[bold green]{en}[/bold green]"]
            if word.get("hint"):
                reveal_parts.append(f"\n[dim italic]Hint: {word['hint']}[/dim italic]")
            if word.get("example"):
                reveal_parts.append(f"\n[cyan]Example: {word['example']}[/cyan]")
            if word.get("conjugation"):
                reveal_parts.append(f"\n[magenta]Conjugation: {word['conjugation']}[/magenta]")
            if word.get("opposite"):
                reveal_parts.append(f"\n[yellow]Opposite: {word['opposite']}[/yellow]")
            if word.get("context"):
                reveal_parts.append(f"\n[dim]Context: {word['context']}[/dim]")

            reveal_panel = Panel(
                Align.center(Text.from_markup("".join(reveal_parts))),
                border_style="green",
                box=box.ROUNDED,
                padding=(1, 4),
            )
            console.print(Align.center(reveal_panel))
            console.print()
            console.print(
                Align.center(
                    Text.from_markup(
                        "[bold cyan][N][/bold cyan] Next  "
                        "[bold cyan][P][/bold cyan] Previous  "
                        "[bold cyan][Q][/bold cyan] Back to modes"
                    )
                )
            )
        else:
            console.print(
                Align.center(
                    Text.from_markup(
                        "[bold cyan][Enter][/bold cyan] Reveal  "
                        "[bold cyan][N][/bold cyan] Next  "
                        "[bold cyan][P][/bold cyan] Previous  "
                        "[bold cyan][Q][/bold cyan] Back to modes"
                    )
                )
            )

        console.print()
        action = Prompt.ask("[bold bright_white]Action[/bold bright_white]", default="").strip().lower()

        if action == "q":
            return
        elif action == "n":
            # Mark seen
            key = get_word_key(category, de)
            progress["words"].setdefault(key, {"mastery": 0, "correct": 0, "wrong": 0})
            idx = (idx + 1) % len(ordered)
            revealed = False
        elif action == "p":
            idx = (idx - 1) % len(ordered)
            revealed = False
        else:
            # Enter or anything else: reveal
            revealed = True

# ---------------------------------------------------------------------------
# Quiz Mode (Multiple Choice)
# ---------------------------------------------------------------------------

def quiz_mode(progress: dict, category: str, words: list[dict]) -> None:
    if len(words) < 2:
        console.print("[red]Not enough words for a quiz in this category.[/red]")
        press_enter_to_continue()
        return

    n_questions = min(10, len(words))
    questions = weighted_sample(progress, category, words, n_questions)
    score = 0

    for qi, word in enumerate(questions, 1):
        clear_screen()
        show_title_banner()

        # Alternate direction: EN→DE on odd, DE→EN on even
        if qi % 2 == 1:
            # EN → DE
            prompt_text = word["en"]
            correct_answer = word["de"]
            direction_label = "English \u2192 German"
            # Build choices
            wrong_pool = [w["de"] for w in words if w["de"] != correct_answer]
            random.shuffle(wrong_pool)
            choices = [correct_answer] + wrong_pool[:3]
            # Pad if category is small
            while len(choices) < 4 and wrong_pool:
                choices.append(wrong_pool.pop())
            random.shuffle(choices)
        else:
            # DE → EN
            prompt_text = word["de"]
            correct_answer = word["en"]
            direction_label = "German \u2192 English"
            wrong_pool = [w["en"] for w in words if w["en"] != correct_answer]
            random.shuffle(wrong_pool)
            choices = [correct_answer] + wrong_pool[:3]
            while len(choices) < 4 and wrong_pool:
                choices.append(wrong_pool.pop())
            random.shuffle(choices)

        # Ensure exactly 4 choices (may be fewer if category is tiny)
        if len(choices) < 2:
            choices = list(set(choices + [correct_answer]))

        console.print(
            Align.center(
                Text.from_markup(
                    f"[dim]{direction_label}[/dim]   "
                    f"[dim]Question {qi}/{n_questions}[/dim]   "
                    f"[dim]Score: {score}[/dim]"
                )
            )
        )
        console.print()

        q_panel = Panel(
            Align.center(Text(prompt_text, style="bold bright_white")),
            border_style="bright_yellow",
            box=box.DOUBLE,
            padding=(1, 6),
        )
        console.print(Align.center(q_panel))
        console.print()

        for ci, choice in enumerate(choices, 1):
            console.print(f"    [bold cyan][{ci}][/bold cyan] {choice}")
        console.print()

        answer = Prompt.ask(
            "[bold bright_white]Your answer[/bold bright_white]",
            choices=[str(i) for i in range(1, len(choices) + 1)],
            default="1",
        )

        selected = choices[int(answer) - 1]
        if selected == correct_answer:
            score += 1
            record_answer(progress, category, word["de"], True)
            progress["xp"] += 10
            console.print(f"\n  [bold green]{random.choice(CORRECT_MESSAGES)}[/bold green]")
        else:
            record_answer(progress, category, word["de"], False)
            console.print(f"\n  [bold red]{random.choice(WRONG_MESSAGES)}[/bold red]")
            console.print(f"  [yellow]Correct answer: {correct_answer}[/yellow]")

        save_progress(progress)
        time.sleep(1.2)

    # Final score
    clear_screen()
    show_title_banner()
    pct = int(score / n_questions * 100)
    if pct == 100:
        grade_msg = "PERFEKT! Ausgezeichnet! \U0001f3c6"
        grade_style = "bold bright_green"
    elif pct >= 70:
        grade_msg = "Sehr gut! Keep it up! \U0001f31f"
        grade_style = "bold green"
    elif pct >= 50:
        grade_msg = "Gut gemacht! Room to grow. \U0001f4aa"
        grade_style = "bold yellow"
    else:
        grade_msg = "Weiter \u00fcben! Practice makes perfect. \U0001f4da"
        grade_style = "bold red"

    result_panel = Panel(
        Align.center(
            Text.from_markup(
                f"[bold white]Quiz Complete![/bold white]\n\n"
                f"[bold]{score}[/bold] / [bold]{n_questions}[/bold] correct  "
                f"([bold]{pct}%[/bold])\n"
                f"[bold]+{score * 10} XP[/bold] earned\n\n"
                f"[{grade_style}]{grade_msg}[/{grade_style}]"
            )
        ),
        border_style="bright_cyan",
        box=box.DOUBLE,
        padding=(1, 4),
    )
    console.print(Align.center(result_panel))
    press_enter_to_continue()

# ---------------------------------------------------------------------------
# Type It Mode
# ---------------------------------------------------------------------------

def type_it_mode(progress: dict, category: str, words: list[dict]) -> None:
    if not words:
        console.print("[red]No words in this category.[/red]")
        press_enter_to_continue()
        return

    n_questions = min(10, len(words))
    questions = weighted_sample(progress, category, words, n_questions)
    score = 0

    for qi, word in enumerate(questions, 1):
        clear_screen()
        show_title_banner()

        en = word["en"]
        de = word["de"]

        console.print(
            Align.center(
                Text.from_markup(
                    f"[dim]Type the German translation[/dim]   "
                    f"[dim]Question {qi}/{n_questions}[/dim]   "
                    f"[dim]Score: {score}[/dim]"
                )
            )
        )
        console.print()

        q_panel = Panel(
            Align.center(Text(en, style="bold bright_white")),
            border_style="bright_yellow",
            box=box.DOUBLE,
            padding=(1, 6),
        )
        console.print(Align.center(q_panel))
        console.print()

        if word.get("hint"):
            console.print(Align.center(Text.from_markup(f"[dim italic]Hint: {word['hint']}[/dim italic]")))
            console.print()

        user_input = Prompt.ask("[bold bright_white]Deine Antwort[/bold bright_white]")

        if normalize_german(user_input) == normalize_german(de):
            score += 1
            record_answer(progress, category, de, True)
            progress["xp"] += 15
            console.print(f"\n  [bold green]{random.choice(CORRECT_MESSAGES)}[/bold green]")
        else:
            record_answer(progress, category, de, False)
            console.print(f"\n  [bold red]{random.choice(WRONG_MESSAGES)}[/bold red]")
            console.print(f"  [bold yellow]Correct: {de}[/bold yellow]")

        save_progress(progress)
        time.sleep(1.2)

    # Final score
    clear_screen()
    show_title_banner()
    pct = int(score / n_questions * 100)
    if pct == 100:
        grade_msg = "PERFEKT! Du bist ein Sprachgenie! \U0001f3c6"
        grade_style = "bold bright_green"
    elif pct >= 70:
        grade_msg = "Sehr gut! Impressive typing! \U0001f31f"
        grade_style = "bold green"
    elif pct >= 50:
        grade_msg = "Nicht schlecht! Keep practicing! \U0001f4aa"
        grade_style = "bold yellow"
    else:
        grade_msg = "Weiter \u00fcben! You'll get there! \U0001f4da"
        grade_style = "bold red"

    result_panel = Panel(
        Align.center(
            Text.from_markup(
                f"[bold white]Type It Complete![/bold white]\n\n"
                f"[bold]{score}[/bold] / [bold]{n_questions}[/bold] correct  "
                f"([bold]{pct}%[/bold])\n"
                f"[bold]+{score * 15} XP[/bold] earned\n\n"
                f"[{grade_style}]{grade_msg}[/{grade_style}]"
            )
        ),
        border_style="bright_cyan",
        box=box.DOUBLE,
        padding=(1, 4),
    )
    console.print(Align.center(result_panel))
    press_enter_to_continue()

# ---------------------------------------------------------------------------
# Speed Round
# ---------------------------------------------------------------------------

def speed_round(progress: dict, category: str, words: list[dict]) -> None:
    if len(words) < 2:
        console.print("[red]Not enough words for a speed round.[/red]")
        press_enter_to_continue()
        return

    clear_screen()
    show_title_banner()

    console.print(
        Align.center(
            Text.from_markup(
                "[bold bright_yellow]\u26a1 SPEED ROUND \u26a1[/bold bright_yellow]\n\n"
                "[white]Answer as many multiple choice questions as you can in 60 seconds![/white]\n"
                "[dim]Press Enter to start...[/dim]"
            )
        )
    )
    Prompt.ask("", default="")

    duration = 60
    start_time = time.time()
    score = 0
    total = 0

    while True:
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        if remaining <= 0:
            break

        total += 1
        word = random.choices(
            words,
            weights=[5 - get_mastery(progress, category, w["de"]) + 1 for w in words],
            k=1,
        )[0]

        # Random direction
        if random.random() < 0.5:
            prompt_text = word["en"]
            correct_answer = word["de"]
        else:
            prompt_text = word["de"]
            correct_answer = word["en"]

        wrong_pool = [
            w["de"] if correct_answer == word["de"] else w["en"]
            for w in words
            if (w["de"] if correct_answer == word["de"] else w["en"]) != correct_answer
        ]
        random.shuffle(wrong_pool)
        choices = [correct_answer] + wrong_pool[:3]
        random.shuffle(choices)

        clear_screen()

        timer_color = "green" if remaining > 20 else "yellow" if remaining > 10 else "bold red"
        console.print(
            Align.center(
                Text.from_markup(
                    f"[{timer_color}]\u23f1  {int(remaining)}s remaining[/{timer_color}]   "
                    f"[bold white]Score: {score}[/bold white]   "
                    f"[dim]#{total}[/dim]"
                )
            )
        )
        console.print()

        q_panel = Panel(
            Align.center(Text(prompt_text, style="bold bright_white")),
            border_style="bright_yellow",
            box=box.HEAVY,
            padding=(0, 4),
        )
        console.print(Align.center(q_panel))
        console.print()

        for ci, choice in enumerate(choices, 1):
            console.print(f"    [bold cyan][{ci}][/bold cyan] {choice}")
        console.print()

        # Check time before prompting
        if time.time() - start_time >= duration:
            break

        answer = Prompt.ask("[bold]Answer[/bold]", default="0").strip()

        # Check time after answer
        if time.time() - start_time >= duration:
            break

        try:
            selected = choices[int(answer) - 1]
        except (ValueError, IndexError):
            selected = ""

        if selected == correct_answer:
            score += 1
            record_answer(progress, category, word["de"], True)
            progress["xp"] += 5
            console.print(f"  [bold green]\u2713[/bold green]")
        else:
            record_answer(progress, category, word["de"], False)
            console.print(f"  [bold red]\u2717[/bold red] [dim]{correct_answer}[/dim]")

        save_progress(progress)
        time.sleep(0.4)

    # Results
    clear_screen()
    show_title_banner()

    is_new_best = score > progress["best_speed"]
    if is_new_best:
        progress["best_speed"] = score
        save_progress(progress)

    result_lines = (
        f"[bold white]\u26a1 Speed Round Complete! \u26a1[/bold white]\n\n"
        f"[bold]{score}[/bold] correct out of [bold]{total}[/bold] attempted\n"
        f"[bold]+{score * 5} XP[/bold] earned\n"
        f"[dim]Personal best: {progress['best_speed']}[/dim]"
    )
    if is_new_best:
        result_lines += "\n\n[bold bright_yellow]\U0001f389 NEW PERSONAL BEST! \U0001f389[/bold bright_yellow]"

    result_panel = Panel(
        Align.center(Text.from_markup(result_lines)),
        border_style="bright_yellow",
        box=box.DOUBLE,
        padding=(1, 4),
    )
    console.print(Align.center(result_panel))
    press_enter_to_continue()

# ---------------------------------------------------------------------------
# Category play loop
# ---------------------------------------------------------------------------

def play_category(progress: dict, category: str, words: list[dict], label: str) -> None:
    """Mode selection loop for a given category/word set."""
    while True:
        mode = mode_menu(label)
        if mode is None:
            return
        if mode == "__invalid__":
            continue
        if mode == "learn":
            learn_mode(progress, category, words)
        elif mode == "quiz":
            quiz_mode(progress, category, words)
        elif mode == "type":
            type_it_mode(progress, category, words)
        elif mode == "speed":
            speed_round(progress, category, words)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Load data
    vocab = load_all_vocab()
    if not vocab:
        console.print("[bold red]Error:[/bold red] No vocabulary files found in data/ directory.")
        console.print(f"[dim]Looked in: {DATA_DIR}[/dim]")
        sys.exit(1)

    progress = load_progress()
    update_streak(progress)
    save_progress(progress)

    while True:
        choice = main_menu(progress, vocab)

        if choice is None:
            # Quit
            clear_screen()
            console.print(
                Align.center(
                    Panel(
                        Align.center(
                            Text.from_markup(
                                "[bold bright_white]Tsch\u00fcss! Bis bald! \U0001f44b[/bold bright_white]\n\n"
                                f"[dim]Total XP: {progress['xp']}  |  "
                                f"Streak: {progress['streak']} day{'s' if progress['streak'] != 1 else ''}  |  "
                                f"Words learned: {words_learned_count(progress)}[/dim]"
                            )
                        ),
                        border_style="bright_blue",
                        box=box.DOUBLE,
                        padding=(1, 4),
                    )
                )
            )
            console.print()
            break

        if choice == "__invalid__":
            continue

        if choice == "all":
            # Merge all words, keeping track of category per word
            all_words: list[dict] = []
            for cat in CATEGORIES:
                cat_words = vocab.get(cat, [])
                for w in cat_words:
                    augmented = dict(w)
                    augmented["_category"] = cat
                    all_words.append(augmented)
            if not all_words:
                continue
            # For "all", use a special category prefix approach
            # We need to wrap play_category to handle multi-category progress
            _play_all_categories(progress, all_words)
        else:
            cat_words = vocab.get(choice, [])
            if not cat_words:
                console.print(f"[red]Category '{choice}' has no words.[/red]")
                press_enter_to_continue()
                continue
            play_category(progress, choice, cat_words, choice.capitalize())


def _play_all_categories(progress: dict, all_words: list[dict]) -> None:
    """Play modes with all categories merged. Uses _category field for progress tracking."""

    # Create wrapper functions that use per-word category
    original_record = record_answer
    original_mastery = get_mastery

    class AllCategoryProxy:
        """Proxy to handle multi-category word lists."""
        pass

    # We re-implement mode functions by overriding category with per-word category
    # Simplest approach: use "all" as the category label and map words via _category
    # Override record_answer and get_mastery temporarily via a helper

    # Build a mapping: de -> actual category
    cat_map = {}
    for w in all_words:
        cat_map[w["de"]] = w.get("_category", "all")

    # Monkey-patch-free approach: just use the actual category from _category field.
    # Since our functions take category as a param, we need a wrapper for the modes.

    # For simplicity, we use a special wrapper that overrides the category for each word
    # by using the _category field. Let's create a thin adapter.

    while True:
        mode = mode_menu("All Categories")
        if mode is None:
            return
        if mode == "__invalid__":
            continue
        if mode == "learn":
            _learn_all(progress, all_words, cat_map)
        elif mode == "quiz":
            _quiz_all(progress, all_words, cat_map)
        elif mode == "type":
            _type_all(progress, all_words, cat_map)
        elif mode == "speed":
            _speed_all(progress, all_words, cat_map)


def _get_cat(word: dict, cat_map: dict) -> str:
    return word.get("_category", cat_map.get(word["de"], "all"))


def _learn_all(progress: dict, words: list[dict], cat_map: dict) -> None:
    """Learn mode for all categories - delegates to learn_mode with per-word category."""
    # Build weighted ordering across all categories
    if not words:
        return

    weights = []
    for w in words:
        cat = _get_cat(w, cat_map)
        m = get_mastery(progress, cat, w["de"])
        weights.append(5 - m + 1)
    total = sum(weights)
    probs = [wt / total for wt in weights]

    chosen_indices: set[int] = set()
    ordered: list[dict] = []
    attempts = 0
    n = len(words)
    while len(ordered) < n and attempts < n * 20:
        idx = random.choices(range(len(words)), weights=probs, k=1)[0]
        if idx not in chosen_indices:
            chosen_indices.add(idx)
            ordered.append(words[idx])
        attempts += 1
    if len(ordered) < n:
        remaining = [w for i, w in enumerate(words) if i not in chosen_indices]
        random.shuffle(remaining)
        ordered.extend(remaining)

    idx = 0
    revealed = False

    while True:
        clear_screen()
        word = ordered[idx]
        de = word["de"]
        en = word["en"]
        cat = _get_cat(word, cat_map)
        mastery = get_mastery(progress, cat, de)
        mastery_stars = "\u2b50" * mastery + "\u2606" * (5 - mastery)

        card_content = Text.from_markup(
            f"[bold bright_white on blue]  {de}  [/bold bright_white on blue]"
        )
        card = Panel(
            Align.center(card_content),
            title=f"[dim]Card {idx + 1}/{len(ordered)}[/dim]  [dim cyan]{cat}[/dim cyan]",
            subtitle=f"[dim]Mastery: {mastery_stars}[/dim]",
            border_style="bright_yellow",
            box=box.DOUBLE,
            padding=(2, 6),
        )
        console.print(Align.center(card))
        console.print()

        if revealed:
            reveal_parts = [f"[bold green]{en}[/bold green]"]
            if word.get("hint"):
                reveal_parts.append(f"\n[dim italic]Hint: {word['hint']}[/dim italic]")
            if word.get("example"):
                reveal_parts.append(f"\n[cyan]Example: {word['example']}[/cyan]")
            if word.get("conjugation"):
                reveal_parts.append(f"\n[magenta]Conjugation: {word['conjugation']}[/magenta]")
            if word.get("opposite"):
                reveal_parts.append(f"\n[yellow]Opposite: {word['opposite']}[/yellow]")

            reveal_panel = Panel(
                Align.center(Text.from_markup("".join(reveal_parts))),
                border_style="green",
                box=box.ROUNDED,
                padding=(1, 4),
            )
            console.print(Align.center(reveal_panel))
            console.print()
            console.print(
                Align.center(
                    Text.from_markup(
                        "[bold cyan][N][/bold cyan] Next  "
                        "[bold cyan][P][/bold cyan] Previous  "
                        "[bold cyan][Q][/bold cyan] Back"
                    )
                )
            )
        else:
            console.print(
                Align.center(
                    Text.from_markup(
                        "[bold cyan][Enter][/bold cyan] Reveal  "
                        "[bold cyan][N][/bold cyan] Next  "
                        "[bold cyan][P][/bold cyan] Previous  "
                        "[bold cyan][Q][/bold cyan] Back"
                    )
                )
            )

        console.print()
        action = Prompt.ask("[bold bright_white]Action[/bold bright_white]", default="").strip().lower()

        if action == "q":
            return
        elif action == "n":
            key = get_word_key(cat, de)
            progress["words"].setdefault(key, {"mastery": 0, "correct": 0, "wrong": 0})
            idx = (idx + 1) % len(ordered)
            revealed = False
        elif action == "p":
            idx = (idx - 1) % len(ordered)
            revealed = False
        else:
            revealed = True


def _quiz_all(progress: dict, words: list[dict], cat_map: dict) -> None:
    """Quiz mode for all categories."""
    if len(words) < 2:
        console.print("[red]Not enough words for a quiz.[/red]")
        press_enter_to_continue()
        return

    # Weighted sample
    w_weights = [5 - get_mastery(progress, _get_cat(w, cat_map), w["de"]) + 1 for w in words]
    total_w = sum(w_weights)
    probs = [wt / total_w for wt in w_weights]
    n_questions = min(10, len(words))

    chosen_indices: set[int] = set()
    questions: list[dict] = []
    attempts = 0
    while len(questions) < n_questions and attempts < n_questions * 20:
        idx = random.choices(range(len(words)), weights=probs, k=1)[0]
        if idx not in chosen_indices:
            chosen_indices.add(idx)
            questions.append(words[idx])
        attempts += 1

    score = 0
    for qi, word in enumerate(questions, 1):
        clear_screen()
        show_title_banner()
        cat = _get_cat(word, cat_map)

        if qi % 2 == 1:
            prompt_text = word["en"]
            correct_answer = word["de"]
            direction_label = "English \u2192 German"
            wrong_pool = [w["de"] for w in words if w["de"] != correct_answer]
        else:
            prompt_text = word["de"]
            correct_answer = word["en"]
            direction_label = "German \u2192 English"
            wrong_pool = [w["en"] for w in words if w["en"] != correct_answer]

        random.shuffle(wrong_pool)
        choices = [correct_answer] + wrong_pool[:3]
        random.shuffle(choices)

        console.print(
            Align.center(
                Text.from_markup(
                    f"[dim]{direction_label}[/dim]   "
                    f"[dim]Question {qi}/{n_questions}[/dim]   "
                    f"[dim]Score: {score}[/dim]"
                )
            )
        )
        console.print()

        q_panel = Panel(
            Align.center(Text(prompt_text, style="bold bright_white")),
            border_style="bright_yellow",
            box=box.DOUBLE,
            padding=(1, 6),
        )
        console.print(Align.center(q_panel))
        console.print()

        for ci, choice in enumerate(choices, 1):
            console.print(f"    [bold cyan][{ci}][/bold cyan] {choice}")
        console.print()

        answer = Prompt.ask(
            "[bold bright_white]Your answer[/bold bright_white]",
            choices=[str(i) for i in range(1, len(choices) + 1)],
            default="1",
        )

        selected = choices[int(answer) - 1]
        if selected == correct_answer:
            score += 1
            record_answer(progress, cat, word["de"], True)
            progress["xp"] += 10
            console.print(f"\n  [bold green]{random.choice(CORRECT_MESSAGES)}[/bold green]")
        else:
            record_answer(progress, cat, word["de"], False)
            console.print(f"\n  [bold red]{random.choice(WRONG_MESSAGES)}[/bold red]")
            console.print(f"  [yellow]Correct answer: {correct_answer}[/yellow]")

        save_progress(progress)
        time.sleep(1.2)

    # Final score
    clear_screen()
    show_title_banner()
    pct = int(score / n_questions * 100)
    if pct == 100:
        grade_msg = "PERFEKT! \U0001f3c6"
        grade_style = "bold bright_green"
    elif pct >= 70:
        grade_msg = "Sehr gut! \U0001f31f"
        grade_style = "bold green"
    elif pct >= 50:
        grade_msg = "Gut gemacht! \U0001f4aa"
        grade_style = "bold yellow"
    else:
        grade_msg = "Weiter \u00fcben! \U0001f4da"
        grade_style = "bold red"

    result_panel = Panel(
        Align.center(
            Text.from_markup(
                f"[bold white]Quiz Complete![/bold white]\n\n"
                f"[bold]{score}[/bold] / [bold]{n_questions}[/bold] correct  "
                f"([bold]{pct}%[/bold])\n"
                f"[bold]+{score * 10} XP[/bold] earned\n\n"
                f"[{grade_style}]{grade_msg}[/{grade_style}]"
            )
        ),
        border_style="bright_cyan",
        box=box.DOUBLE,
        padding=(1, 4),
    )
    console.print(Align.center(result_panel))
    press_enter_to_continue()


def _type_all(progress: dict, words: list[dict], cat_map: dict) -> None:
    """Type It mode for all categories."""
    if not words:
        return

    w_weights = [5 - get_mastery(progress, _get_cat(w, cat_map), w["de"]) + 1 for w in words]
    total_w = sum(w_weights)
    probs = [wt / total_w for wt in w_weights]
    n_questions = min(10, len(words))

    chosen_indices: set[int] = set()
    questions: list[dict] = []
    attempts = 0
    while len(questions) < n_questions and attempts < n_questions * 20:
        idx = random.choices(range(len(words)), weights=probs, k=1)[0]
        if idx not in chosen_indices:
            chosen_indices.add(idx)
            questions.append(words[idx])
        attempts += 1

    score = 0
    for qi, word in enumerate(questions, 1):
        clear_screen()
        show_title_banner()
        cat = _get_cat(word, cat_map)
        en = word["en"]
        de = word["de"]

        console.print(
            Align.center(
                Text.from_markup(
                    f"[dim]Type the German translation[/dim]   "
                    f"[dim]Question {qi}/{n_questions}[/dim]   "
                    f"[dim]Score: {score}[/dim]"
                )
            )
        )
        console.print()

        q_panel = Panel(
            Align.center(Text(en, style="bold bright_white")),
            border_style="bright_yellow",
            box=box.DOUBLE,
            padding=(1, 6),
        )
        console.print(Align.center(q_panel))
        console.print()

        if word.get("hint"):
            console.print(Align.center(Text.from_markup(f"[dim italic]Hint: {word['hint']}[/dim italic]")))
            console.print()

        user_input = Prompt.ask("[bold bright_white]Deine Antwort[/bold bright_white]")

        if normalize_german(user_input) == normalize_german(de):
            score += 1
            record_answer(progress, cat, de, True)
            progress["xp"] += 15
            console.print(f"\n  [bold green]{random.choice(CORRECT_MESSAGES)}[/bold green]")
        else:
            record_answer(progress, cat, de, False)
            console.print(f"\n  [bold red]{random.choice(WRONG_MESSAGES)}[/bold red]")
            console.print(f"  [bold yellow]Correct: {de}[/bold yellow]")

        save_progress(progress)
        time.sleep(1.2)

    clear_screen()
    show_title_banner()
    pct = int(score / n_questions * 100)
    if pct == 100:
        grade_msg = "PERFEKT! \U0001f3c6"
        grade_style = "bold bright_green"
    elif pct >= 70:
        grade_msg = "Sehr gut! \U0001f31f"
        grade_style = "bold green"
    elif pct >= 50:
        grade_msg = "Nicht schlecht! \U0001f4aa"
        grade_style = "bold yellow"
    else:
        grade_msg = "Weiter \u00fcben! \U0001f4da"
        grade_style = "bold red"

    result_panel = Panel(
        Align.center(
            Text.from_markup(
                f"[bold white]Type It Complete![/bold white]\n\n"
                f"[bold]{score}[/bold] / [bold]{n_questions}[/bold] correct  "
                f"([bold]{pct}%[/bold])\n"
                f"[bold]+{score * 15} XP[/bold] earned\n\n"
                f"[{grade_style}]{grade_msg}[/{grade_style}]"
            )
        ),
        border_style="bright_cyan",
        box=box.DOUBLE,
        padding=(1, 4),
    )
    console.print(Align.center(result_panel))
    press_enter_to_continue()


def _speed_all(progress: dict, words: list[dict], cat_map: dict) -> None:
    """Speed round for all categories."""
    if len(words) < 2:
        console.print("[red]Not enough words for a speed round.[/red]")
        press_enter_to_continue()
        return

    clear_screen()
    show_title_banner()
    console.print(
        Align.center(
            Text.from_markup(
                "[bold bright_yellow]\u26a1 SPEED ROUND \u26a1[/bold bright_yellow]\n\n"
                "[white]Answer as many questions as you can in 60 seconds![/white]\n"
                "[dim]Press Enter to start...[/dim]"
            )
        )
    )
    Prompt.ask("", default="")

    duration = 60
    start_time = time.time()
    score = 0
    total = 0

    while True:
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        if remaining <= 0:
            break

        total += 1
        w_weights = [5 - get_mastery(progress, _get_cat(w, cat_map), w["de"]) + 1 for w in words]
        word = random.choices(words, weights=w_weights, k=1)[0]
        cat = _get_cat(word, cat_map)

        if random.random() < 0.5:
            prompt_text = word["en"]
            correct_answer = word["de"]
            wrong_pool = [w["de"] for w in words if w["de"] != correct_answer]
        else:
            prompt_text = word["de"]
            correct_answer = word["en"]
            wrong_pool = [w["en"] for w in words if w["en"] != correct_answer]

        random.shuffle(wrong_pool)
        choices = [correct_answer] + wrong_pool[:3]
        random.shuffle(choices)

        clear_screen()
        timer_color = "green" if remaining > 20 else "yellow" if remaining > 10 else "bold red"
        console.print(
            Align.center(
                Text.from_markup(
                    f"[{timer_color}]\u23f1  {int(remaining)}s remaining[/{timer_color}]   "
                    f"[bold white]Score: {score}[/bold white]   "
                    f"[dim]#{total}[/dim]"
                )
            )
        )
        console.print()

        q_panel = Panel(
            Align.center(Text(prompt_text, style="bold bright_white")),
            border_style="bright_yellow",
            box=box.HEAVY,
            padding=(0, 4),
        )
        console.print(Align.center(q_panel))
        console.print()

        for ci, choice in enumerate(choices, 1):
            console.print(f"    [bold cyan][{ci}][/bold cyan] {choice}")
        console.print()

        if time.time() - start_time >= duration:
            break

        answer = Prompt.ask("[bold]Answer[/bold]", default="0").strip()

        if time.time() - start_time >= duration:
            break

        try:
            selected = choices[int(answer) - 1]
        except (ValueError, IndexError):
            selected = ""

        if selected == correct_answer:
            score += 1
            record_answer(progress, cat, word["de"], True)
            progress["xp"] += 5
            console.print(f"  [bold green]\u2713[/bold green]")
        else:
            record_answer(progress, cat, word["de"], False)
            console.print(f"  [bold red]\u2717[/bold red] [dim]{correct_answer}[/dim]")

        save_progress(progress)
        time.sleep(0.4)

    clear_screen()
    show_title_banner()

    is_new_best = score > progress["best_speed"]
    if is_new_best:
        progress["best_speed"] = score
        save_progress(progress)

    result_lines = (
        f"[bold white]\u26a1 Speed Round Complete! \u26a1[/bold white]\n\n"
        f"[bold]{score}[/bold] correct out of [bold]{total}[/bold] attempted\n"
        f"[bold]+{score * 5} XP[/bold] earned\n"
        f"[dim]Personal best: {progress['best_speed']}[/dim]"
    )
    if is_new_best:
        result_lines += "\n\n[bold bright_yellow]\U0001f389 NEW PERSONAL BEST! \U0001f389[/bold bright_yellow]"

    result_panel = Panel(
        Align.center(Text.from_markup(result_lines)),
        border_style="bright_yellow",
        box=box.DOUBLE,
        padding=(1, 4),
    )
    console.print(Align.center(result_panel))
    press_enter_to_continue()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Tsch\u00fcss! \U0001f44b[/dim]")
        sys.exit(0)
