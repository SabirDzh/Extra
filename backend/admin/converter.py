from typing import Any

from sqladmin.fields import (
    DateTimeField,
)
from sqladmin.forms import (
    ModelConverter as ModelConverterGeneric,
)
from sqladmin.forms import (
    converts,
)


class ModelConverter(ModelConverterGeneric):
    @staticmethod
    @converts("TIMESTAMPAware")
    def conv_timestamp_aware(
        model: type,
        prop: Any,
        kwargs: dict[str, Any],
    ) -> Any:
        return DateTimeField(**kwargs)
