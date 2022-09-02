import logging
import pathlib
import pickle
import signal
import sys

try:
    from pg_dump import core
except ImportError:
    BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.absolute()
    sys.path.insert(0, str(BASE_DIR))

    from pg_dump import core

from pg_dump.config import BASE_DIR, settings
from pg_dump.jobs import PgDumpJob
from pg_dump.pgdump_thread import PgDumpThread
from pg_dump.scheduler_thread import SchedulerThread

log = logging.getLogger(__name__)


class PgDumpDaemon:
    """pg_dump service"""

    def __init__(self, exit_on_fail: bool = False) -> None:
        self.db_version: str = ""
        self.exit_on_fail = exit_on_fail
        log.info("Initialize pg_dump...")
        core.recreate_pgpass_file()
        log.info("Recreated pgpass file")
        self.check_postgres_connection()
        log.info("Recreating last saved queue")
        self.initialize_pgdump_queue_from_picle()
        log.info("Recreating GPG public key")
        core.recreate_gpg_public_key()
        log.info("Initialization finished.")

        self.scheduler_thread = SchedulerThread(db_version=self.db_version)
        self.pgdump_threads: list[PgDumpThread] = []
        for i in range(settings.PGDUMP_NUMBER_PGDUMP_THREADS):
            self.pgdump_threads.append(PgDumpThread(number=i))

        signal.signal(signalnum=signal.SIGINT, handler=self.exit)
        signal.signal(signalnum=signal.SIGTERM, handler=self.exit)

    def run(self):
        self.scheduler_thread.start()
        for thread in self.pgdump_threads:
            thread.start()

    def initialize_pgdump_queue_from_picle(self):
        if settings.PGDUMP_PICKLE_PGDUMP_QUEUE_NAME.is_file():
            with open(settings.PGDUMP_PICKLE_PGDUMP_QUEUE_NAME, "rb") as file:
                queue_elements: list[PgDumpJob] = pickle.loads(file.read())
                for item in queue_elements:
                    core.PGDUMP_QUEUE.put(item, block=False)
                log.info(
                    "initialize_pgdump_queue_from_picle, found %s elements in queue",
                    len(queue_elements),
                )
        else:
            log.info("initialize_pgdump_queue_from_picle no picke queue file, skipping")

    def check_postgres_connection(self):
        while not self.db_version:
            try:
                db_version = core.get_postgres_version()
            except core.CoreSubprocessError as err:
                log.error(err, exc_info=True)
                log.error("Unable to connect to database, exiting")
                exit(1)
            else:
                self.db_version = db_version
                return

    def healthcheck(self):
        healthy = True
        if not self.scheduler_thread.is_alive():
            log.critical("Scheduler thread is not alive")
            healthy = False
        for thread in self.pgdump_threads:
            if not thread.is_alive():
                log.critical("Pgdump thread %s is not alive", thread.number)
                healthy = False
        return healthy

    def exit(self, sig, frame):
        self.scheduler_thread.stop()
        self.scheduler_thread.join()
        for thread in self.pgdump_threads:
            thread.stop()
        for thread in self.pgdump_threads:
            thread.join()
        with open(settings.PGDUMP_PICKLE_PGDUMP_QUEUE_NAME, "wb") as file:
            pickle.dump(list(core.PGDUMP_QUEUE.queue), file)
        log.info("Saved pickled pgdump_queue to file")
        log.info("PgDumpDaemon exits gracefully")


if __name__ == "__main__":
    pg_dump_daemon = PgDumpDaemon()
    pg_dump_daemon.run()
    pg_dump_daemon.scheduler_thread.join()
    for thread in pg_dump_daemon.pgdump_threads:
        thread.join()
