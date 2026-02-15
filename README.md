# Deutsch Lernen

An interactive German vocabulary learning game with web and terminal versions. Practice 567+ words and phrases across 12 categories with spaced repetition, XP tracking, and streak rewards.

## Features

- **12 vocabulary categories**: numbers, days, months, verbs, nouns, adjectives, adverbs, phrases, colors, greetings, pronouns, and full sentences
- **567+ vocabulary items** with German/English translations, memory hints, and examples
- **Progress tracking**: XP system, daily streaks, per-word mastery (0-5 scale)
- **Two interfaces**: browser-based web game and terminal game
- **Spaced repetition**: words you struggle with appear more often

## Getting Started

### Web Version

```bash
python3 serve.py
# Opens browser to http://localhost:8000/web/
```

No build tools or dependencies required — just vanilla HTML, CSS, and JavaScript.

### Terminal Version

```bash
pip install rich
python3 terminal/game.py
```

Requires Python 3 and the [rich](https://github.com/Textualize/rich) library for styled terminal output.

## Project Structure

```
data/               # 12 JSON vocabulary files
  adjectives.json   # 70 adjectives with opposites
  adverbs.json      # 50 common adverbs
  colors.json       # 25 colors and shades
  days.json         # 25 days, times of day, time words
  greetings.json    # 31 greetings and expressions
  months.json       # 28 months, seasons, calendar terms
  nouns.json        # 90 nouns with gender (der/die/das)
  numbers.json      # 51 numbers, ordinals, fractions
  phrases.json      # 45 survival phrases for travelers
  pronouns.json     # 38 personal, possessive, reflexive, interrogative pronouns
  sentences.json    # 45 full sentences at 3 difficulty levels
  verbs.json        # 69 verbs with conjugations and examples
web/                # Browser-based game (vanilla HTML/CSS/JS)
terminal/           # Terminal game (Python 3 + rich)
serve.py            # HTTP server to launch the web version
```

## Data Format

Each JSON file in `data/` is an array of objects with:

| Field | Required | Description |
|---|---|---|
| `de` | Yes | German word or phrase |
| `en` | Yes | English translation |
| `hint` | Yes | Memory aid or pronunciation tip |
| `example` | No | Example sentence |
| `conjugation` | No | Verb conjugation table |
| `context` | No | Usage context (e.g., "formal", "restaurant") |
| `opposite` | No | Antonym |
| `category` | No | Sub-category within the file |
| `difficulty` | No | Difficulty level (1-3, used in sentences) |

## Progress Storage

Progress is saved locally and persists between sessions:

- **Web**: `localStorage` key `deutsh_progress`
- **Terminal**: `~/.deutsh_progress.json`

Both use the same schema: XP, streak, per-word mastery (0-5 scale), correct/wrong counts.
