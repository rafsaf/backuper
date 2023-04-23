import logging
from pathlib import Path

from backuper import core
from backuper.backup_targets.base_target import BaseBackupTarget

log = logging.getLogger(__name__)


class Folder(BaseBackupTarget):
    def __init__(
        self,
        abs_path: str,
        cron_rule: str,
        env_name: str,
        **kwargs,
    ) -> None:
        self.cron_rule = cron_rule
        self.folder_abs_path = abs_path
        self.folder = Path(abs_path)
        super().__init__(cron_rule=cron_rule, env_name=env_name)

    def _backup(self):
        out_file = core.get_new_backup_path(self.env_name, self.folder.name)

        shell_args = f"cp -r {self.folder_abs_path} {out_file}"
        log.debug("start cp -r in subprocess: %s", shell_args)
        core.run_subprocess(shell_args)
        log.debug("finished cp -r, output: %s", out_file)
        return out_file