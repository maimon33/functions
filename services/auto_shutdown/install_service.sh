
/etc/default/idle_shutdown
"""
# Paperspace idle_shutdown.sh tool configuration

# Time (in minutes) that the system can be idle before being shut down
IDLE_TIME=30
"""

/lib/systemd/system/idle.shutdown.service
"""
[Unit]
Description=Idle Auto Shutdown
Requires=dbus.service
After=dbus.service
StartLimitInterval=0

[Service]
EnvironmentFile=-/etc/default/idle_shutdown
ExecStart=/usr/local/bin/idle_shutdown.sh $IDLE_TIME
ExecStop=
ExecReload=/bin/kill -HUP $MAINPID
KillMode=process
Restart=on-failure
RestartPreventExitStatus=255
Type=simple

[Install]
WantedBy=multi-user.target
"""

/usr/local/bin/idle_shutdown.sh
"""
#!/bin/bash

idle_time=`expr $1 \* 60`

if [ -z "$idle_time" ]; then
  exit 1
fi

shutdown_system() {
  shutdown
}

ssh_idle_seconds=0
while true; do

  for i in {1..60} ; do
      if [ $(ps -aef | grep sshd: | grep -v grep | grep -v '\[accepted\]' | grep -v '\[net\]' | wc -l) -gt 0 ] ; then
        ssh_idle_seconds=0
      else
        ssh_idle_seconds=`expr $ssh_idle_seconds + 1`
      fi

      if [ "$ssh_idle_seconds" -gt "$idle_time" ] ; then
          logger "shutting down due to idle timer"
          shutdown_system
          sleep $idle_time
      fi
      sleep 1
  done

done
"""