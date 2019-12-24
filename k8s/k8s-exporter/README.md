# k8s exporter
Simple script the exports a verity of resources from k8s cluster to directory structure.
The script pulls the namespaces and creates yaml files 

### Options
* **-n|--namespace** - Namespace. leave blank for default

### Usage
```
root@ip-172-31-191-12:~# ./scaler.sh -n f2g -d algo
Found
Current replica for algo-attr is: 2
Desired replicas? 2
No Change
```
