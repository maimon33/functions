## AWS helper scripts
### set_region script
##### Usage
`. set_region.sh`  

### assume-role
Easily assume role to another AWS account. for easy in AWScli and boto3.

##### Pre-configuration
* Create the role in the destination account.<br>
**You'll need the source account ID**
* Attach the policy you'd like to grant
* add permissions to assume role to source user\ role

You can review a full tutorial by AWS [link](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_cross-account-with-roles.html)

##### Usage
`. assume-rule.sh 123456789 test-role`
