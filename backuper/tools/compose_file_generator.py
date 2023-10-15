import json
from pathlib import Path
from typing import Callable

import yaml
from compose_db_models import ComposeDatabase
from endoflife_api import (
    EOL_DATA_DIR,
    EOLApiProduct,
    EOLApiProductCycle,
    update_eol_files,
)

DB_PWD = "password-_-12!@#%^&*()/;><.,]}{["
DB_NAME = "database-_-12!@#%^&*()/;><.,]}{["
DB_USERNAME = "user-_-12!@#%^&*()/;><.,]}{["
DEFAULT_NETWORK = "backuper"


def mariadb_db_generator(cycle: EOLApiProductCycle) -> ComposeDatabase:
    host_port = 11000 + int(cycle.cycle.replace(".", ""))
    name = f"backuper_mariadb_{cycle.cycle.replace('.','_')}"
    compose_db = ComposeDatabase(
        name=name,
        restart="no",
        networks=[DEFAULT_NETWORK],
        image=f"mariadb:{cycle.latest}",
        ports=[f"{host_port}:3306"],
        environment=[
            f"MARIADB_ROOT_PASSWORD=root-{DB_PWD}",
            f"MARIADB_DATABASE={DB_NAME}",
            f"MARIADB_USER={DB_USERNAME}",
            f"MARIADB_PASSWORD={DB_PWD}",
        ],
    )

    return compose_db


def mysql_db_generator(cycle: EOLApiProductCycle) -> ComposeDatabase:
    host_port = 9000 + int(cycle.cycle.replace(".", ""))
    name = f"backuper_mysql_{cycle.cycle.replace('.','_')}"
    compose_db = ComposeDatabase(
        name=name,
        restart="no",
        networks=[DEFAULT_NETWORK],
        image=f"mysql:{cycle.latest}",
        ports=[f"{host_port}:3306"],
        environment=[
            f"MYSQL_ROOT_PASSWORD=root-{DB_PWD}",
            f"MYSQL_DATABASE={DB_NAME}",
            f"MYSQL_USER={DB_USERNAME}",
            f"MYSQL_PASSWORD={DB_PWD}",
        ],
    )

    return compose_db


def postgres_db_generator(cycle: EOLApiProductCycle) -> ComposeDatabase:
    host_port = 10000 + int(cycle.cycle.replace(".", ""))
    name = f"backuper_postgres_{cycle.cycle.replace('.','_')}"
    compose_db = ComposeDatabase(
        name=name,
        restart="no",
        networks=[DEFAULT_NETWORK],
        image=f"postgres:{cycle.latest}-bookworm",
        ports=[f"{host_port}:5432"],
        environment=[
            f"POSTGRES_PASSWORD=root-{DB_PWD}",
            f"POSTGRES_DB={DB_NAME}",
            f"POSTGRES_USER={DB_USERNAME}",
        ],
    )

    return compose_db


def handle_file(
    filename: Path,
    cycle_func: Callable[[EOLApiProductCycle], ComposeDatabase],
) -> list[ComposeDatabase]:
    with open(filename) as f:
        product = EOLApiProduct(cycles=json.load(f))

    before_eol_cycles = [cycle for cycle in product.cycles if cycle.before_eol]

    return [cycle_func(cycle) for cycle in before_eol_cycles]


def db_compose_data() -> list[ComposeDatabase]:
    res: list[ComposeDatabase] = []
    res += handle_file(EOL_DATA_DIR / "mariadb.json", mariadb_db_generator)
    res += handle_file(EOL_DATA_DIR / "postgresql.json", postgres_db_generator)
    res += handle_file(EOL_DATA_DIR / "mysql.json", mysql_db_generator)
    return res


if __name__ == "__main__":
    update_eol_files()
    data = {"services": {}, "networks": {"backuper": {}}}
    compose_data = db_compose_data()
    for compose_db_data in compose_data:
        data["services"][compose_db_data.name] = compose_db_data.model_dump(
            exclude={"name"}
        )
    yml_data = yaml.safe_dump(data, indent=2)
    print(yml_data)
