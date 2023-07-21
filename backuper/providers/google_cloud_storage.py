import base64
import logging
import os
import shutil
import time
from pathlib import Path

import google.cloud.storage as storage

from backuper import config, core
from backuper.providers.base_provider import BaseBackupProvider

log = logging.getLogger(__name__)


class GoogleCloudStorage(
    BaseBackupProvider,
    name=config.BackupProviderEnum.GOOGLE_CLOUD_STORAGE,
):
    """Represent GCS bucket for storing backups."""

    MAX_UPLOAD_RETRY = 5
    CHUNK_SIZE = 25 * 1024 * 1024  # 25MB

    def __init__(
        self,
        bucket_name: str,
        bucket_upload_path: str,
        service_account_base64: str,
        **kwargs: str,
    ) -> None:
        service_account_bytes = base64.b64decode(service_account_base64)
        with open(config.CONST_GOOGLE_SERVICE_ACCOUNT_PATH, "wb") as f:
            f.write(service_account_bytes)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
            config.CONST_GOOGLE_SERVICE_ACCOUNT_PATH
        )
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(bucket_name)
        self.bucket_upload_path = bucket_upload_path

    def _post_save(self, backup_file: Path) -> str:
        zip_backup_file = core.run_create_zip_archive(backup_file=backup_file)

        backup_dest_in_bucket = "{}/{}/{}".format(
            self.bucket_upload_path,
            zip_backup_file.parent.name,
            zip_backup_file.name,
        )

        log.info("start uploading %s to %s", zip_backup_file, backup_dest_in_bucket)

        blob = self.bucket.blob(
            backup_dest_in_bucket, chunk_size=GoogleCloudStorage.CHUNK_SIZE
        )
        retry = 0
        while retry < self.MAX_UPLOAD_RETRY:
            try:
                blob.upload_from_filename(zip_backup_file, timeout=120)
                break
            except Exception as err:
                log.error(
                    "error (try %s of %s) when uploading %s to gcs: %s",
                    retry + 1,
                    self.MAX_UPLOAD_RETRY,
                    zip_backup_file,
                    err,
                    exc_info=True,
                )
                if retry == self.MAX_UPLOAD_RETRY - 1:
                    raise RuntimeError("failed upload %s file to gcs", zip_backup_file)
                else:
                    time.sleep(2**retry)
                    retry += 1

        log.info("uploaded %s to %s", zip_backup_file, backup_dest_in_bucket)
        return backup_dest_in_bucket

    def _clean(self, backup_file: Path) -> None:
        for backup_path in backup_file.parent.iterdir():
            if backup_path.is_dir():
                shutil.rmtree(backup_path)
            else:
                backup_path.unlink()
            log.info("removed %s from local disk", backup_path)

        backup_list_cloud: list[str] = []
        prefix = f"{self.bucket_upload_path}/{backup_file.parent.name}"
        for blob in self.storage_client.list_blobs(self.bucket, prefix=prefix):
            backup_list_cloud.append(blob.name)

        # remove oldest
        backup_list_cloud.sort(reverse=True)
        while len(backup_list_cloud) > config.BACKUP_MAX_NUMBER:
            backup_to_remove = backup_list_cloud.pop()
            blob = self.bucket.blob(backup_to_remove)
            blob.delete()
            log.info("deleted backup %s from google cloud storage", backup_to_remove)
