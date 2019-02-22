#!/bin/bash

tmux new -d 'python /home/pi/home-automation/home.py' \; pipe-pane 'cat > /tmp/log.txt'
