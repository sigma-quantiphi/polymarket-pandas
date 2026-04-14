"""Property-based tests for pandera schemas.

Hypothesis generates DataFrames matching each schema and asserts they validate
round-trip. Catches coercion bugs the mocked unit tests miss (e.g. a nullable
int column declared as ``int64`` instead of the nullable ``Int64`` dtype).
"""

from __future__ import annotations

import pandera.pandas as pa
import pytest

from polymarket_pandas import schemas


def _iter_dataframe_models() -> list[type[pa.DataFrameModel]]:
    """Discover every pandera DataFrameModel exported by schemas.py."""
    models: list[type[pa.DataFrameModel]] = []
    for name in dir(schemas):
        obj = getattr(schemas, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, pa.DataFrameModel)
            and obj is not pa.DataFrameModel
            and not name.startswith("_")
        ):
            models.append(obj)
    return models


SCHEMAS = _iter_dataframe_models()


@pytest.mark.parametrize("schema_cls", SCHEMAS, ids=lambda s: s.__name__)
def test_schema_strategy_round_trips(schema_cls: type[pa.DataFrameModel]) -> None:
    """Every schema must yield a DataFrame that re-validates under itself."""
    schema = schema_cls.to_schema()
    try:
        strategy = schema.strategy(size=5)
    except pa.errors.SchemaDefinitionError:
        pytest.skip(
            f"{schema_cls.__name__} has no hypothesis strategy (likely uses un-inferrable dtypes)"
        )
    df = strategy.example()
    schema.validate(df)
