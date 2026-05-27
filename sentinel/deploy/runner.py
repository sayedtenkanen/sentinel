from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..core.context import ReviewContext
from ..core.orchestrator import Orchestrator
from ..core.types import FileContext, ReviewScope
from ..monitor.tracer import Tracer
from ..reporting.report import to_json, to_markdown
from ..tools.config import agent_config, filter_files, load_config, suppress_findings


def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()


def collect_files(
    paths: list[str], exclude_patterns: list[str] | None = None
) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for path in paths:
        p = Path(path)
        if p.is_file():
            files.append((str(p), read_file(str(p))))
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                if ".venv" not in f.parts and "__pycache__" not in f.parts:
                    files.append((str(f), read_file(str(f))))
    if exclude_patterns:
        files = filter_files(files, {"exclude": exclude_patterns})
    return files


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Autonomous Code Review Bot — powered by sub-agents following the ADLC",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to review",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--disable-agent",
        action="append",
        choices=["static-analysis", "security", "style", "best-practices", "documentation"],
        help="Disable a specific agent sub-agent",
    )
    parser.add_argument(
        "--trace-dir",
        type=str,
        help="Directory to store trace logs (ADLC Monitor phase)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to .code-review.json config file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print trace events during review",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    exclude_patterns = cfg.get("exclude", [])
    if exclude_patterns and args.verbose:
        print(f"Excluding patterns: {exclude_patterns}", file=sys.stderr)

    tracer = Tracer(log_dir=args.trace_dir, enabled=True)

    disabled = set(args.disable_agent or [])

    from ..agents.best_practices import BestPracticesAgent
    from ..agents.documentation import DocumentationAgent
    from ..agents.security import SecurityAgent
    from ..agents.static_analysis import StaticAnalysisAgent
    from ..agents.style import StyleAgent

    sa_cfg = agent_config(cfg, "static-analysis")
    agents: list = [
        StaticAnalysisAgent(
            enabled="static-analysis" not in disabled,
            complexity_threshold=sa_cfg.get("complexity_threshold", 25),
            max_function_length=sa_cfg.get("max_function_length", 50),
            max_line_length=sa_cfg.get("max_line_length", 100),
            max_nesting_depth=sa_cfg.get("max_nesting_depth", 6),
        ),
        SecurityAgent(enabled="security" not in disabled),
        StyleAgent(enabled="style" not in disabled),
        BestPracticesAgent(enabled="best-practices" not in disabled),
        DocumentationAgent(enabled="documentation" not in disabled),
    ]

    orchestrator = Orchestrator(agents=agents, tracer=tracer)

    files = collect_files(args.paths, exclude_patterns)
    if not files:
        print("Error: no files found to review", file=sys.stderr)
        return 1

    file_contexts = [FileContext(path=path, content=content) for path, content in files]
    context = ReviewContext(
        scope=ReviewScope.FULL_FILE,
        files=file_contexts,
    )

    if args.verbose:
        print(f"🔍 Reviewing {len(files)} file(s)...", file=sys.stderr)

    report = orchestrator.review(context)
    if cfg.get("suppress"):
        for result in report.agent_results:
            result.findings = suppress_findings(result.findings, cfg)
    summary_text = orchestrator.summarize(report)

    if args.verbose:
        trace_summary = tracer.summary()
        print("\n📊 Trace Summary:", file=sys.stderr)
        for agent, dur in trace_summary["agent_durations_ms"].items():
            print(f"  {agent}: {dur:.1f}ms", file=sys.stderr)
        if trace_summary["errors"]:
            print(f"  Errors: {trace_summary['errors']}", file=sys.stderr)

    if args.format == "json":
        output = to_json(report, summary_text)
    else:
        output = to_markdown(report, summary_text)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        if args.verbose:
            print(f"\n✅ Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    if args.trace_dir:
        tracer.flush()
        if args.verbose:
            print(f"📝 Traces saved to {args.trace_dir}", file=sys.stderr)

    return 0 if report.score >= 50 else 1


if __name__ == "__main__":
    sys.exit(main())
