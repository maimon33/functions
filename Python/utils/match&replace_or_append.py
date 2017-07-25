import re
import subprocess

def update_file(file, match_string, replace_string):
    content = open(file).read()
    for match in re.finditer(match_string, content, re.MULTILINE):
        subprocess.Popen(["sed",
                          "-i",
                          "''",
                          "s/.{}/{} base/".format(match_string, replace_string),
                          file])
        return "Hosts fils Changed"
    with open(file, "a") as myfile:
        myfile.write("{} base".format(replace_string))


update_file("/etc/hosts", '.*\ HOST', get_vhost_ip())