import subprocess

AWS_ACCESS_KEY_ID = subprocess.check_output(['bash','-c', bashCommand("AWS_ACCESS_KEY_ID")]).strip()
AWS_SECRET_ACCESS_KEY = subprocess.check_output(['bash','-c', bashCommand("AWS_SECRET_ACCESS_KEY")]).strip()