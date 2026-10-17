from app.tasks import file_analysed, forget_file, rebuild_collection, rebuild_user


class FakeIndexer:
    def __init__(self, forgets: bool = True, rebuilt: int = 3) -> None:
        self.forgets, self.rebuilt, self.calls = forgets, rebuilt, []

    def file_analysed(self, analysis_id):
        self.calls.append(("file_analysed", analysis_id))

    def forget_file(self, collection_id, file_id):
        self.calls.append(("forget", collection_id, file_id))
        return self.forgets

    def rebuild_collection(self, collection_id):
        self.calls.append(("rebuild_collection", collection_id))
        return self.rebuilt

    def rebuild_user(self, email):
        self.calls.append(("rebuild_user", email))
        return self.rebuilt


def test_each_task_delegates_to_the_indexer() -> None:
    indexer = FakeIndexer(rebuilt=7)

    file_analysed("an1", indexer)
    assert forget_file("c1", "f1", indexer) == "removed"
    assert rebuild_collection("c9", indexer) == 7
    assert rebuild_user("marie@example.fr", indexer) == 7

    assert indexer.calls == [
        ("file_analysed", "an1"),
        ("forget", "c1", "f1"),
        ("rebuild_collection", "c9"),
        ("rebuild_user", "marie@example.fr"),
    ]


def test_forget_file_reports_when_the_file_was_not_indexed() -> None:
    assert forget_file("c1", "f1", FakeIndexer(forgets=False)) == "absent"


def test_the_tasks_have_the_names_the_backend_sends_and_run_on_the_index_queue() -> None:
    from app.celery_app import celery_app

    routes = celery_app.conf.task_routes
    names = {file_analysed.name, forget_file.name, rebuild_collection.name, rebuild_user.name}

    assert names == {"index.file_analysed", "index.forget_file", "index.rebuild_collection", "index.rebuild_user"}
    assert all(routes[name] == {"queue": "index"} for name in names)
