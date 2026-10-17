import time
from collections.abc import Callable

from app.agent.catalog import CatalogError
from app.backend_client import BackendClient, BackendError

# A chart is drawn by the query worker: the agent waits for it like it waits for a query.
WAIT_SECONDS = 60.0
POLL_SECONDS = 0.5


def _detail(error: BackendError) -> str:
    return str(error).split(": ", 1)[-1]


def with_missing_charts(answer: str, charts: list[dict]) -> str:
    """The answer, with at the end every chart of the run that it does not already show.

    The model is told to put each chart in its answer, but a chart that was drawn and then forgotten would be paid
    for and never seen: it goes at the end instead."""
    missing = [chart["markdown"] for chart in charts if chart["url"] not in answer]
    return answer if not missing else answer.rstrip() + "\n\n" + "\n\n".join(missing)


class ChartRunner:
    """Asks for a chart of the result of a query, by the backend, and waits for the query worker to draw it.

    A chart is a description (kind, columns, title), never code: the agent says what to draw, the worker draws.
    Every chart that was drawn is remembered in `created`, for the answer."""

    def __init__(
        self,
        client: BackendClient,
        run_id: str,
        created: list[dict],
        wait_seconds: float = WAIT_SECONDS,
        poll_seconds: float = POLL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.run_id = run_id
        self.created = created
        self.wait_seconds = wait_seconds
        self.poll_seconds = poll_seconds
        self._sleep = sleep
        self._clock = clock

    def run(self, query_id: str, spec: dict) -> dict:
        try:
            chart = self.client.create_chart(self.run_id, query_id, spec)
        except BackendError as error:
            if error.status_code in (404, 409, 422):  # refused on its merits (unknown query, too many charts...)
                raise CatalogError(f"Graphique refusé : {_detail(error)}") from error
            raise
        deadline = self._clock() + self.wait_seconds
        while chart["status"] in ("queued", "running"):
            if self._clock() >= deadline:
                raise CatalogError(f"Le graphique n'a pas été dessiné en {self.wait_seconds:g} secondes.")
            self._sleep(self.poll_seconds)
            chart = self.client.get_chart(chart["id"])
        if chart["status"] == "failed":
            columns = ", ".join(f"{c['name']} ({c['type']})" for c in chart.get("available_columns") or [])
            raise CatalogError(
                f"{chart['error'].rstrip('. ')}. Colonnes du résultat de la requête : {columns or 'inconnues'}."
            )
        done = {"chart_id": chart["id"], "title": chart["title"], "url": chart["url"], "markdown": chart["markdown"]}
        self.created.append(done)
        return {
            **done,
            "instruction": "Insère ce markdown tel quel dans ta réponse, à l'endroit où le graphique doit apparaître.",
        }
