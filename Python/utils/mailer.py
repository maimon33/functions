#!/bin/python

import smtplib

def send_mail(subject, msg):
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login("<Gmail Username>", "<Gmail Password>")

    server.sendmail("<Source Mail", "Destination Mail",
                    'Subject: {}\n\n{}'.format(subject, msg))
    server.quit()

send_mail("Subject", "Mail content")