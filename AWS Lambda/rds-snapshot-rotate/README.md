## RDS snapshot rotator

The following Lambda function will rotate RDS snapshot based on policy.
It will be split into 2 groups. and passed as variables:

* **FULL_BACKUPS_DAYS** - Days in which to keep all snapshots
* **DAILY_BACKUPS_DAYS** - Days in which to keep just one
_Everything past these two will be deleted_

Other Variables for this function:

* **PATTERN** Snapshot ID prefix
* **USE_SNAPSHOT_ID** use snapshot ID instead of creation date
* **LOG_LEVEL Logger** level for the function
