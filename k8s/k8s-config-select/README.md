### kubectl config select

This script helps you easily switch between kube config files.

It is recommended to create an alias to always run this and keep the exports in your shell

1. copy file to your HOME dir<br> `curl https://raw.githubusercontent.com/maimon33/functions/master/k8s/k8s-config-select/kube.sh -O ~/kube_config.sh`
2. add alias to your bashrc <br> `echo "alias kube_config=". ~/.kube_config.sh"`
3. source bashrc to get this to work<br> `source ~/.bashrc`