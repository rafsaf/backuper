---
hide:
  - toc
---

# Single file

## Environment variable

```bash
SINGLEFILE_SOME_STRING="abs_path=... cron_rule=..."
```

!!! note
    _Any environment variable that starts with "**SINGLEFILE_**" will be handled as Single File._ There can be multiple files paths definition for one backuper instance, for example `SINGLEFILE_FOO` and `SINGLEFILE_BAR`. Params must be included in value, splited by single space for example `"value1=1 value2=foo"`.

## Params

| Name        | Type                 | Description                                                                                                                                                                                 | Default           |
| :---------- | :------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------- |
| abs_path    | string[**requried**] | Absolute path to file for backup.                                                                                                                                                           | -                 |
| cron_rule   | string[**requried**] | Cron expression for backups, see [https://crontab.guru/](https://crontab.guru/) for help.                                                                                                   | -                 |
| max_backups | int                  | Max number of backups stored in upload provider, if this number is exceeded, oldest one is removed, by default enviornment variable BACKUP_MAX_NUMBER, see [Configuration](./../configuration.md). | BACKUP_MAX_NUMBER |


## Examples

```bash
# File /home/user/file.txt with backup every single minute
SINGLEFILE_FIRST='abs_path=/home/user/file.txt cron_rule=* * * * *'

# File /etc/hosts with backup on every night (UTC) at 05:00
SINGLEFILE_SECOND='abs_path=/etc/hosts cron_rule=0 5 * * *'

# File config.json in mounted dir /mnt/appname with backup on every 6 hours at '15 with max number of backups of 20
SINGLEFILE_THIRD='abs_path=/mnt/appname/config.json cron_rule=15 */3 * * * max_backups=20'
```

<br>
<br>