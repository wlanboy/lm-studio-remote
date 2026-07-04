"""Load / unload model dialogs and the App mixin that drives them."""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select

from lm_remote.api_client import LMStudioClient


class _AppState(Protocol):
    """Attributes/methods `LoadUnloadMixin` needs from `LMStudioRemoteApp`.

    Used only as a `self` annotation below, never as a real base class, so
    it doesn't affect the runtime MRO of `LMStudioRemoteApp`.
    """

    client: LMStudioClient | None
    models_by_key: dict[str, dict[str, Any]]

    def log_message(self, message: str, level: str = ...) -> None: ...
    def refresh_models(self) -> object: ...
    def query_one(self, *args: Any, **kwargs: Any) -> Any: ...
    def push_screen(self, *args: Any, **kwargs: Any) -> Any: ...

    # sibling members of `LoadUnloadMixin` itself, needed because its
    # methods call each other through the `self: _AppState` annotation
    def _selected_model_key(self) -> str | None: ...
    def open_load_dialog(self) -> None: ...
    def do_load_model(self, params: dict[str, Any]) -> object: ...
    def open_unload_dialog(self) -> None: ...
    def do_unload_model(self, instance_id: str) -> object: ...


class LoadModelScreen(ModalScreen[dict[str, Any] | None]):
    """Form to load a model, prefilled with the selected model key."""

    DEFAULT_CSS = """
    LoadModelScreen {
        align: center middle;
    }
    #load-dialog {
        width: 60;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }
    #load-dialog Input, #load-dialog Checkbox {
        margin-bottom: 1;
    }
    """

    def __init__(self, model_key: str) -> None:
        super().__init__()
        self.model_key = model_key

    def compose(self) -> ComposeResult:
        with Vertical(id="load-dialog"):
            yield Label(f"Load model: [b]{self.model_key}[/b]")
            yield Input(placeholder="context_length (optional)", id="context-length")
            yield Input(placeholder="eval_batch_size (optional)", id="eval-batch-size")
            yield Input(placeholder="num_experts, MoE only (optional)", id="num-experts")
            yield Checkbox("Force flash attention on", id="flash-attention")
            yield Checkbox("Offload KV cache to GPU", id="offload-kv")
            with Horizontal():
                yield Button("Load", id="confirm", variant="success")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        def _int_or_none(widget_id: str) -> int | None:
            raw = self.query_one(f"#{widget_id}", Input).value.strip()
            return int(raw) if raw else None

        try:
            context_length = _int_or_none("context-length")
            eval_batch_size = _int_or_none("eval-batch-size")
            num_experts = _int_or_none("num-experts")
        except ValueError:
            self.app.notify("Numeric fields must be integers", severity="error")
            return

        result: dict[str, Any] = {
            "model": self.model_key,
            "context_length": context_length,
            "eval_batch_size": eval_batch_size,
            "num_experts": num_experts,
        }
        if self.query_one("#flash-attention", Checkbox).value:
            result["flash_attention"] = True
        if self.query_one("#offload-kv", Checkbox).value:
            result["offload_kv_cache_to_gpu"] = True
        self.dismiss(result)


class UnloadModelScreen(ModalScreen[str | None]):
    """Pick which loaded instance to unload."""

    DEFAULT_CSS = """
    UnloadModelScreen {
        align: center middle;
    }
    #unload-dialog {
        width: 70;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }
    """

    def __init__(self, instances: list[tuple[str, str]]) -> None:
        super().__init__()
        self.instances = instances

    def compose(self) -> ComposeResult:
        with Vertical(id="unload-dialog"):
            yield Label("Select instance to unload")
            yield Select(self.instances, id="instance-select")
            with Horizontal():
                yield Button("Unload", id="confirm", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        value = self.query_one("#instance-select", Select).value
        if value is Select.NULL:
            self.dismiss(None)
            return
        self.dismiss(str(value))


class LoadUnloadMixin:
    """Load/unload dialogs and workers, mixed into `LMStudioRemoteApp`."""

    def action_load_model(self: _AppState) -> None:
        if self.client is None:
            self.log_message("Connect to a server first", "warning")
            return
        self.open_load_dialog()

    def action_unload_model(self: _AppState) -> None:
        if self.client is None:
            self.log_message("Connect to a server first", "warning")
            return
        self.open_unload_dialog()

    def _selected_model_key(self: _AppState) -> str | None:
        table = self.query_one("#models-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return row_key.value if row_key is not None else None

    def open_load_dialog(self: _AppState) -> None:
        model_key = self._selected_model_key()
        if model_key is None:
            self.log_message("Select a model row first", "warning")
            return

        def _on_result(result: dict[str, Any] | None) -> None:
            if result is not None:
                self.do_load_model(result)

        self.push_screen(LoadModelScreen(model_key), _on_result)

    @work(exclusive=True, group="models")
    async def do_load_model(self: _AppState, params: dict[str, Any]) -> None:
        if self.client is None:
            return
        model = params.pop("model")
        try:
            response = await self.client.load_model(model, **params)
        except (httpx.HTTPError, OSError) as exc:
            self.log_message(f"Load failed: {exc}", "error")
            return
        self.log_message(
            f"Loaded {model} as {response.get('instance_id')} in "
            f"{response.get('load_time_seconds', '?')}s",
            "success",
        )
        self.refresh_models()

    def open_unload_dialog(self: _AppState) -> None:
        instances: list[tuple[str, str]] = []
        for model in self.models_by_key.values():
            for instance in model.get("loaded_instances") or []:
                instance_id = instance.get("id")
                if instance_id:
                    instances.append((instance_id, instance_id))
        if not instances:
            self.log_message("No loaded instances to unload", "warning")
            return

        def _on_result(instance_id: str | None) -> None:
            if instance_id is not None:
                self.do_unload_model(instance_id)

        self.push_screen(UnloadModelScreen(instances), _on_result)

    @work(exclusive=True, group="models")
    async def do_unload_model(self: _AppState, instance_id: str) -> None:
        if self.client is None:
            return
        try:
            await self.client.unload_model(instance_id)
        except (httpx.HTTPError, OSError) as exc:
            self.log_message(f"Unload failed: {exc}", "error")
            return
        self.log_message(f"Unloaded {instance_id}", "success")
        self.refresh_models()
