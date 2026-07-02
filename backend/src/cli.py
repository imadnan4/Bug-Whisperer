"""Bug Whisperer CLI - Debug from your terminal.

Usage:
    bw "TypeError: Cannot read properties of null"
    bw --stack "at auth.ts:42" "TypeError: null.token"
    npm test 2>&1 | bw pipe
"""

import sys
import json
import re
from typing import Optional, List

import typer
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

app = typer.Typer(
    name="bw",
    help="Bug Whisperer - AI debugger with persistent memory",
    add_completion=False,
)

console = Console()
API_BASE = "http://localhost:8000"


def api_url(path: str) -> str:
    return f"{API_BASE}{path}"


@app.command()
def analyze(
    error: str = typer.Argument(..., help="The error message to analyze"),
    stack: Optional[str] = typer.Option(None, "--stack", "-s", help="Stack trace"),
    lang: str = typer.Option("python", "--lang", "-l", help="Programming language"),
    files: Optional[str] = typer.Option(None, "--files", "-f", help="Comma-separated files involved"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
):
    """Analyze a bug — checks memory for similar past bugs, then uses AI."""
    files_list = [f.strip() for f in files.split(",")] if files else []

    with console.status("[bold violet]Searching memory and analyzing...[/bold violet]", spinner="dots"):
        try:
            resp = httpx.post(
                api_url("/api/bugs/analyze"),
                json={
                    "error_message": error,
                    "stack_trace": stack or "",
                    "language": lang,
                    "files_involved": files_list,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError:
            console.print("\n[red]Connection failed. Is the backend running?[/red]")
            console.print("[dim]Make sure the server is running: uvicorn src.main:app --port 8000[/dim]")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise typer.Exit(code=1)

    if json_output:
        console.print_json(json.dumps(data))
        return

    recall = data["recall"]
    analysis = data["analysis"]

    # ── Header ──
    console.print()
    if recall["found"]:
        confidence = recall["confidence"]
        color = "green" if confidence > 0.7 else "yellow"
        console.print(
            Panel(
                f"[bold {color}]Memory Match![/bold {color}]\n"
                f"[dim]Confidence: {confidence:.0%}[/dim]\n"
                f"{recall.get('reasoning', '')}",
                border_style=color,
            )
        )
    else:
        console.print(
            Panel(
                "[bold yellow]New Bug Pattern[/bold yellow]\n"
                "[dim]No similar bug found in memory. Fresh analysis below.[/dim]",
                border_style="yellow",
            )
        )

    # ── Analysis ──
    severity = analysis.get("severity", "medium").upper()
    severity_color = {
        "CRITICAL": "red",
        "HIGH": "orange1",
        "MEDIUM": "yellow",
        "LOW": "green",
    }.get(severity, "white")

    console.print()

    # Root cause
    cause_text = Text(analysis.get("root_cause_analysis", "N/A"))
    console.print(Panel(cause_text, title="Root Cause", border_style="dim"))

    # Suggested fix
    fix_text = Text(analysis.get("suggested_fix", "N/A"))
    console.print(Panel(fix_text, title="Suggested Fix", border_style="green"))

    # Code snippet
    code = analysis.get("code_snippet")
    if code:
        console.print(Panel(Text(code, style="dim"), title="Code", border_style="dim"))

    # Files
    related = analysis.get("related_files", [])
    if related:
        files_text = Text("\n".join(f"  • {f}" for f in related))
        console.print(Panel(files_text, title="Files Involved", border_style="dim"))

    # ── Footer ──
    console.print()
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Severity", f"[{severity_color}]{severity}[/{severity_color}]")
    table.add_row("From Memory", "Yes" if recall.get("found") else "No")
    table.add_row("Save to Memory", "Run [bold]bw remember[/bold] after applying the fix")
    console.print(table)
    console.print()


@app.command()
def remember(
    root_cause: str = typer.Argument(..., help="Root cause of the bug"),
    fix: str = typer.Argument(..., help="How you fixed it"),
    code: Optional[str] = typer.Option(None, "--code", "-c", help="Fix code snippet"),
    files: Optional[str] = typer.Option(None, "--files", "-f", help="Files changed (comma-separated)"),
):
    """Save a bug and its fix to Cognee memory."""
    files_list = [f.strip() for f in files.split(",")] if files else []

    with console.status("[bold violet]Saving to memory...[/bold violet]", spinner="dots"):
        try:
            resp = httpx.post(
                api_url("/api/bugs/remember"),
                json={
                    "session_id": f"cli_{hash(root_cause) % 10000}",
                    "root_cause": root_cause,
                    "fix_description": fix,
                    "code_snippet": code,
                    "files_changed": files_list,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError:
            console.print("\n[red]Connection failed. Is the backend running?[/red]")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise typer.Exit(code=1)

    console.print()
    console.print("[bold green]OK[/bold green] Bug and fix saved to Cognee memory.")
    console.print(f"  Signature: [dim]{data['error_signature']}[/dim]")
    console.print()


@app.command()
def stats():
    """Show Bug Whisperer statistics."""
    with console.status("[bold violet]Loading stats...[/bold violet]", spinner="dots"):
        try:
            resp = httpx.get(api_url("/api/stats"), timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError:
            console.print("\n[red]Connection failed. Is the backend running?[/red]")
            raise typer.Exit(code=1)

    console.print()
    table = Table(title="Bug Whisperer Stats", box=box.ROUNDED)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Total Bugs", str(data.get("total_bugs", 0)))
    table.add_row("Recalled from Memory", str(data.get("bugs_recalled_from_memory", 0)))
    table.add_row("Recall Hit Rate", f"{data.get('recall_hit_rate', 0):.1f}%")
    table.add_row("Avg Match Confidence", f"{data.get('avg_confidence', 0):.1f}%")
    table.add_row("Time Saved", f"{data.get('estimated_time_saved_minutes', 0)} min")
    table.add_row("Memory Graph Nodes", str(data.get("memory_graph_size", 0)))

    console.print(table)

    top_errors = data.get("top_error_types", [])
    top_files = data.get("top_files", [])

    if top_errors:
        console.print()
        err_table = Table(title="Most Common Errors", box=box.SIMPLE)
        err_table.add_column("Error Type", style="dim")
        err_table.add_column("Count", justify="right")
        for e in top_errors:
            err_table.add_row(e["type"], str(e["count"]))
        console.print(err_table)

    if top_files:
        console.print()
        file_table = Table(title="Most Problematic Files", box=box.SIMPLE)
        file_table.add_column("File", style="dim")
        file_table.add_column("Bugs", justify="right")
        for f in top_files:
            file_table.add_row(f["file"], str(f["count"]))
        console.print(file_table)

    console.print()


# ── Error Extraction Patterns ──

ERROR_PATTERNS = {
    "python": re.compile(
        r"(Traceback \(most recent call last\):.*?)(?=\n\n|\nTraceback|\Z)",
        re.DOTALL,
    ),
    "javascript": re.compile(
        r"((?:TypeError|ReferenceError|SyntaxError|RangeError|Error|URIError|EvalError|InternalError)[^\n]*?(?:\n\s+at\s[^\n]*)+)",
        re.MULTILINE,
    ),
    "typescript": re.compile(
        r"((?:TypeError|ReferenceError|SyntaxError|RangeError|Error)[^\n]*?(?:\n\s+at\s[^\n]*)+)",
        re.MULTILINE,
    ),
    "go": re.compile(
        r"(panic:.*?(?:\n\s+.*?)*?)(?=\n\n|\npanic:|\Z)",
        re.DOTALL,
    ),
    "rust": re.compile(
        r"(error\[E\d+\]:.*?(?:\n\s+-->.*?)*?)(?=\n\n|\nerror\[|\Z)",
        re.DOTALL,
    ),
    "generic": re.compile(
        r"((?:error|Error|ERROR|FAIL|FAILURE|Exception|Fatal)[^\n]*?(?:\n\s+.*?){0,5})",
        re.MULTILINE,
    ),
}


def extract_errors(text: str, lang: str = "generic") -> List[str]:
    """Extract error messages from text output using language-specific patterns."""
    pattern = ERROR_PATTERNS.get(lang, ERROR_PATTERNS["generic"])
    matches = pattern.findall(text)
    if not matches and lang != "generic":
        matches = ERROR_PATTERNS["generic"].findall(text)
    return [m.strip() for m in matches if len(m.strip()) > 20]


def _check_backend():
    """Check if backend is reachable."""
    try:
        resp = httpx.get(api_url("/api/health"), timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


@app.command()
def pipe(
    lang: str = typer.Option("generic", "--lang", "-l", help="Language hint: python, javascript, typescript, go, rust"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
):
    """Read from stdin and analyze every error found in the output.

    Pipe your build, test, or any command output directly:
        npm test 2>&1 | bw pipe
        python main.py 2>&1 | bw pipe --lang python
        go build ./... 2>&1 | bw pipe --lang go
    """
    if sys.stdin.isatty():
        console.print("[yellow]Waiting for piped input...[/yellow]")
        console.print("[dim]Usage: some_command 2>&1 | bw pipe[/dim]")
        console.print("[dim]       npm test 2>&1 | bw pipe --lang typescript[/dim]")
        raise typer.Exit(code=0)

    if not _check_backend():
        console.print("[red]Cannot connect to backend. Is it running?[/red]")
        console.print("[dim]uvicorn src.main:app --port 8000[/dim]")
        raise typer.Exit(code=1)

    stdin_text = sys.stdin.read()
    if not stdin_text.strip():
        console.print("[dim]No input received.[/dim]")
        raise typer.Exit(code=0)

    errors = extract_errors(stdin_text, lang)

    if not errors:
        console.print("[dim]No errors detected in input.[/dim]")
        raise typer.Exit(code=0)

    console.print(f"\n[bold]Found {len(errors)} error(s) in output.[/bold]")
    console.print(f"[dim]Language hint: {lang}[/dim]\n")

    if json_output:
        results = []

    for i, error in enumerate(errors, 1):
        if len(errors) > 1:
            console.rule(f"[bold]Error {i}/{len(errors)}[/bold]")

        with console.status(f"[bold violet]Analyzing error {i}/{len(errors)}...[/bold violet]", spinner="dots"):
            try:
                resp = httpx.post(
                    api_url("/api/bugs/analyze"),
                    json={
                        "error_message": error[:500],
                        "stack_trace": "",
                        "language": lang,
                        "files_involved": [],
                    },
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                console.print(f"[red]Failed: {e}[/red]")
                continue

        if json_output:
            results.append({"error": error[:200], "result": data})
            continue

        recall = data["recall"]
        analysis = data["analysis"]

        console.print()
        if recall["found"]:
            confidence = recall["confidence"]
            color = "green" if confidence > 0.7 else "yellow"
            console.print(
                Panel(
                    f"[bold {color}]Memory Match ({confidence:.0%})[/bold {color}]\n"
                    f"[dim]{recall.get('reasoning', '')}[/dim]",
                    border_style=color,
                    title=f"[bold]Error {i}[/bold]",
                )
            )
        else:
            console.print(
                Panel(
                    f"[dim]{error[:300]}[/dim]",
                    border_style="yellow",
                    title=f"[bold]Error {i} - New Pattern[/bold]",
                )
            )

        console.print(Panel(Text(analysis.get("root_cause_analysis", "")), title="Root Cause", border_style="dim"))
        console.print(Panel(Text(analysis.get("suggested_fix", "")), title="Suggested Fix", border_style="green"))

        code = analysis.get("code_snippet")
        if code:
            console.print(Panel(Text(code, style="dim"), title="Code", border_style="dim"))

    if json_output:
        console.print_json(json.dumps(results))
        return

    console.print()
    summary = Table(title="Summary", box=box.ROUNDED)
    summary.add_column("Metric", style="dim")
    summary.add_column("Value")
    summary.add_row("Errors Found", str(len(errors)))
    summary.add_row("Analyzed", str(len(errors)))
    summary.add_row("Save to Memory", "bw remember 'cause' 'fix'")
    console.print(summary)
    console.print()


@app.callback()
def callback():
    """Bug Whisperer - AI debugger with persistent memory.

    Powered by Cognee's hybrid graph-vector memory layer.
    """


if __name__ == "__main__":
    app()
