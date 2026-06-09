"""Central StrategyRegistry — plugin registration and lookup."""

from typing import Any


class StrategyRegistry:
    """Registry for all RAG pipeline strategies.

    Strategies register themselves with a stage name and strategy name.
    Registration is done via the @register decorator or direct call.
    """

    _strategies: dict[str, dict[str, type]] = {}
    _instances: dict[str, dict[str, Any]] = {}

    @classmethod
    def register(cls, stage: str, name: str):
        """Decorator: register a strategy class for a given stage."""
        def decorator(strategy_cls):
            cls._strategies.setdefault(stage, {})[name] = strategy_cls
            return strategy_cls
        return decorator

    @classmethod
    def get(cls, stage: str, name: str, **kwargs) -> Any:
        """Get an instance of a registered strategy by stage and name."""
        stage_strategies = cls._strategies.get(stage)
        if not stage_strategies:
            raise ValueError(f"No strategies registered for stage '{stage}'. Available stages: {list(cls._strategies.keys())}")
        strategy_cls = stage_strategies.get(name)
        if not strategy_cls:
            raise ValueError(f"Strategy '{name}' not found for stage '{stage}'. Available: {list(stage_strategies.keys())}")
        return strategy_cls(**kwargs)

    @classmethod
    def list_strategies(cls, stage: str | None = None) -> dict[str, list[str]]:
        """List all registered strategies, optionally filtered by stage."""
        if stage:
            return {stage: list(cls._strategies.get(stage, {}).keys())}
        return {s: list(strats.keys()) for s, strats in cls._strategies.items()}

    @classmethod
    def unregister(cls, stage: str, name: str) -> None:
        """Remove a strategy from the registry (useful for dynamic removal)."""
        if stage in cls._strategies and name in cls._strategies[stage]:
            del cls._strategies[stage][name]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered strategies."""
        cls._strategies.clear()
        cls._instances.clear()
