# Copyright: (c) 2024, Rafał Safin <rafal.safin@rafsaf.pl>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import logging
from pathlib import Path

from azure.storage.blob import BlobServiceClient

from ogion import core
from ogion.models.upload_provider_models import AzureProviderModel
from ogion.upload_providers.base_provider import BaseUploadProvider

log = logging.getLogger(__name__)


class UploadProviderAzure(BaseUploadProvider):
    """Azure blob storage for storing backups"""

    def __init__(self, target_provider: AzureProviderModel) -> None:
        self.container_name = target_provider.container_name

        blob_service_client = BlobServiceClient.from_connection_string(
            target_provider.connect_string.get_secret_value()
        )
        self.container_client = blob_service_client.get_container_client(
            container=self.container_name
        )

    def _post_save(self, backup_file: Path) -> str:
        zip_backup_file = core.run_create_zip_archive(backup_file=backup_file)

        backup_dest_in_azure_container = (
            f"{zip_backup_file.parent.name}/{zip_backup_file.name}"
        )
        blob_client = self.container_client.get_blob_client(
            blob=backup_dest_in_azure_container
        )

        log.info(
            "start uploading %s to %s", zip_backup_file, backup_dest_in_azure_container
        )

        with open(file=zip_backup_file, mode="rb") as data:
            blob_client.upload_blob(data=data)

        log.info(
            "uploaded %s to %s in %s",
            zip_backup_file,
            backup_dest_in_azure_container,
            self.container_name,
        )
        return backup_dest_in_azure_container

    def _clean(
        self, backup_file: Path, max_backups: int, min_retention_days: int
    ) -> None:
        for backup_path in backup_file.parent.iterdir():
            core.remove_path(backup_path)
            log.info("removed %s from local disk", backup_path)

        backup_list_cloud: list[str] = []
        for blob in self.container_client.list_blobs(
            name_starts_with=backup_file.parent.name
        ):
            backup_list_cloud.append(blob.name)

        # remove oldest
        backup_list_cloud.sort(reverse=True)

        while len(backup_list_cloud) > max_backups:
            backup_to_remove = backup_list_cloud.pop()
            file_name = backup_to_remove.split("/")[-1]
            if core.file_before_retention_period_ends(
                backup_name=file_name, min_retention_days=min_retention_days
            ):
                log.info(
                    "there are more backups than max_backups (%s/%s), "
                    "but oldest cannot be removed due to min retention days",
                    len(backup_list_cloud),
                    max_backups,
                )
                break

            self.container_client.delete_blob(blob=backup_to_remove)
            log.info("deleted backup %s from azure blob storage", backup_to_remove)
