## EC2 Monitor Volumes

The following Lambda function will monitor volume and alerts.

Variables for this function:

* **INSTACE_NAME** Regex of Instance name
* **ALERT_RATE** burst rate alert level
* **LOG_LEVEL** Logger level for the function