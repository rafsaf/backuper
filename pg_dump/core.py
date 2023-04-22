import logging
import secrets
import subprocess
from datetime import datetime
from pathlib import Path

from pg_dump import config

log = logging.getLogger(__name__)


class CoreSubprocessError(Exception):
    pass


def run_subprocess(shell_args: str) -> str:
    log.debug("run_subprocess running: '%s'", shell_args)
    p = subprocess.run(
        shell_args,
        capture_output=True,
        text=True,
        shell=True,
        timeout=config.SUBPROCESS_TIMEOUT_SECS,
    )
    if p.returncode:
        log.error("run_subprocess failed with status %s", p.returncode)
        log.error("run_subprocess stdout: %s", p.stdout)
        log.error("run_subprocess stderr: %s", p.stderr)
        raise CoreSubprocessError()

    log.debug("run_subprocess finished with status %s", p.returncode)
    log.debug("run_subprocess stdout: %s", p.stdout)
    log.debug("run_subprocess stderr: %s", p.stderr)
    return p.stdout


def get_new_backup_path(env_name: str, name: str) -> Path:
    base_dir_path = config.CONST_BACKUP_FOLDER_PATH / env_name
    base_dir_path.mkdir(mode=0o700, exist_ok=True, parents=True)
    random_string = secrets.token_urlsafe(3)
    new_file = "{}_{}_{}".format(
        datetime.utcnow().strftime("%Y%m%d_%H%M"),
        name,
        random_string,
    )
    return base_dir_path / new_file


def run_create_zip_archive(backup_file: Path) -> Path:
    out_file = Path(f"{backup_file}.zip")
    log.debug("run_create_zip_archive start creating in subprocess: %s", backup_file)
    shell_args_create = (
        f"{config.CONST_ZIP_BIN_7ZZ_PATH} a -p{config.ZIP_ARCHIVE_PASSWORD} -mx=9 "
        f"{out_file} {backup_file}"
    )
    run_subprocess(shell_args_create)
    log.debug("run_create_zip_archive finished, output: %s", out_file)

    log.debug("run_create_zip_archive start integriy test in subprocess: %s", out_file)
    shell_args_integriy = (
        f"{config.CONST_ZIP_BIN_7ZZ_PATH} t "
        f"-p{config.ZIP_ARCHIVE_PASSWORD} {out_file}"
    )
    integrity_check_result = run_subprocess(shell_args_integriy)
    assert "Everything is Ok" in integrity_check_result
    log.debug("run_create_zip_archive finish integriy test in subprocess: %s", out_file)
    return out_file
