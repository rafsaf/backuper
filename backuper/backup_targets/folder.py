import logging
from pathlib import Path

from backuper import config, core
from backuper.backup_targets.base_target import BaseBackupTarget

log = logging.getLogger(__name__)


class Folder(BaseBackupTarget, target_model_name=config.BackupTargetEnum.FOLDER):
    def __init__(
        self,
        abs_path: Path,
        cron_rule: str,
        env_name: str,
        max_backups: int,
        **kwargs: str | int,
    ) -> None:
        self.cron_rule: str = cron_rule
        self.folder: Path = abs_path
        super().__init__(
            cron_rule=cron_rule, env_name=env_name, max_backups=max_backups
        )

    def _backup(self) -> Path:
        out_file = core.get_new_backup_path(self.env_name, self.folder.name)

        shell_create_dir_symlink = f"ln -s {self.folder} {out_file}"
        log.debug("start ln in subprocess: %s", shell_create_dir_symlink)
        core.run_subprocess(shell_create_dir_symlink)
        log.debug("finished ln, output: %s", out_file)
        return out_file