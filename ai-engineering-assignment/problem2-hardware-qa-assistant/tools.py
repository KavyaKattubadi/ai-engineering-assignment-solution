"""
Strict allow-listed system tools + safe execution.

The LLM may only request tools by name.  No arbitrary shell is ever executed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Allow-list – maps logical tool name → fixed argv list
# ---------------------------------------------------------------------------

ALLOW_LISTED_TOOLS: Dict[str, List[str]] = {
    "get_cpu_info": ["lscpu"],
    "get_memory_summary": ["free", "-b"],
    "get_block_devices": [
        "lsblk", "-J", "-o",
        "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,ROTA,TRAN,FSTYPE"
    ],
    "get_pci_devices": ["lspci", "-nn"],
    "get_dmi_memory": ["sudo", "-n", "/usr/sbin/dmidecode", "-t", "memory"],
    "get_dmi_system": ["sudo", "-n", "/usr/sbin/dmidecode", "-t", "system"],
}

# Tools that may be missing on some systems
OPTIONAL_TOOLS = {"get_dmi_memory", "get_dmi_system"}


def available_tools() -> List[str]:
    """Return tools whose primary binary is present on the system."""
    available = []
    for name, argv in ALLOW_LISTED_TOOLS.items():
        # For sudo tools check the real binary
        binary = argv[-3] if argv[0] == "sudo" else argv[0]
        if shutil.which(binary) or (name in OPTIONAL_TOOLS):
            available.append(name)
    return available


# ---------------------------------------------------------------------------
# Safe execution
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Execute an allow-listed tool and return structured JSON.
    Raises ValueError on unknown tools.
    """
    if tool_name not in ALLOW_LISTED_TOOLS:
        raise ValueError(f"Unauthorized tool: {tool_name}")

    cmd = ALLOW_LISTED_TOOLS[tool_name]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,          # we handle non-zero ourselves
            timeout=8,
            shell=False,          # CRITICAL – no shell injection possible
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Tool '{tool_name}' timed out after 8 seconds."}
    except FileNotFoundError:
        return {"error": f"Binary for '{tool_name}' not found on this system."}
    except Exception as e:
        return {"error": f"Execution failed: {type(e).__name__}: {e}"}

    if result.returncode != 0:
        # sudo -n fails with 1 when password would be required
        stderr = (result.stderr or "").strip()
        if "password" in stderr.lower() or result.returncode == 1:
            return {
                "error": "Privilege required. Configure scoped sudo for dmidecode "
                         "or the assistant will use /proc & /sys fallbacks.",
                "hint": "Add:  user ALL=(ALL) NOPASSWD: /usr/sbin/dmidecode"
            }
        return {"error": f"Command failed (rc={result.returncode}): {stderr[:300]}"}

    return parse_output(tool_name, result.stdout)


# ---------------------------------------------------------------------------
# Parsers – turn messy CLI output into clean dicts
# ---------------------------------------------------------------------------

def parse_output(tool_name: str, stdout: str) -> Dict[str, Any]:
    if tool_name == "get_block_devices":
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"error": "Failed to parse lsblk JSON", "raw": stdout[:500]}

    if tool_name == "get_cpu_info":
        data: Dict[str, str] = {}
        for line in stdout.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                data[key.strip()] = val.strip()
        return data

    if tool_name == "get_memory_summary":
        # free -b output
        lines = [l for l in stdout.splitlines() if l.strip()]
        if len(lines) < 2:
            return {"raw": stdout}
        headers = lines[0].split()
        values = lines[1].split()
        # mem line is usually index 1
        mem = dict(zip(headers, values[1:]))  # skip "Mem:"
        return {
            "total_bytes": int(mem.get("total", 0)),
            "used_bytes": int(mem.get("used", 0)),
            "free_bytes": int(mem.get("free", 0)),
            "available_bytes": int(mem.get("available", mem.get("free", 0))),
            "total_gb": round(int(mem.get("total", 0)) / (1024**3), 2),
            "used_gb": round(int(mem.get("used", 0)) / (1024**3), 2),
            "available_gb": round(int(mem.get("available", 0)) / (1024**3), 2),
        }

    if tool_name == "get_pci_devices":
        devices = []
        for line in stdout.splitlines():
            line = line.strip()
            if line:
                devices.append(line)
        return {"devices": devices}

    if tool_name == "get_dmi_memory":
        return _parse_dmi_memory(stdout)

    if tool_name == "get_dmi_system":
        return _parse_dmi_system(stdout)

    return {"raw_output": stdout[:2000]}


def _parse_dmi_memory(stdout: str) -> Dict[str, Any]:
    max_cap_match = re.search(r"Maximum Capacity:\s*(.+)", stdout, re.I)
    # Collect every "Size:" line that belongs to a Memory Device
    size_matches = re.findall(r"Size:\s*(.+)", stdout, re.I)

    installed = []
    empty = 0
    for s in size_matches:
        s = s.strip()
        if "No Module Installed" in s or s.lower() == "no module installed":
            empty += 1
        else:
            installed.append(s)

    # Also try to count slots from "Number Of Devices" if present
    num_devices = re.search(r"Number Of Devices:\s*(\d+)", stdout, re.I)

    return {
        "maximum_capacity": max_cap_match.group(1).strip() if max_cap_match else "Unknown",
        "total_slots": int(num_devices.group(1)) if num_devices else len(size_matches),
        "used_slots": len(installed),
        "free_slots": empty if empty else (len(size_matches) - len(installed)),
        "installed_modules": installed,
    }


def _parse_dmi_system(stdout: str) -> Dict[str, Any]:
    fields = {}
    for key in ("Manufacturer", "Product Name", "Version", "Serial Number", "UUID", "Family"):
        m = re.search(rf"{key}:\s*(.+)", stdout, re.I)
        if m:
            fields[key.lower().replace(" ", "_")] = m.group(1).strip()
    return fields


# ---------------------------------------------------------------------------
# Tool definitions for the LLM (OpenAI / Ollama function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_cpu_info",
            "description": "Get CPU model, cores, threads, architecture, frequency and cache details via lscpu.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_summary",
            "description": "Get current RAM usage summary (total / used / available) in bytes and GB.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_block_devices",
            "description": "List block devices (disks, partitions) with size, type, mount point, model, transport (NVMe/SATA) and rotational flag.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pci_devices",
            "description": "List PCI devices including GPU, network, storage controllers (lspci).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dmi_memory",
            "description": "Get physical RAM topology: maximum capacity supported by the motherboard, number of slots, which slots are occupied, and module sizes. Requires scoped sudo for dmidecode.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dmi_system",
            "description": "Get system manufacturer, product name, serial number and UUID from DMI/SMBIOS.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]