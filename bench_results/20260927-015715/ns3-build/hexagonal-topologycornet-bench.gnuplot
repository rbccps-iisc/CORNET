set term pdf
set output "/home/acharya/simulation/CORNET_Research/bench_results/20260927-015715/ns3-build/./hexagonal-topologycornet-bench.gnuplot.pdf"
set style arrow 1 lc "black" lt 1 head filled
set xrange [-6929:6929]
set yrange [-6929:6929]
set arrow 1 from 0,0 rto 124.996,72.1667 arrowstyle 1 
set object 1 polygon from \
1, -577.333 to \
-498.985, -288.667 to \
-498.985, 288.667 to \
1, 577.333 to \
500.985, 288.667 to \
500.985, -288.667 to \
1, -577.333 front fs empty 
set label 1 "1" at 1 , 0 center
set label at 110.796 , 216.784 point pointtype 7 pointsize 0.2 center
unset key
plot 1/0
