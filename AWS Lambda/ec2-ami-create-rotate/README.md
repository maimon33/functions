## EC2 AMI Create

The following Lambda function will create AMI for EC2 instance based on an Hour interval.

Variables for this function:

* **COPIES_TO_KEEP** How many AMI to keep for each instance
* **INSTANCE_ID** Instances IDs, separated by commas
* **INTERVAL** "Daily" or "Weekly" AMI
* **LOG_LEVEL** Logger level for the function