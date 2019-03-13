#!/bin/bash

# start in new detached tmux window
tmux new -d 'python /home/pi/home-automation/home.py' \;
tmux a
