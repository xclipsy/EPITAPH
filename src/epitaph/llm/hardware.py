"""Detección de hardware y recomendación de modelos."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Hardware:
    system: str = platform.system()
    machine: str = platform.machine()
    cpu_count: int = os.cpu_count() or 4
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpu: str = ""
    gpu_vram_gb: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def has_gpu(self) -> bool:
        return bool(self.gpu) and self.gpu_vram_gb > 0


def detect() -> Hardware:
    hw = Hardware()
    total, available = _read_memory()
    hw.ram_total_gb = round(total, 1)
    hw.ram_available_gb = round(available, 1)
    hw.gpu, hw.gpu_vram_gb = _read_gpu()
    if not hw.ram_total_gb:
        hw.ram_total_gb = 8.0
        hw.ram_available_gb = 4.0
        hw.notes.append("No se pudo leer la memoria; se asume un perfil conservador.")
    return hw


def _read_memory() -> tuple[float, float]:
    system = platform.system()
    if system == "Linux":
        try:
            values: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, _, rest = line.partition(":")
                values[key] = int(rest.strip().split()[0])
            total = values.get("MemTotal", 0) / 1024 / 1024
            available = values.get("MemAvailable", values.get("MemFree", 0)) / 1024 / 1024
            return total, available
        except (OSError, ValueError, IndexError):
            return 0.0, 0.0
    if system == "Darwin":
        try:
            total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip()) / 1024**3
            return total, total * 0.5
        except (subprocess.SubprocessError, ValueError):
            return 0.0, 0.0
    if system == "Windows":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # type: ignore[attr-defined]
            return status.ullTotalPhys / 1024**3, status.ullAvailPhys / 1024**3
        except Exception:
            return 0.0, 0.0
    return 0.0, 0.0


def _read_gpu() -> tuple[str, float]:
    if shutil.which("nvidia-smi"):
        try:
            output = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
            ).strip()
            if output:
                first = output.splitlines()[0]
                name, _, memory = first.partition(",")
                return name.strip(), round(float(memory.strip()) / 1024, 1)
        except (subprocess.SubprocessError, ValueError):
            pass
    if shutil.which("rocm-smi"):
        return "AMD ROCm", 0.0
    return "", 0.0


def estimate_ram_gb(model: dict) -> float:
    size = model.get("size") or 0
    if size:
        return round(size / 1024**3 + 1.0, 1)
    params = str(model.get("details", {}).get("parameter_size", "")).upper()
    try:
        billions = float(params.rstrip("B"))
    except ValueError:
        billions = 3.0
    return round(billions * 0.75 + 1.0, 1)


def estimate_tokens_per_second(model: dict, hw: Hardware) -> float:
    params = str(model.get("details", {}).get("parameter_size", "")).upper()
    try:
        billions = float(params.rstrip("B"))
    except ValueError:
        billions = 3.0
    if hw.has_gpu:
        return round(60.0 / max(billions, 1.0), 1)
    return round(22.0 / max(billions, 1.0) * (hw.cpu_count / 8), 1)


def viable(model: dict, hw: Hardware) -> tuple[bool, str]:
    required = estimate_ram_gb(model)
    budget = hw.ram_available_gb or hw.ram_total_gb * 0.5
    if required + 1.0 <= budget:
        return True, "viable"
    return False, f"requiere ~{required:.1f} GB y hay ~{budget:.1f} GB libres"
