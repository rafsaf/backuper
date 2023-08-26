import argparse
import logging
import signal
import sys
import threading
import time
from threading import Thread
from types import FrameType
from typing import NoReturn

from backuper import config, core
from backuper.backup_targets import BaseBackupTarget
from backuper.notifications import PROGRAM_STEP, NotificationsContext
from backuper.upload_providers import BaseUploadProvider

exit_event = threading.Event()
log = logging.getLogger(__name__)


def quit(sig: int, frame: FrameType | None) -> None:
    log.info("interrupted by %s, shutting down", sig)
    exit_event.set()


def backup_provider(
    backup_provider_env: str, settings: config.Settings
) -> BaseUploadProvider:
    backup_provider_map: dict[config.UploadProviderEnum, type[BaseUploadProvider]] = {}
    for backup_provider in BaseUploadProvider.__subclasses__():
        backup_provider_map[backup_provider.NAME] = backup_provider  # type: ignore

    provider_model = core.create_provider_model(backup_provider_env, settings)
    log.info(
        "initializing provider: `%s`",
        provider_model.name,
    )
    provider_target_cls = backup_provider_map[provider_model.name]
    log.debug("initializing %s with %s", provider_target_cls, provider_model)
    res_backup_provider = provider_target_cls(**provider_model.model_dump())
    log.info(
        "success initializing provider: `%s`",
        provider_model.name,
    )
    return res_backup_provider


def backup_targets(settings: config.Settings) -> list[BaseBackupTarget]:
    backup_targets_map: dict[config.BackupTargetEnum, type[BaseBackupTarget]] = {}
    for backup_target in BaseBackupTarget.__subclasses__():
        backup_targets_map[backup_target.NAME] = backup_target  # type: ignore

    backup_targets: list[BaseBackupTarget] = []
    target_models = core.create_target_models(settings=settings)
    if not target_models:
        raise RuntimeError("Found 0 backup targets, at least 1 is required.")

    log.info("initializating %s backup targets", len(target_models))

    for target_model in target_models:
        log.info(
            "initializing target: `%s`",
            target_model.env_name,
        )
        backup_target_cls = backup_targets_map[target_model.target_type]
        log.debug("initializing %s with %s", backup_target_cls, target_model)
        backup_targets.append(backup_target_cls(**target_model.model_dump()))
        log.info(
            "success initializing target: `%s`",
            target_model.env_name,
        )

    return backup_targets


def shutdown(timeout_secs: int) -> NoReturn:
    start = time.time()
    deadline = start + timeout_secs
    log.info(
        "start backuper shutdown, force exit after SIGTERM_TIMEOUT_SECS=%ss, "
        "use this environment to control it, see https://backuper.rafsaf.pl/latest/configuration/.",
        timeout_secs,
    )
    for thread in threading.enumerate():
        if thread.name == "MainThread":
            continue
        timeout_left = deadline - time.time()
        if timeout_left < 0:
            break
        log.info(
            "there is still backup running, waiting %ss for thread `%s` to join...",
            round(timeout_left, 2),
            thread.name,
        )
        thread.join(timeout=timeout_left)
        if thread.is_alive():
            log.warning(
                "thread `%s` is still alive!",
                thread.name,
            )
        else:
            log.info(
                "thread `%s` exited gracefully",
                thread.name,
            )
    if threading.active_count() == 1:
        log.info("gracefully exiting backuper")
        sys.exit(0)
    else:
        log.warning(
            "noooo, exiting! i am now killing myself with %d daemon threads force killed. "
            "you can extend this time using environment SIGTERM_TIMEOUT_SECS.",
            threading.active_count() - 1,
        )
        sys.exit(1)


def run_backup(
    target: BaseBackupTarget, provider: BaseUploadProvider, settings: config.Settings
) -> None:
    log.info("start making backup of target: `%s`", target.env_name)
    with NotificationsContext(
        step_name=PROGRAM_STEP.BACKUP_CREATE,
        settings=settings,
        env_name=target.env_name,
    ):
        backup_file = target.make_backup()
    log.info(
        "backup file created: %s, starting post save upload to provider %s",
        backup_file,
        provider.NAME,
    )
    with NotificationsContext(
        step_name=PROGRAM_STEP.UPLOAD,
        settings=settings,
        env_name=target.env_name,
    ):
        provider.post_save(backup_file=backup_file)

    with NotificationsContext(
        step_name=PROGRAM_STEP.CLEANUP,
        settings=settings,
        env_name=target.env_name,
        send_on_success=True,
    ):
        provider.clean(backup_file=backup_file, max_backups=target.max_backups)

    log.info(
        "backup and upload finished, next backup of target `%s` is: %s",
        target.env_name,
        target.next_backup_time,
    )


def setup_runtime_arguments() -> bool:
    parser = argparse.ArgumentParser(description="Backuper program")
    parser.add_argument(
        "-s", "--single", action="store_true", help="Only single backup then exit"
    )
    args = parser.parse_args()
    single: bool = args.single
    return single


def main() -> NoReturn:
    log.info("start backuper configuration...")
    signal.signal(signalnum=signal.SIGINT, handler=quit)
    signal.signal(signalnum=signal.SIGTERM, handler=quit)

    settings = config.Settings()  # type: ignore
    config.logging_config(settings.LOG_LEVEL, settings.LOG_FOLDER_PATH)

    single_run = setup_runtime_arguments()

    with NotificationsContext(step_name=PROGRAM_STEP.SETUP_PROVIDER, settings=settings):
        provider = backup_provider(
            backup_provider_env=settings.BACKUP_PROVIDER, settings=settings
        )

    with NotificationsContext(step_name=PROGRAM_STEP.SETUP_TARGETS, settings=settings):
        targets = backup_targets(settings=settings)

    log.info("backuper configuration finished")

    while not exit_event.is_set():
        for target in targets:
            if target.next_backup() or single_run:
                pretty_env_name = target.env_name.replace("_", "-")
                backup_thread = Thread(
                    target=run_backup,
                    args=(target, provider),
                    daemon=True,
                    name=f"Thread-{pretty_env_name}",
                )
                backup_thread.start()
                exit_event.wait(0.5)
        if single_run:
            exit_event.set()
        exit_event.wait(5)

    shutdown(timeout_secs=settings.SIGTERM_TIMEOUT_SECS)


if __name__ == "__main__":  # pragma: no cover
    main()
