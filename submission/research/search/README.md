# Native search and packing

The C++ triangle search uses the grid, shape, adjacency cloud and isohedral checker from Craig Kaplan's `heesch-sat` at `d12a527c04310fed51d522318126781e2f7ed56d`. Set `KAPLAN_SRC` to that separate checkout's `src` directory. Compile from this directory with a C++20 compiler. The compatibility header comes from our first Yukon entry. [Pinned source](https://github.com/isohedral/heesch-sat/tree/d12a527c04310fed51d522318126781e2f7ed56d)

```sh
c++ -O2 -std=c++20 -I"$KAPLAN_SRC" -Icompat search.cpp "$KAPLAN_SRC/isohedral.cpp" -o search
c++ -O2 -std=c++20 torus.cpp -o torus
xz -dc ../data/third.tsv.xz > third.tsv
mkdir -p patches
./search --batch third.tsv patches 5 21039 4 > third-d5.tsv
```

In `search`, the last parameter is the time limit per outline in seconds. An interruption or recursive support failure is a native diagnostic. Each positive patch included in the submission passes the independent frozen verifier. The second seed is 9517 with 5 seconds per previously time-limited shape. The finite-quotient solver reads the same tabular input via stdin, with maximum number of copies and a per-quotient node limit as positional arguments. For a quick certificate replay use `python ../replay.py` with the benchmark installed.

The CP-SAT code uses OR-Tools 9.15. Run `python repack.py DESTINATION` to generate a candidate fixed-patch packing. Runtime limits and solver versions can affect which solutions emerge. The exact 43-copy submission is archived in `../../best.heesch`.
