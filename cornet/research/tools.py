"""SDK custom-tool surface. Functions run in the harness process."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from cornet.catalog.compat import check_compat
from cornet.catalog.compose import compose
from cornet.catalog.loader import list_packs, load_pack
from cornet.catalog.schema import ScenarioSpec
from cornet.catalog.smoke import smoke_test
from cornet.research.brief import Brief, dump_brief, load_brief
from cornet.research.jobs import JobQueue
from cornet.research.journal import append_journal, record_hypothesis, set_verdict
from cornet.research.session import ResearchSession, hash_eval, privilege_error
from cornet.research.stats import compare_samples

TOOL_NAMES = (
    "ask_user",
    "list_packs",
    "describe_pack",
    "check_compat",
    "compose",
    "smoke_test",
    "submit_experiment",
    "experiment_status",
    "leaderboard_summary",
    "compare",
    "read_run_artifacts",
    "record_hypothesis",
    "append_journal",
)


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    execute: Callable[[dict], Any]


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    body: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        body["required"] = required
    return body


class ToolContext:
    def __init__(self, session: ResearchSession, jobs: JobQueue, repo: Path) -> None:
        self.session = session
        self.jobs = jobs
        self.repo = repo
        self.brief: Brief | None = None

    def brief_path(self) -> Path:
        return self.session.task_dir / "research" / "brief.yaml"

    def load(self) -> Brief | None:
        path = self.brief_path()
        if path.is_file():
            self.brief = load_brief(path.read_text())
        return self.brief


def build_tools(ctx: ToolContext) -> dict[str, ToolDef]:
    def ask_user(args: dict) -> str:
        question = {
            "id": f"q{len(ctx.session.questions) + 1}",
            "prompt": args["prompt"],
            "options": list(args.get("options") or []),
            "allow_free_text": bool(args.get("allow_free_text", False)),
            "answer": None,
        }
        ctx.session.questions.append(question)
        ctx.session.save()
        return "question queued; end your turn"

    def list_packs_tool(args: dict) -> list[dict]:
        kind = args.get("kind")
        packs = list_packs(kind)
        return [{"name": pack.name, "kind": pack.kind, "description": pack.description} for pack in packs]

    def describe_pack(args: dict) -> dict:
        pack = load_pack(args["kind"], args["name"])
        return {
            "name": pack.name,
            "kind": pack.kind,
            "description": pack.description,
            "compatible": pack.compatible,
            "intake_questions": pack.intake_questions,
        }

    def check_compat_tool(args: dict) -> dict:
        reasons = check_compat(
            args["robot"],
            args["world"],
            args["network"],
            args.get("radio_sites"),
            args.get("population"),
            args.get("lane") or "v2.4-ns3.38",
            world_variant=args.get("world_variant"),
            ue_altitude_m=float(args.get("ue_altitude_m") or 1.5),
        )
        return {"ok": not reasons, "reasons": reasons}

    def compose_tool(args: dict) -> dict:
        spec = ScenarioSpec.model_validate(args["scenario"])
        dest = ctx.repo / "tasks" / spec.id
        compose(spec, dest, lane=spec.lane)
        return {"task": spec.id, "path": str(dest)}

    def smoke_tool(args: dict) -> dict:
        task = ctx.repo / "tasks" / args["task"]
        smoke_test(task)
        return {"ok": True, "task": args["task"]}

    def submit_experiment(args: dict) -> dict:
        brief = ctx.load()
        if brief is None:
            return {"error": "no brief"}
        overrides = dict(args.get("overrides") or {})
        allowed = {item.path: item.values for item in brief.independent_variables}
        for key, value in overrides.items():
            if key not in allowed:
                return {"error": f"override {key} is not an independent variable"}
            if value not in allowed[key]:
                return {"error": f"override {key}={value} is outside the brief"}
        current = hash_eval(ctx.session.task_dir)
        if ctx.session.eval_hash and current != ctx.session.eval_hash:
            return {"error": "evaluation is frozen"}
        if ctx.session.primary_metric and brief.dependent_variables:
            if ctx.session.primary_metric not in brief.dependent_variables:
                return {"error": "evaluation is frozen"}
        priv = privilege_error(ctx.session.task_dir)
        if priv:
            ask_user({"prompt": priv, "options": ["grant and resume", "stop"], "allow_free_text": False})
            return {"error": priv}
        repeats = int(args.get("repeats") or brief.repeats)
        seed = int(args.get("seed") or 1)
        job = ctx.jobs.submit(
            ctx.session.task_dir,
            overrides,
            repeats,
            seed,
            args.get("hypothesis_id"),
        )
        return {"job_id": job.job_id, "status": job.status}

    def experiment_status(args: dict) -> dict:
        try:
            job = ctx.jobs.status(args["job_id"])
        except KeyError:
            return {"error": f"unknown job {args['job_id']}"}
        return {
            "job_id": job.job_id,
            "status": job.status,
            "error": job.error,
            "entries": [entry.get("variant_id") for entry in job.entries],
        }

    def leaderboard_summary(args: dict) -> dict:
        path = ctx.session.task_dir / "leaderboard.json"
        if not path.is_file():
            return {"count": 0, "by_hypothesis": {}, "top": []}
        rows = json.loads(path.read_text())
        grouped: dict[str, list[float]] = {}
        for row in rows:
            if row.get("metric") is None:
                continue
            key = str(row.get("hypothesis_id") or row.get("variant_id"))
            grouped.setdefault(key, []).append(float(row["metric"]))
        aggregates = {
            key: {"n": len(values), "mean": sum(values) / len(values)}
            for key, values in grouped.items()
        }
        ranked = sorted(
            (row for row in rows if row.get("metric") is not None),
            key=lambda row: float(row["metric"]),
        )
        top = [
            {"variant_id": row.get("variant_id"), "metric": row.get("metric"), "seed": row.get("seed")}
            for row in ranked[:5]
        ]
        return {"count": len(rows), "by_hypothesis": aggregates, "top": top}

    def compare_tool(args: dict) -> dict:
        path = ctx.session.task_dir / "leaderboard.json"
        rows = json.loads(path.read_text()) if path.is_file() else []
        a_name, b_name = args["a"], args["b"]
        metric = args.get("metric")
        a_vals = _metrics(rows, a_name, metric)
        b_vals = _metrics(rows, b_name, metric)
        brief = ctx.load()
        alpha = brief.alpha if brief else 0.05
        expect = "different"
        hypothesis_id = args.get("hypothesis_id")
        if brief and hypothesis_id:
            match = next((item for item in brief.hypotheses if item.id == hypothesis_id), None)
            if match:
                expect = match.expect
        result = compare_samples(a_vals, b_vals, alpha=alpha, expect=expect)
        result["hypothesis_id"] = hypothesis_id
        result["evidence"] = [row.get("variant_id") for row in rows if _matches(row, a_name) or _matches(row, b_name)]
        if hypothesis_id:
            set_verdict(ctx.session.task_dir, hypothesis_id, result["verdict"], result["evidence"])
        path = ctx.session.task_dir / "research" / "comparisons.json"
        existing = json.loads(path.read_text()) if path.is_file() else []
        existing.append(result)
        path.write_text(json.dumps(existing))
        return result

    def read_run_artifacts(args: dict) -> dict:
        variant = args["variant_id"]
        path = ctx.session.task_dir / "leaderboard.json"
        rows = json.loads(path.read_text()) if path.is_file() else []
        row = next((item for item in rows if item.get("variant_id") == variant), None)
        if row is None:
            return {"error": f"unknown run {variant}"}
        return {
            "variant_id": variant,
            "status": row.get("status"),
            "metric": row.get("metric"),
            "seed": row.get("seed"),
            "config_hash": row.get("config_hash"),
            "timing_ok": row.get("timing_ok"),
        }

    def record_hypothesis_tool(args: dict) -> dict:
        from cornet.research.brief import Hypothesis

        if args.get("status") not in (None, "open"):
            return {"error": "verdicts come from compare"}
        hypothesis = Hypothesis.model_validate(args["hypothesis"])
        return record_hypothesis(ctx.session.task_dir, hypothesis)

    def append_journal_tool(args: dict) -> dict:
        append_journal(ctx.session.task_dir, args["text"])
        return {"ok": True}

    specs = [
        ("ask_user", "Queue a question for the user and end the turn.", _schema({"prompt": {"type": "string"}, "options": {"type": "array"}, "allow_free_text": {"type": "boolean"}}, ["prompt"]), ask_user),
        ("list_packs", "List catalogue packs.", _schema({"kind": {"type": "string"}}), list_packs_tool),
        ("describe_pack", "Describe one catalogue pack.", _schema({"kind": {"type": "string"}, "name": {"type": "string"}}, ["kind", "name"]), describe_pack),
        ("check_compat", "Check a robot, world, and network combination.", _schema({"robot": {"type": "string"}, "world": {"type": "string"}, "network": {"type": "string"}}, ["robot", "world", "network"]), check_compat_tool),
        ("compose", "Compile a catalogue scenario into a task directory.", _schema({"scenario": {"type": "object"}}, ["scenario"]), compose_tool),
        ("smoke_test", "Relay-smoke a compiled task.", _schema({"task": {"type": "string"}}, ["task"]), smoke_tool),
        ("submit_experiment", "Queue an experiment. Runs one at a time.", _schema({"overrides": {"type": "object"}, "repeats": {"type": "integer"}, "seed": {"type": "integer"}, "hypothesis_id": {"type": "string"}}), submit_experiment),
        ("experiment_status", "Poll a queued experiment.", _schema({"job_id": {"type": "string"}}, ["job_id"]), experiment_status),
        ("leaderboard_summary", "Aggregates and the top entries, not the raw file.", _schema({}), leaderboard_summary),
        ("compare", "Compare two variant groups and set the hypothesis verdict.", _schema({"a": {"type": "string"}, "b": {"type": "string"}, "metric": {"type": "string"}, "hypothesis_id": {"type": "string"}}, ["a", "b"]), compare_tool),
        ("read_run_artifacts", "Summarise one run.", _schema({"variant_id": {"type": "string"}}, ["variant_id"]), read_run_artifacts),
        ("record_hypothesis", "Open a hypothesis. Verdicts are rejected.", _schema({"hypothesis": {"type": "object"}}, ["hypothesis"]), record_hypothesis_tool),
        ("append_journal", "Append a journal paragraph.", _schema({"text": {"type": "string"}}, ["text"]), append_journal_tool),
    ]
    tools = {
        name: ToolDef(name=name, description=desc, input_schema=schema, execute=fn)
        for name, desc, schema, fn in specs
    }
    missing = [name for name in TOOL_NAMES if name not in tools]
    if missing:
        raise RuntimeError(f"missing tools: {missing}")
    return tools


def _matches(row: dict, name: str) -> bool:
    variant = str(row.get("variant_id") or "")
    return variant == name or variant.startswith(name + "_") or name in variant


def _metrics(rows: list[dict], name: str, metric: str | None) -> list[float]:
    values = []
    for row in rows:
        if not _matches(row, name):
            continue
        if metric and row.get("primary_metric") not in (None, metric):
            continue
        if row.get("metric") is None:
            continue
        values.append(float(row["metric"]))
    return values


def answer_question(session: ResearchSession, question_id: str, answer: str) -> None:
    for question in session.questions:
        if question["id"] == question_id:
            question["answer"] = answer
            session.save()
            brief_path = session.task_dir / "research" / "brief.yaml"
            if brief_path.is_file():
                brief = load_brief(brief_path.read_text())
                from cornet.research.brief import Decision

                brief.decisions.append(
                    Decision(name=question["prompt"], status="asked", answer=answer)
                )
                brief_path.write_text(dump_brief(brief))
            return
    raise KeyError(question_id)
