from collections.abc import Callable
from typing import Any

import pytest

from ogion.backup_targets.base_target import BaseBackupTarget
from ogion.backup_targets.targets_mapping import get_target_cls_map
from ogion.config import BackupTargetEnum, UploadProviderEnum
from ogion.models import backup_target_models, upload_provider_models
from ogion.models.models_mapping import get_provider_map, get_target_map
from ogion.upload_providers.base_provider import BaseUploadProvider
from ogion.upload_providers.providers_mapping import get_provider_cls_map


def test_get_target_map_contains_all_enums_and_has_valid_value_types() -> None:
    mapping = get_target_map()
    for target in BackupTargetEnum:
        assert target in mapping
    assert len(BackupTargetEnum) == len(mapping)

    for cls in mapping.values():
        assert issubclass(cls, backup_target_models.TargetModel)


def test_get_provider_map_contains_all_enums_and_has_valid_value_types() -> None:
    mapping = get_provider_map()
    for target in UploadProviderEnum:
        assert target in mapping
    assert len(UploadProviderEnum) == len(mapping)

    for cls in mapping.values():
        assert issubclass(cls, upload_provider_models.ProviderModel)


def test_get_target_cls_map_contains_all_enums_and_has_valid_value_types() -> None:
    mapping = get_target_cls_map()
    for target in BackupTargetEnum:
        assert target in mapping
    assert len(BackupTargetEnum) == len(mapping)

    for cls in mapping.values():
        assert issubclass(cls, BaseBackupTarget)


def test_get_provider_cls_map_contains_all_enums_and_has_valid_value_types() -> None:
    mapping = get_provider_cls_map()
    for target in UploadProviderEnum:
        assert target in mapping
    assert len(UploadProviderEnum) == len(mapping)

    for cls in mapping.values():
        assert issubclass(cls, BaseUploadProvider)


@pytest.mark.parametrize(
    "mapping_func",
    [get_target_map, get_target_cls_map, get_provider_map, get_provider_cls_map],
)
def test_all_mappings_value_classes_are_unique(
    mapping_func: Callable[[], dict[str, Any]],
) -> None:
    values = list(mapping_func().values())
    assert len(values) == len(set(values))
