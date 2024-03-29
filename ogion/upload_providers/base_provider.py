# Copyright: (c) 2024, Rafał Safin <rafal.safin@rafsaf.pl>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import final

from ogion.models.upload_provider_models import ProviderModel

log = logging.getLogger(__name__)


class BaseUploadProvider(ABC):
    def __init__(self, target_provider: ProviderModel) -> None:  # pragma: no cover
        pass

    @final
    def post_save(self, backup_file: Path) -> str:
        try:
            return self._post_save(backup_file=backup_file)
        except Exception as err:
            log.error(err, exc_info=True)
            raise

    @final
    def clean(
        self, backup_file: Path, max_backups: int, min_retention_days: int
    ) -> None:
        try:
            return self._clean(
                backup_file=backup_file,
                max_backups=max_backups,
                min_retention_days=min_retention_days,
            )
        except Exception as err:
            log.error(err, exc_info=True)
            raise

    @abstractmethod
    def _post_save(self, backup_file: Path) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def _clean(
        self, backup_file: Path, max_backups: int, min_retention_days: int
    ) -> None:  # pragma: no cover
        pass
