from app.models import SqlQuery
from app.repositories.base import BaseRepository


class SqlQueryRepository(BaseRepository[SqlQuery]):
    model = SqlQuery
