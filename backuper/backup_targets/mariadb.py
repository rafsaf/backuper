import logging
import re
from pathlib import Path

from pydantic import SecretStr

from backuper import config, core
from backuper.backup_targets.base_target import BaseBackupTarget

log = logging.getLogger(__name__)

VERSION_REGEX = re.compile(r"\d*\.\d*\.\d*")


class MariaDB(BaseBackupTarget):
    # https://mariadb.com/kb/en/configuring-mariadb-with-option-files/
    # https://mariadb.com/kb/en/mariadb-dumpmariadbdump/
    # https://mariadb.com/kb/en/connecting-to-mariadb/

    def __init__(
        self,
        user: str,
        password: SecretStr,
        port: int,
        host: str,
        db: str,
        cron_rule: str,
        env_name: str,
        **kwargs,
    ) -> None:
        super().__init__(cron_rule=cron_rule, env_name=env_name)
        self.cron_rule = cron_rule
        self.user = user
        self.port = port
        self.db = db
        self.host = host
        self.password = password
        self.option_file = self._init_option_file()
        self.db_version = self._mariadb_connection()

    def _init_option_file(self) -> Path:
        name = f"{self.env_name}.mariadb.cnf"
        path = config.BASE_DIR / name
        path.unlink(missing_ok=True)
        path.touch(0o600)
        with open(path, "w") as file:
            password = self.password.get_secret_value()
            file.write(
                "{}\n{}\n{}\n{}\n{}\n{}".format(
                    "[client]",
                    f"user={self.user}",
                    f"host={self.host}",
                    f"port={self.port}",
                    "protocol=TCP",
                    f"password={password}" if self.password else "",
                )
            )
        return path

    def _mariadb_connection(self):
        log.debug("mariadb_connection start mariadb connection")

        try:
            result = core.run_subprocess(
                f"mariadb --defaults-file={self.option_file} {self.db} "
                "--execute='SELECT version();'",
            )
        except core.CoreSubprocessError as err:
            log.error(err, exc_info=True)
            log.error("mariadb_connection unable to connect to database, exiting")
            exit(1)

        version = None
        matches = VERSION_REGEX.finditer(result)

        for match in matches:
            version = match.group(0)
            break
        if version is None:  # pragma: no cover
            log.error(
                "mariadb_connection error processing sql result, version unknown: %s",
                result,
            )
            exit(1)
        log.debug("mariadb_connection calculated version: %s", version)
        return version

    def _backup(self):
        name = f"{self.db}_{self.db_version}"
        out_file = core.get_new_backup_path(self.env_name, name)

        shell_args = (
            f"mariadb-dump --defaults-file={self.option_file} "
            f"--result-file={out_file} --verbose {self.db}"
        )
        log.debug("start mariadbdump in subprocess: %s", shell_args)
        core.run_subprocess(shell_args)
        log.debug("finished mariadbdump, output: %s", out_file)
        return out_file