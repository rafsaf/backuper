#!/bin/bash

chown -R ${PG_DUMP_SERVICE_NAME}:${PG_DUMP_SERVICE_NAME} ${PG_DUMP_FOLDER_PATH} ${PG_DUMP_LOG_FOLDER_PATH}
exec runuser -u ${PG_DUMP_SERVICE_NAME} "$@"