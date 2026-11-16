# Problem 2: Hardware Q&A Assistant for Linux Laptop

## Overview

A local, natural-language CLI chatbot that answers questions about the machine’s hardware by safely calling system inspection tools. The LLM never invents specs and never executes arbitrary shell commands.

### Core Flow
1. User asks a natural-language question.
2. LLM selects one or more allow-listed tools.
3. Tools are executed safely (`shell=False`, fixed binaries).
4. Raw output is parsed into structured JSON.
5. LLM answers using **only** the verified JSON.

## Safety Design (Interviewer Focus)

- **Strict allow-list** – LLM can only choose named tools; it cannot invent command strings.
- **No shell** – every tool is executed with `subprocess.run(..., shell=False)`.
- **Fixed arguments** – tools accept only validated scalar parameters (or none).
- **Scoped sudo** – only `dmidecode` is allowed via a sudoers rule; the rest of the agent runs as the normal user.
- **Anti-hallucination prompt** – system message forces the model to say “I cannot determine this…” when data is missing.

## Tools Implemented

| Tool name              | Command(s)                          | Requires root? |
|------------------------|-------------------------------------|----------------|
| `get_cpu_info`         | `lscpu`                             | No             |
| `get_memory_summary`   | `free -b`                           | No             |
| `get_block_devices`    | `lsblk -J ...`                      | No             |
| `get_pci_devices`      | `lspci -nn`                         | No             |
| `get_dmi_memory`       | `sudo dmidecode -t memory`          | Yes (scoped)   |
| `get_dmi_system`       | `sudo dmidecode -t system`          | Yes (scoped)   |

## Privilege Handling

Recommended production setup:

```bash
# /etc/sudoers.d/hw-assistant
youruser ALL=(ALL) NOPASSWD: /usr/sbin/dmidecode
```

If sudo is not configured the assistant falls back to `/proc` and `/sys` data and clearly reports limited information.

## Multi-turn Support

Previous tool results are kept in session memory. Follow-up questions such as “and what about the GPU?” reuse cached data when possible and only call new tools when necessary.

## Privacy

- Fully offline capable with Ollama (`llama3.2:3b` or `qwen2.5:7b`).
- Optional OpenAI / Anthropic fallback when the user explicitly enables it.
- No hardware data leaves the machine in the default local mode.

## Running

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: start a local model
# ollama run llama3.2:3b

python main.py
```

Example session:

```
You: How much RAM do I have?
Assistant: You have 16 GB of RAM installed ...

You: Can I add more, and how much?
Assistant: You currently use 1 of 2 slots. The board supports up to 64 GB, so you can add a stick of up to 32 GB.
```

## Design Notes for Interview

- Tool-calling design is the primary signal – the LLM only *selects* tools; it never constructs shell commands.
- Safety is enforced at the execution layer, not by hoping the model behaves.
- Accuracy is enforced by the system prompt + structured JSON only.