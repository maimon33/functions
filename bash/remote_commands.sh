#!/usr/bin/expect -f

spawn ssh assi@192.168.240.140 -o StrictHostKeychecking=no
expect "assword:"
send "123456\r"
sleep 1
expect "$ "
send "ls\r"
interact