from app.tasks import forget_file, rebuild_index, run_analysis


class Indexer:
    def __init__(self, forgets: bool = True, rebuilt: int = 3) -> None:
        self.forgets, self.rebuilt, self.calls = forgets, rebuilt, []

    def forget_file(self, collection_id: str, file_id: str) -> bool:
        self.calls.append(("forget", collection_id, file_id))
        return self.forgets

    def rebuild(self, collection_id: str) -> int:
        self.calls.append(("rebuild", collection_id))
        return self.rebuilt


def test_forget_file_task_reports_whether_the_file_was_in_the_index() -> None:
    assert forget_file("c1", "f1", Indexer(forgets=True)) == "removed"
    assert forget_file("c1", "f1", Indexer(forgets=False)) == "absent"


def test_forget_file_task_delegates_with_the_given_ids() -> None:
    indexer = Indexer()

    forget_file("c1", "f1", indexer)

    assert indexer.calls == [("forget", "c1", "f1")]


def test_rebuild_task_returns_the_number_of_files_indexed() -> None:
    indexer = Indexer(rebuilt=7)

    assert rebuild_index("c9", indexer) == 7
    assert indexer.calls == [("rebuild", "c9")]


def test_the_tasks_are_routed_to_the_analysis_queue_under_the_names_the_backend_sends() -> None:
    from app.celery_app import celery_app

    routes = celery_app.conf.task_routes
    names = {run_analysis.name, forget_file.name, rebuild_index.name}

    assert names == {"analysis.run", "analysis.forget_file", "analysis.rebuild_index"}
    assert all(routes[name] == {"queue": "analysis"} for name in names)
