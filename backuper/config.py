import json
import logging
import logging.config
import os
import re
from enum import StrEnum
from pathlib import Path

from croniter import croniter
from pydantic import BaseModel, SecretStr, validator

BASE_DIR = Path(__file__).resolve().parent.parent.absolute()

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass

CONST_ENV_NAME_REGEX = re.compile(r"^[A-Za-z_0-9]{1,}$")
CONST_ZIP_PASSWORD_REGEX = re.compile(r"^[a-zA-Z0-9]{4,1024}$")
CONST_ZIP_BIN_7ZZ_PATH: Path = BASE_DIR / "bin/7zz"
CONST_BACKUP_FOLDER_PATH: Path = BASE_DIR / "data"
CONST_PGPASS_FILE_PATH: Path = BASE_DIR / ".pgpass"
CONST_GOOGLE_SERVICE_ACCOUNT_PATH: Path = BASE_DIR / "google_auth.json"
os.environ["PGPASSFILE"] = str(CONST_PGPASS_FILE_PATH)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(CONST_GOOGLE_SERVICE_ACCOUNT_PATH)
CONST_GOOGLE_SERVICE_ACCOUNT_PATH.touch(mode=0o700, exist_ok=True)
CONST_PGPASS_FILE_PATH.unlink(missing_ok=True)
CONST_PGPASS_FILE_PATH.touch(mode=0o700)
CONST_BACKUP_FOLDER_PATH.mkdir(mode=0o700, parents=True, exist_ok=True)
CONST_ALLOWED_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
assert (
    LOG_LEVEL in CONST_ALLOWED_LOG_LEVELS
), f"invalid log level: {LOG_LEVEL}, must be one of {CONST_ALLOWED_LOG_LEVELS}"


def logging_config(log_level: str):
    conf = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{asctime} [{levelname}] {name}: {message}",
                "style": "{",
            },
        },
        "handlers": {
            "stream": {
                "class": "logging.StreamHandler",
                "formatter": "verbose",
                "level": "DEBUG",
            },
        },
        "loggers": {
            "": {
                "level": log_level,
                "handlers": ["stream"],
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(conf)


logging_config(LOG_LEVEL)

log = logging.getLogger(__name__)


class BackupProviderEnum(StrEnum):
    LOCAL_FILES = "local"
    GOOGLE_CLOUD_STORAGE = "gcs"


class BackupTargetEnum(StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    FILE = "singlefile"
    FOLDER = "directory"


BACKUP_PROVIDER = os.environ.get("BACKUP_PROVIDER", BackupProviderEnum.LOCAL_FILES)

ZIP_ARCHIVE_PASSWORD = os.environ.get("ZIP_ARCHIVE_PASSWORD", "")
if not CONST_ZIP_PASSWORD_REGEX.match(ZIP_ARCHIVE_PASSWORD):
    raise RuntimeError(
        f"`ZIP_ARCHIVE_PASSWORD` does not match regex {CONST_ZIP_PASSWORD_REGEX}: `{ZIP_ARCHIVE_PASSWORD}`"
    )
SUBPROCESS_TIMEOUT_SECS: int = int(os.environ.get("SUBPROCESS_TIMEOUT_SECS", 60 * 60))
BACKUP_COOLING_SECS: int = int(os.environ.get("BACKUP_COOLING_SECS", 60))
BACKUP_COOLING_RETRIES: int = int(os.environ.get("BACKUP_COOLING_RETRIES", 1))
BACKUP_MAX_NUMBER: int = int(os.environ.get("BACKUP_MAX_NUMBER", 7))
GOOGLE_BUCKET_NAME: str = os.environ.get("GOOGLE_BUCKET_NAME", "")
GOOGLE_BUCKET_UPLOAD_PATH: str | None = os.environ.get(
    "GOOGLE_BUCKET_UPLOAD_PATH", None
)
GOOGLE_SERVICE_ACCOUNT_BASE64: str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_BASE64", "")


class BackupTarget(BaseModel):
    env_name: str
    type: BackupTargetEnum
    cron_rule: str

    @validator("cron_rule")
    def cron_rule_is_valid(cls, cron_rule: str):
        if not croniter.is_valid(cron_rule):
            raise ValueError(
                f"Error in cron_rule expression: `{cron_rule}` is not valid"
            )
        return cron_rule

    @validator("env_name")
    def env_name_is_valid(cls, env_name: str):
        if not CONST_ENV_NAME_REGEX.match(env_name):
            raise ValueError(
                f"Env variable does not match regex {CONST_ENV_NAME_REGEX}: `{env_name}`"
            )
        return env_name


class PostgreSQLBackupTarget(BackupTarget):
    user: str = "postgres"
    host: str = "localhost"
    port: int = 5432
    db: str = "postgres"
    password: SecretStr
    type = BackupTargetEnum.POSTGRESQL


class MySQLBackupTarget(BackupTarget):
    user: str = "root"
    host: str = "localhost"
    port: int = 3306
    db: str
    password: SecretStr
    type = BackupTargetEnum.MYSQL


class FileBackupTarget(BackupTarget):
    abs_path: str
    type = BackupTargetEnum.FILE


class FolderBackupTarget(BackupTarget):
    abs_path: str
    type = BackupTargetEnum.FOLDER


def _validate_backup_target(env_name: str, val: str, target: type[BackupTarget]):
    target_type = target.__name__.lower()
    log.info("validating %s variable: `%s`", target_type, env_name)
    try:
        db_data_from_env = json.loads(val)
        res = target(env_name=env_name, **db_data_from_env)
    except Exception as err:
        log.error(err)
        raise RuntimeError(f"Error validating environment variable: `{env_name}`")
    log.info("%s variable ok: `%s`", target_type, env_name)
    return res


BACKUP_TARGETS: list[BackupTarget] = []
for env_name, val in os.environ.items():
    env_name = env_name.lower()
    if env_name.startswith(BackupTargetEnum.POSTGRESQL):
        BACKUP_TARGETS.append(
            _validate_backup_target(env_name, val, PostgreSQLBackupTarget)
        )
    elif env_name.startswith(BackupTargetEnum.MYSQL):
        BACKUP_TARGETS.append(_validate_backup_target(env_name, val, MySQLBackupTarget))
    elif env_name.startswith(BackupTargetEnum.FILE):
        BACKUP_TARGETS.append(_validate_backup_target(env_name, val, FileBackupTarget))
    elif env_name.startswith(BackupTargetEnum.FOLDER):
        BACKUP_TARGETS.append(
            _validate_backup_target(env_name, val, FolderBackupTarget)
        )


def runtime_configuration():
    if BACKUP_PROVIDER == BackupProviderEnum.GOOGLE_CLOUD_STORAGE:
        if not GOOGLE_BUCKET_NAME:
            raise RuntimeError(
                f"For provider: `{BACKUP_PROVIDER}` you must use environment variable `GOOGLE_BUCKET_NAME`"
            )
        elif not GOOGLE_SERVICE_ACCOUNT_BASE64:
            raise RuntimeError(
                f"For provider: `{BACKUP_PROVIDER}` you must use environment variable `GOOGLE_SERVICE_ACCOUNT_BASE64`"
            )
    if ZIP_ARCHIVE_PASSWORD and not CONST_ZIP_BIN_7ZZ_PATH.exists():
        raise RuntimeError(
            f"`{ZIP_ARCHIVE_PASSWORD}` is set but `{CONST_ZIP_BIN_7ZZ_PATH}` binary does not exists, did you forget to create it?"
        )


runtime_configuration()
