"""Model list filtering, sorting, and rendering, and the App mixin that
drives the models table."""

from __future__ import annotations

import re
from typing import Any, Protocol

import httpx
from rich.text import Text
from textual import work
from textual.widgets import DataTable, Input

from lm_remote.api_client import LMStudioClient, LMStudioModel


def _human_size(num_bytes: Any) -> str:
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


_UNIT_MULTIPLIERS = {
    "": 1.0,
    "B": 1.0,
    "K": 1_000.0,
    "KB": 1_000.0,
    "M": 1_000_000.0,
    "MB": 1_000_000.0,
    "G": 1_000_000_000.0,
    "GB": 1_000_000_000.0,
    "T": 1_000_000_000_000.0,
    "TB": 1_000_000_000_000.0,
    "P": 1_000_000_000_000_000.0,
    "PB": 1_000_000_000_000_000.0,
}
_NUMBER_UNIT_RE = re.compile(r"^\s*(-?[\d.]+)\s*([A-Za-z]*)\s*$")


def _column_sort_key(cell: Any) -> tuple[int, float, str]:
    """Sort key that treats '-' as lowest and numbers with unit suffixes
    (e.g. '1.2GB', '7B' params) as numeric rather than lexicographic."""
    text = cell.plain if isinstance(cell, Text) else str(cell)
    if text in ("-", ""):
        return (0, 0.0, "")
    match = _NUMBER_UNIT_RE.match(text)
    if match:
        multiplier = _UNIT_MULTIPLIERS.get(match.group(2).upper())
        if multiplier is not None:
            return (1, float(match.group(1)) * multiplier, text.lower())
    return (2, 0.0, text.lower())


class _AppState(Protocol):
    """Attributes/methods `ModelsTableMixin` needs from `LMStudioRemoteApp`.

    Used only as a `self` annotation below, never as a real base class, so
    it doesn't affect the runtime MRO of `LMStudioRemoteApp`.
    """

    client: LMStudioClient | None
    models_by_key: dict[str, LMStudioModel]
    _all_models: list[LMStudioModel]
    _sort_column_key: Any
    _sort_reverse: bool

    def log_message(self, message: str, level: str = ...) -> None: ...
    def query_one(self, *args: Any, **kwargs: Any) -> Any: ...

    # sibling members of `ModelsTableMixin` itself
    def _render_models_table(self) -> int: ...
    def _apply_sort(self, table: DataTable) -> None: ...
    def _model_matches(self, model: LMStudioModel, query: str) -> bool: ...
    def refresh_models(self) -> object: ...


class ModelsTableMixin:
    """Model table filtering, sorting, and refresh, mixed into `LMStudioRemoteApp`."""

    def action_refresh_models(self: _AppState) -> None:
        self.refresh_models()

    def action_focus_search(self: _AppState) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self: _AppState, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._render_models_table()

    def on_input_submitted(self: _AppState, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.query_one("#models-table", DataTable).focus()

    @staticmethod
    def _model_matches(model: LMStudioModel, query: str) -> bool:
        haystack = " ".join(
            str(value)
            for value in (
                model.type,
                model.publisher,
                model.key,
                model.display_name,
                model.params_string,
                model.format,
            )
        ).lower()
        return query in haystack

    def _render_models_table(self: _AppState) -> int:
        query = self.query_one("#search-input", Input).value.strip().lower()
        table = self.query_one("#models-table", DataTable)
        table.clear()
        shown = 0
        for model in self._all_models:
            if query and not self._model_matches(model, query):
                continue
            shown += 1
            loaded = model.loaded_instances
            cells = (
                model.type,
                model.publisher,
                model.key,
                model.display_name,
                model.params_string,
                _human_size(model.size_bytes),
                model.format or "-",
                str(len(loaded)) if loaded else "-",
            )
            if loaded:
                cells = tuple(Text(str(cell), style="bold green") for cell in cells)
            table.add_row(*cells, key=model.key)
        self._apply_sort(table)
        return shown

    def _apply_sort(self: _AppState, table: DataTable) -> None:
        if self._sort_column_key is not None:
            table.sort(self._sort_column_key, key=_column_sort_key, reverse=self._sort_reverse)

    @work(exclusive=True, group="models")
    async def refresh_models(self: _AppState) -> None:
        if self.client is None:
            return
        try:
            models = await self.client.list_models()
        except (httpx.HTTPError, OSError) as exc:
            self.log_message(f"Failed to list models: {exc}", "error")
            return

        self.models_by_key = {model.key: model for model in models}
        self._all_models = models
        shown = self._render_models_table()
        if shown != len(models):
            self.log_message(f"Loaded {len(models)} model(s), {shown} match current filter")
        else:
            self.log_message(f"Loaded {len(models)} model(s)")

    def on_data_table_header_selected(self: _AppState, event: DataTable.HeaderSelected) -> None:
        if self._sort_column_key == event.column_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column_key = event.column_key
            self._sort_reverse = False
        self._apply_sort(event.data_table)
        direction = "descending" if self._sort_reverse else "ascending"
        self.log_message(f"Sorted by {event.label.plain} ({direction})")
