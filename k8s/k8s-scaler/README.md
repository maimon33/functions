# k8s Scaler script
Simple script that iterates through cluster deployment matching a regex search and prompts current status and scales by request

### Options
* **-n|--namespace** - Namespace. leave blank for default
* **-d|--deployments** - Regex search for deployment name

### Usage
```
root@ip-172-31-191-12:~# ./scaler.sh -n f2g -d algo
Found
Current replica for algo-attr is: 2
Desired replicas? 2
No Change
```
