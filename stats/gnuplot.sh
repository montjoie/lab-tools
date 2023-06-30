#!/bin/sh

echo "
set key at graph 1, 1 horizontal samplen 10
set style data histogram
set style histogram cluster gap 1
set style fill solid border -1
set boxwidth 1
set xtic rotate by 90 scale 0
unset ytics
set y2tics rotate by 90
#set xrange [-0.5:6.5]
set y2label 'Seconds' offset 0
set xlabel ' '
set size 1, 1
set label 1 'Devtype' offset 10, -2 centre rotate by 180
set label 2 'Waittime' at graph 9, 85 left rotate by 90
set term png
set output 'waittime.png'
p 'waittime.dat' u 2 title 'Waittime', '' u 0:(0):xticlabel(1) w l title ''
" > wait.gnuplot

for i in 1 2 7 15 30
do
echo "
set title 'Waittime on last $i days $(date)'
set auto x
set style data histogram
set style histogram cluster gap 1
set style fill solid border -1
set boxwidth 0.9
set xtics border offset -5 rotate by 1 scale 0
set xlabel 'Devtype' offset -10
#set bmargin 10 
set term png size 1600,900
set output 'waittime-$i.png'
#set label 1 'Devtype' offset 10, -2 centre
plot 'waittime-$i.dat' using 2:xtic(1)
" > wait.gnuplot

gnuplot wait.gnuplot || exit $?
if [ -e /var/www/html/lava/ ];then
	cp waittime-$i.png /var/www/html/lava/
	chmod 644 /var/www/html/lava/waittime-$i.png
fi
done

echo "
set title 'Statbyday'
set auto x
set style data histogram
set style histogram cluster gap 1
set style fill solid border -1
set boxwidth 0.9
set xtic rotate by -45 scale 0
#set bmargin 10 
set term png size 8000,900
set output 'statbyday.png'
plot 'statbyday.dat' using 2:xtic(1)
" > statbyday.gnuplot
gnuplot statbyday.gnuplot

if [ -e /var/www/html/lava/ ];then
	cp statbyday.png /var/www/html/lava/
	chmod 644 /var/www/html/lava/*.png
fi

echo "
set title 'Fiability'
set auto x
set style data histogram
set style histogram cluster gap 1
set style fill solid border -1
set boxwidth 0.9
set xtic rotate by -45 scale 0
#set bmargin 10 
set term png size 2600,900
set output 'fiabi.png'
plot 'fiabi-30.dat' using 2:xtic(1)
" > fiabi.gnuplot
gnuplot fiabi.gnuplot

if [ -e /var/www/html/lava/ ];then
	cp fiabi.png /var/www/html/lava/
	chmod 644 /var/www/html/lava/*.png
fi

echo "<html><body>" > hc.html
for hc in $(ls hc)
do
echo "Handlin $hc"
sort hc/$hc > hc/tmp
mv hc/tmp hc/$hc
echo "
set title '$hc by day'
set auto x
set style data histogram
set style histogram cluster gap 1
set style fill solid border -1
set boxwidth 0.9
#set xtic rotate by -45 scale 0
set xtics border rotate offset 0 scale 0
#set bmargin 10 
set term png size 1600,500
set output 'png/$hc.png'
plot 'hc/$hc' using 2:xtic(1) with boxes lt rgb '#40FF00', '' using 3 with boxes lt rgb '#FF0000', '' using 4 with boxes lt rgb '#0000FF'
" > png/$hc.gnuplot
gnuplot png/$hc.gnuplot
echo "$hc<br><img src=$hc.png><br>" >> hc.html
if [ -e /var/www/html/lava/ ];then
	cp png/$hc.png /var/www/html/lava/
	chmod 644 /var/www/html/lava/*.png
fi
done

echo "</body></html>" >> hc.html

if [ -e /var/www/html/lava/ ];then
	cp hc.html /var/www/html/lava/
	chmod 644 /var/www/html/lava/*.png
fi
