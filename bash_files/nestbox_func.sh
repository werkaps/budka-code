#!/bin/bash


function nestbox(){
	echo -e "\e[1;33mNestBox running on http://raspberrypi.local:8000/ \nDo not close this window!\e[31m"
	/usr/bin/env python3 /home/nestbox/Documents/budka-code/app.py
	}


