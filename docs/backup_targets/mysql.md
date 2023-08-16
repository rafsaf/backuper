---
hide:
  - toc
---

# MySQL

## Environment variable

```bash
MYSQL_SOME_STRING="host=... password=... cron_rule=..."
```

!!! note
    _Any environment variable that starts with "**MYSQL_**" will be handled as MySQL._ There can be multiple files paths definition for one backuper instance, for example `MYSQL_FOO_MY_DB1` and `MYSQL_BAR_MY_DB2`. Supported versions are: 8.0, 5.7. Params must be included in value, splited by single space for example `"value1=1 value2=foo"`.

## Params

| Name        | Type                 | Description                                                                                                                                                                                 | Default           |
| :---------- | :------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------- |
| password    | string[**requried**] | MySQL database password.                                                                                                                                                                    | -                 |
| cron_rule   | string[**requried**] | Cron expression for backups, see [https://crontab.guru/](https://crontab.guru/) for help.                                                                                                   | -                 |
| user        | string               | MySQL database username.                                                                                                                                                                    | root              |
| host        | string               | MySQL database hostname.                                                                                                                                                                    | localhost         |
| port        | int                  | MySQL database port.                                                                                                                                                                        | 3306              |
| db          | string               | MySQL database name.                                                                                                                                                                        | mysql             |
| max_backups | int                  | Max number of backups stored in upload provider, if this number is exceeded, oldest one is removed, by default enviornment variable BACKUP_MAX_NUMBER, see [Configuration](./../configuration.md). | BACKUP_MAX_NUMBER |


## Examples

```bash
# 1. Local MySQL with backup every single minute
MYSQL_FIRST_DB='host=localhost port=3306 password=secret cron_rule=* * * * *'

# 2. MySQL in local network with backup on every night (UTC) at 05:00
MYSQL_SECOND_DB='host=10.0.0.1 port=3306 user=foo password=change_me! db=bar cron_rule=0 5 * * *'

# 3. MySQL in local network with backup on every 6 hours at '15 with max number of backups of 20
MYSQL_THIRD_DB='host=192.168.1.5 port=3306 user=root password=change_me_please! db=project cron_rule=15 */3 * * * max_backups=20'
```

<br>
<br>