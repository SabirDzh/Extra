from pydantic import BaseModel, Field


# начать использовать в зависимостях контроллеров, вместо ручного написания, так как есть единое место изменив которое можно настроить все остальные
# query_filter: Annotated[BaseFilter, Query()]
class BaseFilter(BaseModel):
    limit: int = Field(10, ge=0, le=100)
    offset: int = Field(0, ge=0, le=100)
