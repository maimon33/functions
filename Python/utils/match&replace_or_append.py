#!/bin/python

def update_file(filepath, match_string, replace_string):
    # Read in the file
    with open(filepath, 'r') as file:
        filedata = file.read()

        # Replace the target string
        filedata = filedata.replace(match_string, replace_string)

    # Write the file out again
    with open(filepath, 'w') as file:
        file.write(filedata)


update_file('PATH to File', '<string to replace>', '<new string>')