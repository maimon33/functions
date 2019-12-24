#!/bin/bash

LOGIN_AWS_URL='https://fdna.okta.com/home/amazon_aws/0oam4pbnoazqusVx7296/272'
BUCKET_URL='https://s3.console.aws.amazon.com/s3/buckets/fdna-production-k8s/cluster-history/'
BUCKET_POSTFIX="/?region=eu-west-1&tab=overview"
DIRECT_LINK='https://s3-eu-west-1.amazonaws.com/fdna-production-k8s/cluster-history'
DATE=`date '+%Y-%m-%d_%H-%M'`
echo $DATE

ssh -t 34.241.210.221 -o StrictHostKeychecking=no << EOF
 sudo su
 mkdir $DATE
 cd $DATE
 
 echo "Report Generated at $DATE" > nodes.txt
 kubectl get nodes > nodes.txt
 kubectl get nodes | grep node | cut -d " " -f 1 | while read -r node ; do
   echo "Processing \$node"
   kubectl describe nodes \$node >> nodes.txt
 done
 
 kubectl get ns |grep -v NAME | cut -d " " -f 1 | while read -r ns ; do
   echo "Processing Namespace: \$ns"
   echo "Report Generated at $DATE" > \$ns.txt
   kubectl -n \$ns get pods -o wide >> \$ns.txt
   echo " " >> \$ns.txt
   kubectl -n \$ns get svc -o wide >> \$ns.txt
   echo " " >> \$ns.txt
   kubectl -n \$ns get pods | grep -v NAME | cut -d " " -f 1 | while read -r pod ; do
     echo "Processing Pod: \$pod"
     echo " " >> \$ns.txt
     echo "Pod: \$pod" >> \$ns.txt
     echo " " >> \$ns.txt
     kubectl -n \$ns describe pods \$pod >> \$ns.txt
   done
   
   kubectl -n \$ns get svc | grep -v NAME | cut -d " " -f 1 | while read -r svc ; do
     echo "Processing Service: \$svc"
     echo " " >> \$ns.txt
     echo "Service: \$svc" >> \$ns.txt
     echo " " >> \$ns.txt
     kubectl -n \$ns describe svc \$svc >> \$ns.txt
   done
 done
 
 cd ..
 aws s3 sync $DATE s3://fdna-production-k8s/cluster-history/$DATE
 rm -r $DATE
EOF

echo " "

echo "To view report, make sure you are logged in to Production AWS Console"
echo "Easy login link: $LOGIN_AWS_URL"

echo " "
echo "Bucket link: $BUCKET_URL$DATE$BUCKET_POSTFIX"