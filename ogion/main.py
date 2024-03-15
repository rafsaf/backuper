# Copyright: (c) 2024, Rafał Safin <rafal.safin@rafsaf.pl>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import argparse
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass
from threading import Thread
from types import FrameType
from typing import NoReturn

from ogion import config, core
from ogion.backup_targets import (
    base_target,
    targets_mapping,
)
from ogion.notifications.notifications_context import (
    PROGRAM_STEP,
    NotificationsContext,
)
from ogion.upload_providers import (
    base_provider,
    providers_mapping,
)

exit_event = threading.Event()
log = logging.getLogger(__name__)


def quit(sig: int, frame: FrameType | None) -> None:
    log.info("interrupted by %s, shutting down", sig)
    exit_event.set()


@NotificationsContext(step_name=PROGRAM_STEP.SETUP_PROVIDER)
def backup_provider() -> base_provider.BaseUploadProvider:
    provider_cls_map = providers_mapping.get_provider_cls_map()

    provider_model = core.create_provider_model()
    log.info(
        "initializing provider: `%s`",
        provider_model.name,
    )

    provider_target_cls = provider_cls_map[provider_model.name]
    log.debug("initializing %s with %s", provider_target_cls, provider_model)
    res_backup_provider = provider_target_cls(target_provider=provider_model)
    log.info(
        "success initializing provider: `%s`",
        provider_model.name,
    )
    return res_backup_provider


@NotificationsContext(step_name=PROGRAM_STEP.SETUP_TARGETS)
def backup_targets() -> list[base_target.BaseBackupTarget]:
    backup_target_cls_map = targets_mapping.get_target_cls_map()

    backup_targets: list[base_target.BaseBackupTarget] = []
    target_models = core.create_target_models()
    if not target_models:
        raise RuntimeError("Found 0 backup targets, at least 1 is required.")

    log.info("initializating %s backup targets", len(target_models))

    for target_model in target_models:
        log.info(
            "initializing target: `%s`",
            target_model.env_name,
        )
        backup_target_cls = backup_target_cls_map[target_model.name]
        log.debug("initializing %s with %s", backup_target_cls, target_model)
        backup_targets.append(backup_target_cls(target_model=target_model))
        log.info(
            "success initializing target: `%s`",
            target_model.env_name,
        )

    return backup_targets


def shutdown() -> NoReturn:  # pragma: no cover
    timeout_secs = config.options.SIGTERM_TIMEOUT_SECS
    start = time.time()
    deadline = start + timeout_secs
    log.info(
        "start ogion shutdown, force exit after SIGTERM_TIMEOUT_SECS=%ss, "
        "use this environment to control it, see https://ogion.rafsaf.pl/latest/configuration/.",
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
        log.info("gracefully exiting ogion")
        sys.exit(0)
    else:
        log.warning(
            "noooo, exiting! i am now killing myself with %d daemon threads "
            "force killed. you can extend this time using environment "
            "SIGTERM_TIMEOUT_SECS.",
            threading.active_count() - 1,
        )
        sys.exit(1)


def run_backup(
    target: base_target.BaseBackupTarget, provider: base_provider.BaseUploadProvider
) -> None:
    log.info("start making backup of target: `%s`", target.env_name)
    with NotificationsContext(
        step_name=PROGRAM_STEP.BACKUP_CREATE, env_name=target.env_name
    ):
        backup_file = target.make_backup()
    log.info(
        "backup file created: %s, starting post save upload to provider %s",
        backup_file,
        provider.__class__.__name__,
    )
    with NotificationsContext(
        step_name=PROGRAM_STEP.UPLOAD,
        env_name=target.env_name,
    ):
        provider.post_save(backup_file=backup_file)

    with NotificationsContext(
        step_name=PROGRAM_STEP.CLEANUP,
        env_name=target.env_name,
    ):
        provider.clean(
            backup_file=backup_file,
            max_backups=target.max_backups,
            min_retention_days=target.min_retention_days,
        )

    log.info(
        "backup and upload finished, next backup of target `%s` is: %s",
        target.env_name,
        target.next_backup_time,
    )


@dataclass
class RuntimeArgs:
    single: bool
    debug_notifications: bool


def setup_runtime_arguments() -> RuntimeArgs:
    parser = argparse.ArgumentParser(description="Ogion program")
    parser.add_argument(
        "-s", "--single", action="store_true", help="Only single backup then exit"
    )
    parser.add_argument(
        "-n",
        "--debug-notifications",
        action="store_true",
        help="Check if notifications setup is working",
    )
    return RuntimeArgs(**vars(parser.parse_args()))


def main() -> NoReturn:
    log.info("start ogion configuration...")

    runtime_args = setup_runtime_arguments()

    if runtime_args.debug_notifications:
        try:
            with NotificationsContext(step_name=PROGRAM_STEP.DEBUG_NOTIFICATIONS):
                raise ValueError("hi! this is notifications debug exception")
        except Exception:
            sys.exit(0)

    provider = backup_provider()
    targets = backup_targets()

    log.info("ogion configuration finished")

    while not exit_event.is_set():
        for target in targets:
            if target.next_backup() or runtime_args.single:
                pretty_env_name = target.env_name.replace("_", "-")
                backup_thread = Thread(
                    target=run_backup,
                    args=(target, provider),
                    daemon=True,
                    name=f"Thread-{pretty_env_name}",
                )
                backup_thread.start()
                exit_event.wait(0.5)
        if runtime_args.single:
            exit_event.set()
        exit_event.wait(5)

    shutdown()


if __name__ == "__main__":  # pragma: no cover
    signal.signal(signalnum=signal.SIGINT, handler=quit)
    signal.signal(signalnum=signal.SIGTERM, handler=quit)

    main()
