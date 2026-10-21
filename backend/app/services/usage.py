from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TokenUsage
from app.repositories import TokenUsageRepository
from app.services.actor import Actor


@dataclass
class UsageSums:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


@dataclass
class NodeUsage(UsageSums):
    node: str = ""


@dataclass
class DayUsage(UsageSums):
    day: date | None = None


@dataclass
class ModelUsage(UsageSums):
    model: str | None = None


@dataclass
class UserUsage(UsageSums):
    user_id: str = ""
    email: str | None = None


@dataclass
class Usage:
    days: int
    totals: UsageSums
    by_node: list[NodeUsage] = field(default_factory=list)
    by_day: list[DayUsage] = field(default_factory=list)
    by_model: list[ModelUsage] = field(default_factory=list)
    by_user: list[UserUsage] = field(default_factory=list)  # administrators only


def _sums(row) -> dict:
    return {
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "total_tokens": row.total_tokens,
        "calls": row.calls,
    }


class UsageService:
    """Tokens consumed by the agent's LLM calls, per node, day, model and person."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.usage = TokenUsageRepository(session)

    async def record(self, run_id, user_id: str, email: str | None, model: str | None, calls: list[dict]) -> None:
        """Stores the calls of a run, replacing any reported before for it (staged: the caller commits)."""
        await self.usage.delete_for_run(run_id)
        for call in calls:
            await self.usage.add(
                TokenUsage(
                    run_id=run_id,
                    user_id=user_id,
                    user_email=email,
                    model=model,
                    node=call["node"],
                    input_tokens=call["input_tokens"],
                    output_tokens=call["output_tokens"],
                    total_tokens=call["total_tokens"],
                )
            )

    async def mine(self, actor: Actor, days: int) -> Usage:
        return await self._report(days, actor.user_id, with_users=False)

    async def overall(self, days: int, user_id: str | None = None) -> Usage:
        """Everyone's consumption, or only `user_id`'s. Callers must already have checked for an administrator."""
        return await self._report(days, user_id, with_users=True)

    async def _report(self, days: int, user_id: str | None, with_users: bool) -> Usage:
        since = datetime.now(UTC) - timedelta(days=days)
        return Usage(
            days=days,
            totals=UsageSums(**_sums(await self.usage.totals(since, user_id))),
            by_node=[NodeUsage(node=r.node, **_sums(r)) for r in await self.usage.by_node(since, user_id)],
            by_day=[DayUsage(day=r.day, **_sums(r)) for r in await self.usage.by_day(since, user_id)],
            by_model=[ModelUsage(model=r.model, **_sums(r)) for r in await self.usage.by_model(since, user_id)],
            by_user=[UserUsage(user_id=r.user_id, email=r.email, **_sums(r)) for r in await self.usage.by_user(since)]
            if with_users
            else [],
        )
