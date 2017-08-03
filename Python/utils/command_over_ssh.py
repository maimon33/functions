#!/bin/python

import paramiko

host = ''
username = ''
password = ''

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host , username=username, password=password)

# Send command without output
ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("touch assi.assi")


# Connect. Send command and print output
channel = ssh.invoke_shell()
stdin = channel.makefile('wb')
stdout = channel.makefile('rb')

stdin.write('''
ls
exit
''')
print stdout.read()

stdout.close()
stdin.close()
ssh.close()