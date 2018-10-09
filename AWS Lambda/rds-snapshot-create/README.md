## RDS snapshot create

The following Lambda function will create RDS snapshots.

Variables for this function:

* **INTERVAL** Hours between snapshots
* **DESTINATION_ACCOUNTS** Destination AWS accounts IDs, separated by commas
* **DESTINATION_KMS_ID** KMS key to be used for new copy in destination region
* **DESTINATION_REGION** Destination of RDS snapshots
* **SNAPSHOTS_TO_KEEP** Number of snapshots to keep
* **PATTERN** prefix of RDS instance
* **SNS_TOPIC** SNS channel to update
* **USE_SNAPSHOT_ID** use snapshot ID instead of creation date
* **LOG_LEVEL** Logger level for the function
