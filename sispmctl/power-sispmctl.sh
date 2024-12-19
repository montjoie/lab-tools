#!/bin/sh

SERIAL=""
SISPMCTL_OPTS=""

help() {
	echo "USAGE: $0 [reset|off|on] portnumber[1...4] [serialnumber]"
}

if [ $# -le 1 ];then
	echo "ERROR: need more argument"
	help()
	exit 1
fi

if [ ! -z "$3" ];then
	SERIAL="$3"
	SISPMCTL_OPTS="-D $SERIAL"
fi
LOCKFILE='/tmp/sispmctl.lock'

lock() {
	TIMEOUT=0
	while [ $TIMEOUT -le 40 ]
	do
		mkdir "$LOCKFILE" 2>/dev/null
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
	rmdir "$LOCKFILE"
}

case "$1" in
reset)
	lock || exit 1
	sispmctl $SISPMCTL_OPTS -f "$2"
	sleep 3
	sispmctl $SISPMCTL_OPTS -o "$2"
	ret=$?
	unlock
	exit $ret
;;
off)
	lock || exit 1
	sispmctl $SISPMCTL_OPTS -f "$2"
	ret=$?
	unlock
	exit $ret
;;
on)
	lock || exit 1
	sispmctl $SISPMCTL_OPTS -o "$2"
	ret=$?
	unlock
	exit $ret
;;
*)
	echo "ERROR: unknow command: $1"
	exit 1
esac
exit 1
