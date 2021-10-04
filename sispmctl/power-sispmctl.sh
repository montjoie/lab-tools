#!/bin/sh

if [ $# -le 1 ];then
	echo "ERROR: need more argument"
	exit 1
fi

lock() {
	TIMEOUT=0
	while [ $TIMEOUT -le 40 ]
	do
		mkdir /tmp/sispmctl.lock 2>/dev/null
		if [ $? -eq 0 ];then
			return 0
		fi
		echo "DEBUG: on attend"
		sleep 30
		TIMEOUT=$(($TIMEOUT+1))
	done
	echo "ERROR: cannot lock (timeout=$TIMEOUT)"
	return 1
}

unlock() {
	rmdir /tmp/sispmctl.lock
}

case "$1" in
reset)
	lock || exit 1
	sispmctl -f "$2"
	sleep 3
	sispmctl -o "$2"
	unlock
	exit 0
;;
off)
	lock || exit 1
	sispmctl -f "$2"
	unlock
	exit 0
;;
on)
	lock || exit 1
	sispmctl -o "$2"
	unlock
	exit 0
;;
*)
	echo "ERROR: unknow command: $1"
	exit 1
esac
exit 1
