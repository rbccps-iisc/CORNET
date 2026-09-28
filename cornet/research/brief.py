"""Validated research brief."""

from __future__ import annotations

from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


class Hypothesis(BaseModel):
    id: str
    claim: str
    prediction: str
    falsification: str
    expect: Literal["a_lower", "a_higher", "different"] = "different"


class IndependentVariable(BaseModel):
    path: str
    values: list[Any]


class GuardMetric(BaseModel):
    name: str
    tolerance: float = 0.0
    higher_is_better: bool = True


class Decision(BaseModel):
    name: str
    status: Literal["derived", "asked"]
    justification: str = ""
    answer: str = ""


class Budget(BaseModel):
    max_trials: int = 40
    max_sim_seconds: float = 3600.0
    max_wall_hours: float = 8.0
    max_agent_runs: int = 40


class Brief(BaseModel):
    question: str
    hypotheses: list[Hypothesis]
    independent_variables: list[IndependentVariable] = Field(default_factory=list)
    dependent_variables: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    scenario: dict[str, Any] | None = None
    standard: bool = True
    lane: str = "v2.4-ns3.38"
    repeats: int = 5
    budget: Budget = Field(default_factory=Budget)
    decisions: list[Decision] = Field(default_factory=list)
    guard_metrics: list[GuardMetric] = Field(default_factory=list)
    factorial: bool = False
    alpha: float = 0.05

    @model_validator(mode="after")
    def _reject_isd(self) -> Brief:
        for variable in self.independent_variables:
            if variable.path == "network.radio_sites.isd_m" or variable.path.endswith(".isd_m"):
                raise ValueError(
                    f"ISD is derived from the deployment; {variable.path} cannot be an independent variable"
                )
        if self.repeats < 1:
            raise ValueError("repeats must be >= 1")
        return self


def load_brief(text: str) -> Brief:
    data = yaml.safe_load(text) or {}
    try:
        return Brief.model_validate(data)
    except ValidationError as exc:
        missing = [
            err
            for err in exc.errors()
            if err.get("type") == "missing" and "falsification" in err.get("loc", ())
        ]
        if missing:
            hyp = missing[0]["loc"]
            ident = hyp[1] if len(hyp) > 1 else "?"
            raise ValueError(f"hypothesis {ident} is missing falsification") from exc
        raise


def dump_brief(brief: Brief) -> str:
    return yaml.safe_dump(brief.model_dump(mode="json"), sort_keys=False)
