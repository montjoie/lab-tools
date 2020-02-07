#!/bin/sh

CFG=""
B_HUB=""
while [ $# -ge 1 ];do
case $1 in
-f)
	shift
	CFG=$1
	shift
;;
-p)
	shift
	VPORT=$1
	shift
;;
-a)
	shift
	ACTION=$1
	shift
	case $ACTION in
	on)
	;;
	off)
	;;
	reset)
	;;
	switch_on)
		ACTION=on
	;;
	switch_off)
		ACTION=off
	;;
	*)
		echo "ERROR: unknown action $ACTION"
		exit 1
	;;
	esac
;;
*)
	echo "ERROR: unknown arg $1"
	exit 1
;;
esac
done

for devi in $(ls /sys/bus/usb/devices/*/manufacturer)
do
	grep -q VIA $devi
	if [ $? -eq 0 ];then
		B_HUB=$(echo $devi | cut -d'/' -f6 | sed 's,.4$,g,')
	fi
done

if [ -z "$B_HUB" ];then
	echo "ERROR: No compatible HUB found"
	exit 1
fi

echo "INFO: found compatible HUB at $B_HUB"

if [ -z "$VPORT" ];then
	echo "ERROR: No port given"
	exit 1
fi

case $VPORT in
1)
	B=$B_HUB
	PORT=3
;;
2)
	B=$B_HUB
	PORT=2
;;
3)
	B=$B_HUB
	PORT=1
;;
4)
	B=$B_HUB.4
	PORT=3
;;
5)
	B=$B_HUB.4
	PORT=2
;;
6)
	B=$B_HUB.4
	PORT=1
;;
7)
	B=$B_HUB.4.4
	PORT=3
;;
8)
	B=$B_HUB.4.4
	PORT=2
;;
9)
	B=$B_HUB.4.4
	PORT=1
;;
10)
	B=$B_HUB.4.4
	PORT=4
;;
esac

echo "PORT $VPORT is on $B port $PORT"

if [ -z "$ACTION" ];then
	exit 0
fi

case $ACTION
in
off)
	uhubctl -l $B -p $PORT -a 0
;;
on)
	uhubctl -l $B -p $PORT -a 1
;;
reset)
	uhubctl -l $B -p $PORT -a 2
;;
esac
