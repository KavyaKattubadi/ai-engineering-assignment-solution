#!/usr/bin/env python3
"""
Hardware Q&A Assistant – CLI entry point.

Usage:
    python main.py                          # uses OPENAI_API_KEY / default model
    python main.py --model llama3.2:3b --base-url http://localhost:11434/v1
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from agent import HardwareAgent
from tools import available_tools

app = typer.Typer(add_completion=False, help="Local Linux Hardware Q&A Assistant")
console = Console()


@app.command()
def chat(
    model: str = typer.Option(
        "gpt-4o-mini",
        "--model", "-m",
        help="Model name (OpenAI or Ollama tag)",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        help="OpenAI-compatible base URL (e.g. http://localhost:11434/v1 for Ollama)",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="API key (defaults to OPENAI_API_KEY env var)",
    ),
):
    """Start an interactive hardware Q&A session."""

    console.print(Panel.fit(
        "[bold cyan]Linux Hardware Q&A Assistant[/bold cyan]\n"
        "Ask natural-language questions about this machine.\n"
        "Type [bold]exit[/bold] or [bold]quit[/bold] to leave, [bold]reset[/bold] to clear memory.",
        border_style="cyan",
    ))

    tools = available_tools()
    console.print(f"[dim]Available tools: {', '.join(tools) or 'none'}[/dim]\n")

    if not tools:
        console.print("[red]No system inspection tools found. Exiting.[/red]")
        raise typer.Exit(1)

    agent = HardwareAgent(model=model, base_url=base_url, api_key=api_key)

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Bye.[/dim]")
            break
        if user_input.lower() == "reset":
            agent.reset()
            console.print("[yellow]Conversation memory cleared.[/yellow]\n")
            continue

        with console.status("[bold blue]Thinking…[/bold blue]", spinner="dots"):
            try:
                answer = agent.ask(user_input)
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                continue

        console.print(Panel(Markdown(answer), title="[bold]Assistant[/bold]", border_style="blue"))
        console.print()


if __name__ == "__main__":
    app()