"""Hermes memory provider for mindledger.

This provider is intentionally read-only. It recalls indexed memory with the
mindledger CLI and injects short, source-linked context before each model turn.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


DEFAULT_COMMAND = "mind"
DEFAULT_PROVIDER = "onnx"
DEFAULT_TOP_K = 5
DEFAULT_TIMEOUT = 20


def _read_plugin_config(hermes_home: str | Path) -> dict[str, Any]:
    config_path = Path(hermes_home) / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        import yaml

        data = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
    except Exception as exc:
        logger.debug("Failed to read Hermes config for mindledger: %s", exc)
        return {}

    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return {}
    config = plugins.get("mindledger")
    return config if isinstance(config, dict) else {}


def _coerce_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _source_label(source: str) -> str:
    if source.startswith("/home/ubuntu/AI-Memory/"):
        return "AI-Memory"
    if source.startswith("/home/ubuntu/.openclaw/"):
        return "OpenClaw"
    return "Other"


class MindledgerMemoryProvider(MemoryProvider):
    @property
    def name(self) -> str:
        return "mindledger"

    def __init__(self) -> None:
        self.command = os.environ.get("MINDLEDGER_COMMAND", DEFAULT_COMMAND)
        self.collection = os.environ.get("MINDLEDGER_COLLECTION", "")
        self.provider = os.environ.get("MINDLEDGER_PROVIDER", DEFAULT_PROVIDER)
        self.top_k = _coerce_int(os.environ.get("MINDLEDGER_TOP_K"), DEFAULT_TOP_K)
        self.timeout = _coerce_int(os.environ.get("MINDLEDGER_TIMEOUT"), DEFAULT_TIMEOUT)

    def is_available(self) -> bool:
        return shutil.which(self.command) is not None

    def initialize(self, session_id: str, **kwargs) -> None:
        del session_id
        config = _read_plugin_config(kwargs.get("hermes_home", Path.home() / ".hermes"))

        self.command = str(config.get("command") or self.command)
        self.collection = str(config.get("collection") or self.collection)
        self.provider = str(config.get("provider") or self.provider)
        self.top_k = _coerce_int(config.get("top_k"), self.top_k)
        self.timeout = _coerce_int(config.get("timeout"), self.timeout)

    def system_prompt_block(self) -> str:
        return (
            "# mindledger Memory\n"
            "Read-only long-term memory recall is active. Relevant indexed notes "
            "may be injected before a turn with source paths."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        del session_id
        query = (query or "").strip()
        if not query:
            return ""

        try:
            results = self._search(query)
        except Exception as exc:
            logger.debug("mindledger recall failed: %s", exc)
            return ""

        if not results:
            return ""

        lines = ["## mindledger recall"]
        for index, item in enumerate(results, start=1):
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            source = str(item.get("source") or "unknown source")
            label = _source_label(source)
            start_line = item.get("start_line")
            score = item.get("score")
            location = source
            if start_line:
                location = f"{source}:{start_line}"
            score_text = ""
            if isinstance(score, (int, float)):
                score_text = f" score={score:.3f}"
            lines.append(f"{index}. [{label}] Source: {location}{score_text}\n{content}")

        return "\n\n".join(lines) if len(lines) > 1 else ""

    def _search(self, query: str) -> list[dict[str, Any]]:
        cmd = [
            self.command,
            "search",
            query,
            "--json-output",
            "--top-k",
            str(self.top_k),
        ]
        if self.collection:
            cmd.extend(["--collection", self.collection])
        if self.provider:
            cmd.extend(["--provider", self.provider])

        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if proc.returncode != 0:
            logger.debug("mindledger search failed: %s", proc.stderr.strip())
            return []

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            logger.debug("mindledger search returned invalid JSON: %s", exc)
            return []
        return data if isinstance(data, list) else []

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "mindledger_search",
                "description": "Search read-only long-term memory indexed by mindledger.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language memory search query.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of results.",
                        },
                    },
                    "required": ["query"],
                },
            }
        ]

    def handle_tool_call(self, tool_name: str, args: dict[str, Any], **kwargs) -> str:
        del kwargs
        if tool_name != "mindledger_search":
            return json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})

        original_top_k = self.top_k
        try:
            if "top_k" in args:
                self.top_k = _coerce_int(args.get("top_k"), self.top_k)
            results = self._search(str(args.get("query") or ""))
            return json.dumps({"success": True, "results": results}, ensure_ascii=False)
        finally:
            self.top_k = original_top_k

    def get_config_schema(self) -> list[dict[str, Any]]:
        return [
            {"key": "command", "description": "mindledger CLI command", "default": DEFAULT_COMMAND},
            {"key": "collection", "description": "mindledger collection name", "default": ""},
            {"key": "provider", "description": "Embedding provider", "default": DEFAULT_PROVIDER},
            {"key": "top_k", "description": "Default number of recalled chunks", "default": str(DEFAULT_TOP_K)},
            {"key": "timeout", "description": "Search timeout in seconds", "default": str(DEFAULT_TIMEOUT)},
        ]

    def save_config(self, values: dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml

            existing = {}
            if config_path.exists():
                existing = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["mindledger"] = values
            config_path.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")
        except Exception as exc:
            logger.debug("Failed to save mindledger config: %s", exc)


def register(ctx) -> None:
    ctx.register_memory_provider(MindledgerMemoryProvider())
