# lm-studio-remote

Eine Python-basierte Terminal-UI (gebaut mit [Textual](https://textual.textualize.io/)), um eine oder mehrere [LM Studio](https://lmstudio.ai/)-Instanzen im lokalen Netzwerk fernzusteuern, ohne die LM Studio Desktop-App selbst zu öffnen. Die App scannt das lokale /24-Subnetz nach erreichbaren LM-Studio-REST-API-Servern, merkt sich gefundene Server samt optionalem API-Token in einer JSON-Datei (`lmstudioserver.json`, unverschlüsselt) und erlaubt es, sich per Dropdown mit einem Server zu verbinden. Ein Hintergrund-Healthcheck prüft alle bekannten Server periodisch und zeigt den Status als Ampel-Symbol im Dropdown sowie neben dem verbundenen Server an. Nach dem Verbinden zeigt eine Tabelle alle verfügbaren Modelle inklusive Typ, Publisher, Parametergröße, Dateigröße, Format und Ladezustand an. Modelle können direkt aus der TUI geladen (mit Optionen wie Context Length, Flash Attention, Eval Batch Size) und wieder entladen werden; ein Log-Tab protokolliert alle Aktionen und Fehler.

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

## Docker

```bash
docker build -t lm-studio-remote .
docker run --rm -it -e TERM -e COLORTERM -v ./data:/app/data lm-studio-remote
```

Der Container braucht ein Terminal (`-it`), da es sich um eine Textual-TUI handelt. `/app/data` enthält `lmstudioserver.json` und sollte als Volume gemountet werden, damit gefundene Server über Container-Neustarts hinweg erhalten bleiben. Bei einem Bind-Mount (`-v ./data:/app/data`) muss das Host-Verzeichnis vorher `chown 1000:1000` bekommen, da der Container als non-root User `1000` läuft; ein benanntes Docker-Volume (wie oben) funktioniert ohne diesen Schritt.

`-e TERM -e COLORTERM` (ohne Wert) reicht die Werte aus der Host-Shell in den Container durch. Docker übernimmt Umgebungsvariablen wie `TERM`/`COLORTERM` **nicht** automatisch, auch nicht mit `-it` – ohne sie erkennt Textual/Rich im Container eine geringere Farbtiefe und die Styles (Theme-Farben, Hintergründe) sehen anders aus als im normalen Terminal. Falls die Host-Shell `COLORTERM` nicht setzt (`echo $COLORTERM` prüfen), kann es auch explizit gesetzt werden: `-e COLORTERM=truecolor`.

## Alias

Um die App von überall aus starten zu können, z.B. folgenden Alias in `~/.bashrc` bzw. `~/.zshrc` eintragen:

```bash
alias lm-remote="uv run --project ~/git/lm-studio-remote main.py"
```

Danach reicht `lm-remote` in einem neuen Shell-Fenster.
