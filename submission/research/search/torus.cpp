// Search elementary-triangle quotients for exact periodic tilings.
// Input: rows "id I? x y ..." with Kaplan's encoded triangle centers.
// Each success writes an explicit index-K*area HNF lattice and K transforms.
// Work is bounded separately per lattice; "UNKNOWN" gives no non-tiler evidence.
#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using Cell = std::pair<int,int>;
using Matrix = std::array<int,4>;
using Mask = std::array<std::uint64_t,32>;
struct Motion { Matrix turn; int dx, dy; };
struct Row { Mask bits{}; Motion placement; };

struct Lattice {
    int a,b,c;
    int residue(int x, int y) const {
        const int p=(x%3+3)%3;
        const int u=(x-p)/3, v=(y-p)/3;
        int ry = v % c;
        if (ry < 0) ry += c;
        int rx = (u - ((v - ry)/c)*b) % a;
        if (rx < 0) rx += a;
        return 2*(ry*a + rx)+p;
    }
};

std::vector<Matrix> triangle_turns() {
    return {{1,0,0,1},{-1,-1,1,0},{0,1,-1,-1},{1,0,-1,-1},{0,1,1,0},{-1,-1,0,1},
            {0,-1,-1,0},{-1,0,1,1},{1,1,0,-1},{1,1,-1,0},{-1,0,0,-1},{0,-1,1,1}};
}

bool has_cell(const Mask &m, int cell) {
    return (m[cell/64] & (std::uint64_t{1} << (cell%64))) != 0;
}
void mark(Mask &m, int cell) {
    m[cell/64] |= std::uint64_t{1} << (cell%64);
}

struct TileSearch {
    int k, n, words;
    std::vector<Row> rows;
    std::vector<std::vector<int>> covering;
    std::vector<Motion> selected;
    int nodes;
    Lattice lattice;
    const std::vector<Cell> &cells;
    const std::vector<Matrix> &turns;

    bool separate(const Mask &a, const Mask &b) const {
        for (int i = 0; i < words; ++i)
            if (a[i] & b[i]) return false;
        return true;
    }

    bool dfs(const Mask &occupied) {
        if (static_cast<int>(selected.size()) == k) return true;
        if (--nodes <= 0) return false;
        int minimum = 2147483647;
        int pivot = -1;
        for (int cell = 0; cell < n; ++cell) {
            if (has_cell(occupied,cell)) continue;
            int count = 0;
            for (int id : covering[cell]) {
                if (separate(occupied,rows[id].bits) && ++count >= minimum)
                    break;
            }
            if (!count) return false;
            if (count < minimum) { minimum = count; pivot = cell; }
        }
        if (pivot < 0) return false;
        for (int id : covering[pivot]) {
            if (!separate(occupied,rows[id].bits)) continue;
            Mask next = occupied;
            for (int i = 0; i < words; ++i) next[i] |= rows[id].bits[i];
            selected.push_back(rows[id].placement);
            if (dfs(next)) return true;
            selected.pop_back();
            if (nodes <= 0) break;
        }
        return false;
    }

    bool solve() {
        Mask origin{};
        for (auto [x,y] : cells) {
            int idx = lattice.residue(x,y);
            if (has_cell(origin,idx)) return false;
            mark(origin,idx);
        }
        selected.push_back({{1,0,0,1},0,0});
        if (k == 1) return true;
        covering.resize(n);
        std::set<Mask> used;
        for (unsigned i=0;i<turns.size();i++) {
            const auto &m = turns[i];
            int off = i>=6;
            std::vector<Cell> oriented;
            Mask prototype{};
            for (auto [x,y] : cells) {
                const int u = m[0]*x+m[1]*y+off, v = m[2]*x+m[3]*y+off;
                const int idx = lattice.residue(u,v);
                if (has_cell(prototype,idx)) break;
                mark(prototype,idx);
                oriented.emplace_back(u,v);
            }
            if (oriented.size() != cells.size()) continue;
            for (int dy = 0; dy < lattice.c; ++dy) {
                for (int dx = 0; dx < lattice.a; ++dx) {
                    Mask candidate{};
                    bool touches_origin = false;
                    for (auto [u,v] : oriented) {
                        int idx = lattice.residue(3*dx+u,3*dy+v);
                        if (has_cell(origin,idx)) { touches_origin = true; break; }
                        mark(candidate,idx);
                    }
                    if (touches_origin || !used.insert(candidate).second) continue;
                    const int id = static_cast<int>(rows.size());
                    rows.push_back({candidate,{m,3*dx+off,3*dy+off}});
                    for (int word = 0; word < words; ++word)
                        for (auto mask = candidate[word]; mask; mask &= mask-1)
                            covering[word*64+std::countr_zero(mask)].push_back(id);
                }
            }
        }
        return dfs(origin);
    }
};

int main(int argc, char **argv) {
    const int maxk = argc > 1 ? std::stoi(argv[1]) : 6;
    const int budget = argc > 2 ? std::stoi(argv[2]) : 150;
    std::string line;
    while (std::getline(std::cin,line)) {
        std::istringstream in(line);
        std::string id,grid;
        in >> id >> grid;
        int x,y;
        std::vector<Cell> cells;
        while (in >> x >> y) cells.emplace_back(x,y);
        if (cells.empty() || maxk*cells.size() > 2048) return 2;
        if (grid!="I?") return 2;
        const auto turns = triangle_turns();
        bool found = false;
        for (int k = 1; k <= maxk && !found; ++k) {
            const int n = static_cast<int>(cells.size()) * k;
            if (n%2) continue;
            const int pairs=n/2;
            for (int a = 1; a <= pairs && !found; ++a) {
                if (pairs % a) continue;
                const int c = pairs/a;
                for (int b = 0; b < a && !found; ++b) {
                    TileSearch search{k,n,(n+63)/64,{},{},{},budget,{a,b,c},cells,turns};
                    if (!search.solve()) continue;
                    std::cout << id << " TILER " << k << ' ' << a << ' ' << b << ' ' << c;
                    for (const auto &motion : search.selected) {
                        const auto [u,v,z,w] = motion.turn;
                        std::cout << ' ' << u << ',' << v << ',' << motion.dx
                                  << ',' << z << ',' << w << ',' << motion.dy;
                    }
                    std::cout << '\n' << std::flush;
                    found = true;
                }
            }
        }
        if (!found) std::cout << id << " UNKNOWN\n" << std::flush;
    }
}
