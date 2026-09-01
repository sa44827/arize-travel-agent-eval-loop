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
    ) -> list[RegisteredEvaluator]:
        out = self._by_agent.get(agent, [])
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
