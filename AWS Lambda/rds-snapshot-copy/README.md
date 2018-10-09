## RDS Copy Shared Snapshots

The following Lambda function will copy shared snapshots.

Variables for this function:

* **PATTERN** RDS snapshot prefix to match
* **SNS_TOPIC** SNS channel to update
* **DESTINATION_KMS_ID** KMS key to use for new copy encryption
* **LOG_LEVEL** Logger level for the function
