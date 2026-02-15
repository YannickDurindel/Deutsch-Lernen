# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Deutsch Lernen — an interactive German vocabulary learning game with web and terminal versions.

## Structure

- `data/` — 11 JSON vocabulary files (numbers, days, months, verbs, nouns, adjectives, adverbs, phrases, colors, greetings, pronouns)
- `web/` — Browser-based game (vanilla HTML/CSS/JS, no build tools)
- `terminal/` — Terminal game (Python 3 + rich library)
- `serve.py` — HTTP server to launch the web version

## Running

### Web version
```bash
python3 serve.py
# Opens browser to http://localhost:8000/web/
```

### Terminal version
```bash
pip install rich
python3 terminal/game.py
```

## Data Format

Each JSON file in `data/` is an array of objects with:
- `de` (string) — German word/phrase
- `en` (string) — English translation
- `hint` (string) — Memory aid
- Optional: `example`, `conjugation`, `context`, `opposite`, `category`

## Progress Storage

- Web: localStorage key `deutsh_progress`
- Terminal: `~/.deutsh_progress.json`

Both use the same schema: XP, streak, per-word mastery (0-5 scale), correct/wrong counts.
