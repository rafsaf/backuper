from backuper.config import BackupTargetEnum, UploadProviderEnum
from backuper.models import backup_target_models, upload_provider_models


def get_target_map() -> dict[str, type[backup_target_models.TargetModel]]:
    return {
        BackupTargetEnum.FILE: backup_target_models.SingleFileTargetModel,
        BackupTargetEnum.FOLDER: backup_target_models.DirectoryTargetModel,
        BackupTargetEnum.MARIADB: backup_target_models.MariaDBTargetModel,
        BackupTargetEnum.MYSQL: backup_target_models.MySQLTargetModel,
        BackupTargetEnum.POSTGRESQL: backup_target_models.PostgreSQLTargetModel,
    }


def get_provider_map() -> dict[str, type[upload_provider_models.ProviderModel]]:
    return {
        UploadProviderEnum.AZURE: upload_provider_models.AzureProviderModel,
        UploadProviderEnum.LOCAL_FILES_DEBUG: upload_provider_models.DebugProviderModel,
        UploadProviderEnum.GCS: upload_provider_models.GCSProviderModel,
        UploadProviderEnum.AWS_S3: upload_provider_models.AWSProviderModel,
    }
