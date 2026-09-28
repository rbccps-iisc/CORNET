"""Research session state machine. Agents are called per phase."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from cornet.catalog.compat import check_compat
from cornet.config.loader import load_unified
from cornet.research.brief import dump_brief, load_brief
from cornet.research.critic import deterministic_checks, has_blocking, parse_challenge_report
from cornet.research.gitwork import commit_accepted, foreign_changes, revert_paths
from cornet.research.jobs import JobQueue
from cornet.research.journal import record_hypothesis
from cornet.research.report import check_evidence, render_report
from cornet.research.session import ResearchSession, budget_exhausted, find_session, hash_eval, new_session
from cornet.research.tools import ToolContext, answer_question, build_tools


def _text(result: Any) -> str:
    if isinstance(result, str):
        return result
    for attr in ("text", "result"):
        value = getattr(result, attr, None)
        if callable(value):
            value = value()
        if isinstance(value, str):
            return value
    return str(result)


def _yaml_block(text: str) -> str:
    if "```" not in text:
        return text
    inside = False
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines) if lines else text


def present_questions(session: ResearchSession, *, input_fn=input, output_fn=print) -> list[str]:
    delivered = []
    for question in session.questions:
        if question.get("answer"):
            continue
        options = question.get("options") or []
        output_fn(question["prompt"])
        if options:
            output_fn("options: " + ", ".join(options))
        answer = input_fn("> ").strip()
        answer_question(session, question["id"], answer)
        delivered.append(f"{question['prompt']}: {answer}")
    return delivered


def run_session(
    task_dir: Path,
    question: str,
    *,
    researcher: Any | None = None,
    critic: Any | None = None,
    executor=None,
    repo: Path | None = None,
    resume_id: str | None = None,
    input_fn=input,
    output_fn=print,
) -> ResearchSession:
    repo = repo or Path.cwd()
    if resume_id:
        session = find_session(repo, resume_id)
        pending = present_questions(session, input_fn=input_fn, output_fn=output_fn)
        if pending and researcher is not None:
            _send(researcher, "Answers:\n" + "\n".join(pending))
    else:
        session = new_session(task_dir, question)
        session.wall_started = time.time()
        session.save()
    output_fn(session.session_id)
    jobs = JobQueue(executor)
    ctx = ToolContext(session, jobs, repo)
    tools = build_tools(ctx)
    if researcher is None or critic is None:
        researcher, critic = _sdk_pair(session, tools)
    _run_phases(session, ctx, tools, researcher, critic, repo, output_fn)
    return session


def _sdk_pair(session: ResearchSession, tools: dict):
    import os

    from cornet.research.agents import create_local_agent, sdk_custom_tools

    api_key = os.environ["CURSOR_API_KEY"]
    model = os.environ.get("CORNET_RESEARCH_MODEL", "composer-2.5")
    from cursor_sdk import Cursor

    listed = [item.id if hasattr(item, "id") else str(item) for item in Cursor.models.list()]
    custom = sdk_custom_tools(tools)
    researcher = create_local_agent(
        api_key=api_key,
        model=model,
        cwd=session.task_dir,
        custom_tools=custom,
        allow_web_search=session.allow_web_search,
        available_models=listed,
        resume_id=session.agent_ids.get("researcher"),
    )
    critic = create_local_agent(
        api_key=api_key,
        model=os.environ.get("CORNET_CRITIC_MODEL", model),
        cwd=session.task_dir,
        custom_tools=custom,
        allow_web_search=False,
        available_models=listed,
        resume_id=session.agent_ids.get("critic"),
    )
    return researcher, critic


def _send(agent: Any, prompt: str) -> str:
    from cornet.research.agents import send_with_retry

    def _log(agent_id, run_id) -> None:
        if agent_id or run_id:
            print(f"agent_id={agent_id} run_id={run_id}")

    if hasattr(agent, "send"):
        try:
            return _text(send_with_retry(agent, prompt, _log))
        except Exception:
            if type(getattr(agent, "send")(prompt)).__name__ == "type":
                raise
            result = agent.send(prompt)
            return _text(result)
    return _text(agent(prompt))


def _run_phases(session, ctx, tools, researcher, critic, repo: Path, output_fn) -> None:
    task_rel = f"tasks/{session.task_id}"
    if session.phase in {"intake", "brief"}:
        session.phase = "brief"
        session.consumed["agent_runs"] = session.consumed.get("agent_runs", 0) + 1
        raw = _send(researcher, f"Write brief.yaml for: {session.question}")
        brief = load_brief(_yaml_block(raw))
        for hypothesis in brief.hypotheses:
            record_hypothesis(session.task_dir, hypothesis)
        path = ctx.brief_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_brief(brief))
        ctx.brief = brief
        if brief.scenario:
            reasons = check_compat(
                brief.scenario["robot"],
                brief.scenario["world"],
                brief.scenario["network"],
                brief.scenario.get("radio_sites"),
                brief.scenario.get("population"),
                brief.lane,
                world_variant=brief.scenario.get("world_variant"),
            )
            if reasons:
                _send(researcher, "incompatible scenario: " + "; ".join(reasons))
                session.save()
                return
        session.phase = "critique"
        session.save()

    brief = ctx.load()
    assert brief is not None
    if session.phase == "critique":
        report = _send(critic, "Review this brief and return a Challenge Report:\n" + dump_brief(brief))
        challenges = parse_challenge_report(report) + deterministic_checks(brief)
        if has_blocking(challenges):
            _send(researcher, "Blocking challenges:\n" + json.dumps(challenges))
            session.save()
            return
        session.phase = "compile"
        session.save()

    if session.phase == "compile":
        if brief.scenario and brief.scenario.get("robot"):
            from cornet.catalog.compose import compose
            from cornet.catalog.schema import ScenarioSpec

            spec = ScenarioSpec.model_validate(brief.scenario)
            dest = repo / "tasks" / spec.id
            compose(spec, dest, lane=brief.lane)
            if dest != session.task_dir:
                old_research = session.task_dir / "research"
                if old_research.is_dir():
                    dest_research = dest / "research"
                    dest_research.mkdir(parents=True, exist_ok=True)
                    for item in old_research.iterdir():
                        target = dest_research / item.name
                        if item.is_file() and not target.exists():
                            target.write_bytes(item.read_bytes())
                session.task_dir = dest
                session.task_id = spec.id
                session.save()
        session.eval_hash = hash_eval(session.task_dir)
        config = load_unified(session.task_dir / "config.yaml")
        session.primary_metric = config.experiment.primary_metric
        session.phase = "loop"
        session.save()

    if session.phase == "loop":
        if budget_exhausted(session, now=time.time()):
            session.phase = "report"
        else:
            proposal = _send(researcher, "Propose the next experiment batch as JSON with hypothesis_id, repeats, and groups.")
            batch = _parse_batch(proposal, brief)
            challenges = deterministic_checks(brief, batch.get("override_sets"))
            if has_blocking(challenges):
                revert_paths(repo, foreign_changes(repo, task_rel)) if _is_git(repo) else None
                _send(researcher, "Blocking checks:\n" + json.dumps(challenges))
                session.save()
                return
            result: dict = {}
            for group in batch["groups"]:
                if budget_exhausted(session, now=time.time()):
                    break
                result = tools["submit_experiment"].execute(
                    {
                        "overrides": group["overrides"],
                        "repeats": batch["repeats"],
                        "seed": int(group.get("seed") or 1),
                        "hypothesis_id": batch["hypothesis_id"],
                    }
                )
                if result.get("error"):
                    output_fn(result["error"])
                    session.phase = "report"
                    break
                job = ctx.jobs.wait(result["job_id"])
                session.consumed["trials"] = session.consumed.get("trials", 0) + job.repeats
                config = load_unified(session.task_dir / "config.yaml")
                session.consumed["sim_seconds"] = session.consumed.get("sim_seconds", 0) + job.repeats * config.experiment.duration
            if len(batch["groups"]) >= 2 and not result.get("error"):
                tools["compare"].execute(
                    {
                        "a": batch["groups"][0]["name"],
                        "b": batch["groups"][1]["name"],
                        "hypothesis_id": batch["hypothesis_id"],
                    }
                )
            if _is_git(repo):
                bad = foreign_changes(repo, task_rel)
                if bad:
                    revert_paths(repo, bad)
                else:
                    commit_accepted(repo, task_rel, f"research: accept batch {session.session_id}")
            session.phase = "report"
            session.save()

    if session.phase == "report":
        _write_report(session, brief, researcher)
        session.phase = "done"
        session.save()


def _parse_batch(text: str, brief) -> dict:
    raw = _yaml_block(text).strip()
    if raw.startswith("{"):
        data = json.loads(raw)
    else:
        data = {}
    groups = data.get("groups")
    if not groups and brief.independent_variables:
        variable = brief.independent_variables[0]
        groups = [
            {"name": str(value), "overrides": {variable.path: value}, "seed": 1 + index}
            for index, value in enumerate(variable.values[:2])
        ]
    return {
        "hypothesis_id": data.get("hypothesis_id") or brief.hypotheses[0].id,
        "repeats": int(data.get("repeats") or brief.repeats),
        "groups": groups or [],
        "override_sets": [group.get("overrides") or {} for group in (groups or [])],
    }


def _write_report(session: ResearchSession, brief, researcher) -> None:
    from cornet.research.journal import load_hypotheses

    discussion = _send(researcher, "Write the discussion section only.")
    board_path = session.task_dir / "leaderboard.json"
    rows = json.loads(board_path.read_text()) if board_path.is_file() else []
    comparisons_path = session.task_dir / "research" / "comparisons.json"
    comparisons = json.loads(comparisons_path.read_text()) if comparisons_path.is_file() else []
    hypotheses = load_hypotheses(session.task_dir)
    text = render_report(
        question=session.question,
        brief_summary=brief.question,
        hypotheses=hypotheses,
        comparisons=comparisons,
        leaderboard=rows,
        discussion=discussion,
        scenario=brief.scenario,
    )
    # Comparisons live on the hypothesis evidence; re-read after compare stored verdicts.
    report_path = session.task_dir / "research" / "report.md"
    report_path.write_text(text)
    problems = check_evidence(text, board_path)
    if problems:
        report_path.write_text(text + "\nEvidence problems: " + ", ".join(problems) + "\n")


def _is_git(repo: Path) -> bool:
    return (repo / ".git").exists()
