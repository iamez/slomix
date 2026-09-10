"""GET /api/datasets — the dataset register (docs/design/19 §5, slice 1).

Public and read-only: it says what the site can show, what collects it and
what it costs, not what any user chose. Typed, so the SPA's generated
types carry the shape and the drift checker can see it."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from website.backend.services.dataset_registry import (
    REGISTRY_VERSION,
    DatasetDescriptor,
    get_registry,
)

router = APIRouter()


class DatasetRegistry(BaseModel):
    registry_version: str
    count: int
    datasets: list[DatasetDescriptor]


@router.get("/datasets", response_model=DatasetRegistry)
async def list_datasets() -> DatasetRegistry:
    """Every dataset the site can show, with its collector, its collection
    switch, the pages it is shown on by default, what it depends on and its
    measured cold cost where one exists."""
    datasets = get_registry()
    return DatasetRegistry(registry_version=REGISTRY_VERSION, count=len(datasets), datasets=datasets)
