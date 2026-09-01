"""Agent-agnostic evaluator registry.

Every agent under `evals/agents/` registers its evaluators here under its own
name. The runner, the CI suite, and the production monitor all pull from this
one registry, so an evaluator is written once and reused in all three places.

Nothing in `evals/core/` may import from `evals/agents/` — the dependency runs
one way only. That is what makes adding agent #2 a matter of dropping in a new
package rather than editing the framework.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal

Suite = Literal["regression", "capability"]
Kind = Literal["code", "llm"]


@dataclass(frozen=True)
class RegisteredEvaluator:
    """One evaluator plus the metadata the runner and gates need."""

    name: str
    agent: str
    kind: Kind
    #: "invariant" checks gate CI (assert / hard fail); "signal" checks only trend.
    mode: Literal["invariant", "signal"]
    evaluator: Any
    #: Which suite this belongs to. Regression targets ~100%, capability 50-80%.
    suite: Suite = "regression"
    #: True when the evaluator needs no ground-truth label and can therefore run
    #: against live production spans, not just a golden dataset. This is the
    #: line between offline/CI evaluation and online monitoring.
    online: bool = False
    #: "maximize" (1.0 good) or "minimize" (1.0 bad, e.g. hallucination). Stored
    #: because a monitor that averages scores without it reports backwards.
    direction: Literal["maximize", "minimize"] = "maximize"
    #: Optional predicate over a reconstructed record deciding whether this
    #: evaluator means anything for that turn. Without it a judge scoped to
    #: no-result turns gets run on successful ones and reports a false alarm.
    applies: Any = None
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


class Registry:
    def __init__(self) -> None:
        self._by_agent: dict[str, list[RegisteredEvaluator]] = defaultdict(list)

    def register(
        self,
        *,
        agent: str,
        name: str,
        kind: Kind,
        mode: Literal["invariant", "signal"],
        suite: Suite = "regression",
        online: bool = False,
        direction: Literal["maximize", "minimize"] = "maximize",
        applies: Any = None,
        description: str = "",
        tags: Iterable[str] = (),
    ) -> Callable[[Any], Any]:
        """Decorator/registrar. Returns the evaluator unchanged so the module
        can also use it directly (e.g. in a pytest assert)."""

        def _register(evaluator: Any) -> Any:
            self._by_agent[agent].append(
                RegisteredEvaluator(
                    name=name,
                    agent=agent,
                    kind=kind,
                    mode=mode,
                    evaluator=evaluator,
                    suite=suite,
                    online=online,
                    direction=direction,
                    applies=applies,
                    description=description,
                    tags=tuple(tags),
                )
            )
            return evaluator

        return _register

    def for_agent(
        self,
        agent: str,
        *,
        kind: Kind | None = None,
        mode: str | None = None,
        suite: Suite | None = None,
        online: bool | None = None,
    ) -> list[RegisteredEvaluator]:
        out = self._by_agent.get(agent, [])
        if online is not None:
            out = [e for e in out if e.online == online]
        if kind is not None:
            out = [e for e in out if e.kind == kind]
        if mode is not None:
            out = [e for e in out if e.mode == mode]
        if suite is not None:
            out = [e for e in out if e.suite == suite]
        return out

    def agents(self) -> list[str]:
        return sorted(self._by_agent)


REGISTRY = Registry()
