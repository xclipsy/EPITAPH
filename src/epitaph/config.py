"""Configuración del proyecto (.epitaph/config.toml)."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import ConfigError
from .scheduler.trigger import parse_spec

CONFIG_DIR = ".epitaph"
CONFIG_FILE = "config.toml"


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ProjectCfg(_Model):
    name: str = ""
    target_path: str = ""
    output_language: str = "es"
    ignore_file: str = ".epitaphignore"


class TriggerSafetyCfg(_Model):
    debounce_seconds: float = 4.0
    cooldown_seconds: float = 30.0
    only_if_changed: bool = True
    max_run_seconds: int = 120
    skip_while_chatting: bool = True
    idle_seconds: int = 60


class TriggerCfg(_Model):
    default: str = "interval:5"
    overrides: dict[str, str] = Field(default_factory=dict)
    safety: TriggerSafetyCfg = Field(default_factory=TriggerSafetyCfg)

    @field_validator("default")
    @classmethod
    def _validate_default(cls, value: str) -> str:
        try:
            parse_spec(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return value

    @field_validator("overrides")
    @classmethod
    def _validate_overrides(cls, value: dict[str, str]) -> dict[str, str]:
        for feature, spec in value.items():
            if spec == "inherit":
                continue
            try:
                parse_spec(spec)
            except ValueError as exc:
                raise ValueError(f"{feature}: {exc}") from exc
        return value


class FeaturesCfg(_Model):
    readme: bool = True
    requirements: bool = True
    suggestions: bool = True


class ReadmeCfg(_Model):
    path: str = "README.md"
    preset: str = "estandar"
    sections: list[str] = Field(
        default_factory=lambda: [
            "overview",
            "install",
            "usage",
            "structure",
            "architecture",
            "requirements",
            "development",
            "license",
        ]
    )
    max_sections: int = 12
    include_tree: bool = True
    tree_depth: int = 3
    include_badges: bool = False
    tone: str = "neutral"
    verbosity: str = "normal"


class PreferencesCfg(_Model):
    enabled: bool = True
    path: str = ".epitaph/preferences.toml"
    confirm_from_chat: bool = True
    max_directives: int = 20
    max_directive_chars: int = 240
    inherit_global: bool = True


class RequirementsCfg(_Model):
    path: str = "requirements.txt"
    mode: str = "suggest"
    auto_apply: bool = False


class SuggestionsCfg(_Model):
    path: str = "suggestions.md"
    max_items: int = 15
    include_llm: bool = True


class LLMRolesCfg(_Model):
    summarizer: str = "qwen2.5-coder:1.5b"
    writer: str = "qwen2.5-coder:3b"
    advisor: str = "qwen2.5-coder:3b"
    chat: str = "qwen2.5-coder:3b"


class LLMParamsCfg(_Model):
    num_ctx: int = 4096
    num_predict: int = 600
    num_thread: int = 7
    temperature: float = 0.2
    keep_alive: str = "30m"


class LLMCfg(_Model):
    backend: str = "ollama"
    base_url: str = "http://localhost:11434"
    auto_select: bool = True
    roles: LLMRolesCfg = Field(default_factory=LLMRolesCfg)
    params: LLMParamsCfg = Field(default_factory=LLMParamsCfg)


class PermissionsCfg(_Model):
    write_readme: str = "ask"
    write_requirements: str = "deny"
    write_suggestions: str = "allow"
    write_code: str = "deny"
    network: bool = False


class SafetyCfg(_Model):
    require_clean_git: bool = True
    backup_retention: int = 20
    audit: bool = True


class UICfg(_Model):
    theme: str = "epitaph"
    animations: bool = True
    stream: bool = True


class Config(_Model):
    project: ProjectCfg = Field(default_factory=ProjectCfg)
    trigger: TriggerCfg = Field(default_factory=TriggerCfg)
    features: FeaturesCfg = Field(default_factory=FeaturesCfg)
    readme: ReadmeCfg = Field(default_factory=ReadmeCfg)
    preferences: PreferencesCfg = Field(default_factory=PreferencesCfg)
    requirements: RequirementsCfg = Field(default_factory=RequirementsCfg)
    suggestions: SuggestionsCfg = Field(default_factory=SuggestionsCfg)
    llm: LLMCfg = Field(default_factory=LLMCfg)
    permissions: PermissionsCfg = Field(default_factory=PermissionsCfg)
    safety: SafetyCfg = Field(default_factory=SafetyCfg)
    ui: UICfg = Field(default_factory=UICfg)

    # ------------------------------------------------------------------ paths

    @staticmethod
    def dir_for(root: Path) -> Path:
        return Path(root) / CONFIG_DIR

    @classmethod
    def path_for(cls, root: Path) -> Path:
        env = os.getenv("EPITAPH_CONFIG")
        if env:
            return Path(env).expanduser()
        return cls.dir_for(root) / CONFIG_FILE

    @classmethod
    def load(cls, root: Path) -> Config:
        path = cls.path_for(root)
        if not path.exists():
            raise ConfigError(
                f"No existe la configuración en {path}",
                hint="ejecuta `epitaph init` para crearla",
            )
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"configuración inválida en {path}: {exc}") from exc
        try:
            return cls.model_validate(raw)
        except Exception as exc:  # pydantic ValidationError
            raise ConfigError(f"configuración inválida en {path}: {exc}") from exc

    @classmethod
    def load_or_default(cls, root: Path) -> Config:
        try:
            return cls.load(root)
        except ConfigError:
            return cls.default(Path(root).name)

    @classmethod
    def default(cls, project_name: str = "") -> Config:
        cfg = cls()
        cfg.project.name = project_name
        return cfg

    def save(self, root: Path) -> Path:
        path = self.path_for(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(self.model_dump(mode="python")), encoding="utf-8")
        return path

    # --------------------------------------------------------------- helpers

    def trigger_for(self, feature: str) -> str:
        override = self.trigger.overrides.get(feature, "inherit")
        return self.trigger.default if override == "inherit" else override

    def project_name(self, root: Path) -> str:
        return self.project.name or Path(root).resolve().name


# --------------------------------------------------------------------- TOML


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"valor TOML no soportado: {type(value)!r}")


def dumps(data: dict[str, Any]) -> str:
    lines: list[str] = []
    _emit_table(lines, [], data)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _emit_table(lines: list[str], path: list[str], table: dict[str, Any]) -> None:
    scalars = {
        key: value
        for key, value in table.items()
        if value is not None and not isinstance(value, dict)
    }
    subs = {
        key: value
        for key, value in table.items()
        if value is not None and isinstance(value, dict)
    }

    if path:
        lines.append(f"[{'.'.join(path)}]")
    for key, value in scalars.items():
        lines.append(f"{key} = {_toml_value(value)}")
    if scalars and subs:
        lines.append("")

    for index, (key, value) in enumerate(subs.items()):
        _emit_table(lines, [*path, key], value)
        if index < len(subs) - 1:
            lines.append("")
