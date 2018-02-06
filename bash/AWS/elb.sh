#!/bin/bash

ELB=test1
REMOVE_TIMEOUT=20
INSERT_TIMEOUT=45

LOGFILE=log.log

list_instances_in_elb() {
	aws elb describe-instance-health --load-balancer-name $ELB --output text | cut -f3
}

is_instance_active_in_lb() {
	state=$(aws elb describe-instance-health --load-balancer-name $ELB --instances $1 --output text | cut -f5)
	while [ $state == "InService" ]; do
		return 0
	else
		return 1
	done
}

remove_from_lb_and_wait() {
	aws elb deregister-instances-from-load-balancer --load-balancer-name $ELB --instances $1
	sleep $REMOVE_TIMEOUT
}

insert_into_lb_and_wait() {
	aws elb register-instances-with-load-balancer --load-balancer-name $ELB --instances $1
	sleep $INSERT_TIMEOUT
}


main() {
	instances=$(list_instances_in_elb)
	
	for instance in $instances; do
		while is_instance_active_in_lb $instance; do
			remove_from_lb_and_wait $instance
			insert_into_lb_and_wait $instance
		else
			echo "Instance $1 not Active"
	done	
}

main |& tee -a $LOGFILE
