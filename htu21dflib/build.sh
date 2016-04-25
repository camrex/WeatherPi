#!/bin/bash
# Build the code with a standalone test program.
#   htu21dflib      -- A small test program using the library. Use it verify
#                       the code and sensor are working.
#   htu21dflib.o    -- The library code which can be linked into a larger program.
#
gcc -O2 -Wall -o htu21dflib -DHTU21DFTEST htu21dflib.c
gcc -O2 -Wall -c htu21dflib.c
