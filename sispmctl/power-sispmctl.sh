#!/bin/sh

if [ $# -le 1 ];then
	echo "ERROR: need more argument"
fi

case $1 in
reset)
	sispmctl -f $2
	sleep 3
	sispmctl -o $2
	exit $?
;;
off)
	sispmctl -f $2
	exit $?
;;
on)
	sispmctl -o $2
	exit $?
;;
*)
	echo "ERROR: unknow command: $1"
	exit 1
esac
exit 1
