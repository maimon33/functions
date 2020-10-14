# k8s scripts and functions

## ssh-nodes

Access k8s nodes via kubectl resources

**Usage**
`./ssh-nodes.sh node_name`

## scaler

Easy script to scale replicas on your cluster

**Usage**
* To go through every deployment leave out deployment name<br>
`./scaler.sh -n elk`

* Or specify which deployment to scale<br>
`./scaler.sh -n elk -d logstash`
