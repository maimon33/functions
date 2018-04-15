#!/usr/bin/env bash


sudo useradd -m gui
sudo passwd gui
sudo usermod -aG admin gui
sudo vim /etc/ssh/sshd_config # edit line "PasswordAuthentication" to yes
sudo /etc/init.d/ssh restart


sudo apt-get update
sudo apt-get install ubuntu-desktop
sudo apt-get install vnc4server


su - gui
vncserver
vncserver -kill :1
vim /home/gui/.vnc/xstartup

vncserver

####


sudo apt-get update
sudo apt-get install xfce4 xfce4-goodies tightvncserver vnc4server -y


mv ~/.vnc/xstartup ~/.vnc/xstartup.bak
vi ~/.vnc/xstartup
"""
#!/bin/bash
xrdb $HOME/.Xresources
startxfce4 &
"""
sudo chmod +x ~/.vnc/xstartup


sudo vi  /etc/init.d/vncserver
"""
#!/bin/bash
PATH="$PATH:/usr/bin/"
export USER="gui"
DISPLAY="1"
DEPTH="16"
GEOMETRY="1024x768"
OPTIONS="-depth ${DEPTH} -geometry ${GEOMETRY} :${DISPLAY}"
. /lib/lsb/init-functions

case "$1" in
start)
log_action_begin_msg "Starting vncserver for user '${USER}' on localhost:${DISPLAY}"
su ${USER} -c "/usr/bin/vncserver ${OPTIONS}"
;;

stop)
log_action_begin_msg "Stopping vncserver for user '${USER}' on localhost:${DISPLAY}"
su ${USER} -c "/usr/bin/vncserver -kill :${DISPLAY}"
;;

restart)
$0 stop
$0 start
;;
esac
exit 0
"""

sudo chmod +x /etc/init.d/vncserver

sudo service vncserver start







sudo useradd -m awsgui
sudo passwd awsgui
sudo usermod -aG admin awsgui
sudo vim /etc/ssh/sshd_config # edit line "PasswordAuthentication" to yes
sudo /etc/init.d/ssh restart


sudo apt-get update
sudo apt-get install ubuntu-desktop
sudo apt-get install vnc4server


su - awsgui
vncserver
vncserver -kill :1
vim /home/awsgui/.vnc/xstartup

vncserver

####


nano ~/.vnc/xstartup

Add the following line.

!/bin/sh
def
export XKLXMODMAPDISABLE=1
unset SESSIONMANAGER
unset DBUSSESSIONBUSADDRESS

gnome-panel &
gnome-settings-daemon &
metacity &
nautilus &
gnome-terminal &

sudo apt-get install ubuntu-gnome-desktop -y


####


sudo apt-get update
sudo apt-get install xfce4 xfce4-goodies tightvncserver


mv ~/.vnc/xstartup ~/.vnc/xstartup.bak
vi ~/.vnc/xstartup
"""
#!/bin/bash
xrdb $HOME/.Xresources
startxfce4 &
"""
sudo chmod +x ~/.vnc/xstartup


sudo vi  /etc/init.d/vncserver
"""#!/bin/bash
PATH="$PATH:/usr/bin/"
export USER="awsgui"
DISPLAY="1"
DEPTH="16"
GEOMETRY="1024x768"
OPTIONS="-depth ${DEPTH} -geometry ${GEOMETRY} :${DISPLAY}"
. /lib/lsb/init-functions

case "$1" in
start)
log_action_begin_msg "Starting vncserver for user '${USER}' on localhost:${DISPLAY}"
su ${USER} -c "/usr/bin/vncserver ${OPTIONS}"
;;

stop)
log_action_begin_msg "Stopping vncserver for user '${USER}' on localhost:${DISPLAY}"
su ${USER} -c "/usr/bin/vncserver -kill :${DISPLAY}"
;;

restart)
$0 stop
$0 start
;;
esac
exit 0
"""

sudo chmod +x /etc/init.d/vncserver

sudo service vncserver start