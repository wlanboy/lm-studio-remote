# lm-studio-remote

Eine Python-basierte Terminal-UI (gebaut mit [Textual](https://textual.textualize.io/)), um eine oder mehrere [LM Studio](https://lmstudio.ai/)-Instanzen im lokalen Netzwerk fernzusteuern, ohne die LM Studio Desktop-App selbst zu öffnen. Die App scannt das lokale /24-Subnetz nach erreichbaren LM-Studio-REST-API-Servern, merkt sich gefundene Server in einer JSON-Datei und erlaubt es, sich per Dropdown mit einem Server zu verbinden (optional mit API-Token). Nach dem Verbinden zeigt eine Tabelle alle verfügbaren Modelle inklusive Typ, Publisher, Parametergröße, Dateigröße, Format und Ladezustand an. Modelle können direkt aus der TUI geladen (mit Optionen wie Context Length, Flash Attention, Eval Batch Size) und wieder entladen werden; ein Log-Tab protokolliert alle Aktionen und Fehler.

## Voraussetzungen

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/) als Paket- und Projektmanager

## Bauen

```bash
uv sync
```

Installiert alle Laufzeit- und Dev-Abhängigkeiten (`httpx`, `textual`, sowie `pytest`, `pyright`, `ruff`) in eine lokale virtuelle Umgebung.

## Starten

```bash
uv run main.py
```

## Tests & Linting

```bash
uv run pytest
uv run pyright
uv run ruff check .
```

## Alias

Um die App von überall aus starten zu können, z.B. folgenden Alias in `~/.bashrc` bzw. `~/.zshrc` eintragen:

```bash
alias lm-remote="uv run --project ~/git/lm-studio-remote main.py"
```

Danach reicht `lm-remote` in einem neuen Shell-Fenster.
