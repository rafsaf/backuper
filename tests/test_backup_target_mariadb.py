import pytest
from freezegun import freeze_time
from pytest import LogCaptureFixture, MonkeyPatch

from backuper import config
from backuper.backup_targets import MariaDB

from .conftest import (
    ALL_MARIADB_DBS_TARGETS,
    CONST_TOKEN_URLSAFE,
    DB_VERSION_BY_ENV_VAR,
)


@pytest.mark.parametrize("mariadb_target", ALL_MARIADB_DBS_TARGETS)
def test_mariadb_connection_success(
    caplog: LogCaptureFixture, mariadb_target: config.MariaDBBackupTarget
):
    db = MariaDB(**mariadb_target.dict())
    assert db.db_version == DB_VERSION_BY_ENV_VAR[mariadb_target.env_name]


@pytest.mark.parametrize("mariadb_target", ALL_MARIADB_DBS_TARGETS)
def test_mariadb_connection_fail(
    caplog: LogCaptureFixture,
    mariadb_target: config.MariaDBBackupTarget,
    monkeypatch: MonkeyPatch,
):
    with pytest.raises(SystemExit) as system_exit:
        # simulate not existing db port 9999 and connection err
        monkeypatch.setattr(mariadb_target, "port", 9999)
        MariaDB(**mariadb_target.dict())
    assert system_exit.type == SystemExit
    assert system_exit.value.code == 1


@freeze_time("2022-12-11")
@pytest.mark.parametrize("mariadb_target", ALL_MARIADB_DBS_TARGETS)
def test_run_mariadb_dump(
    caplog: LogCaptureFixture, mariadb_target: config.MariaDBBackupTarget
):
    db = MariaDB(**mariadb_target.dict())
    out_backup = db._backup()
    out_file = (
        f"{db.env_name}/20221211_0000_maria_{db.db_version}_{CONST_TOKEN_URLSAFE}"
    )
    out_path = config.CONST_BACKUP_FOLDER_PATH / out_file
    assert out_backup == out_path