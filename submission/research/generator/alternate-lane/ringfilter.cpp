// Necessary local surround condition for square and hexagonal cell grids.
// Align every orientation of the tile to its halo, enumerate compatible covers,
// and propagate support across the inverse of each placement. Work exhaustion
// returns UNKNOWN. A surviving local surround is a search lead only.
#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

using Point = std::pair<int, int>;
using Matrix = std::array<int, 4>;
using Bits = std::uint64_t;
using Mask = std::vector<Bits>;

Point transform(const Matrix &m, Point point) {
    auto [x, y] = point;
    return {m[0]*x + m[1]*y, m[2]*x + m[3]*y};
}

Matrix compose(const Matrix &a, const Matrix &b) {
    return {a[0]*b[0] + a[1]*b[2], a[0]*b[1] + a[1]*b[3],
            a[2]*b[0] + a[3]*b[2], a[2]*b[1] + a[3]*b[3]};
}

std::vector<Matrix> orientations(bool hex) {
    const Matrix rotation = hex ? Matrix{0,-1,1,1} : Matrix{0,-1,1,0};
    const Matrix reflection = {0,1,1,0};
    Matrix current = {1,0,0,1};
    std::vector<Matrix> result;
    for (int i = 0; i < (hex ? 6 : 4); ++i) {
        result.push_back(current);
        result.push_back(compose(current, reflection));
        current = compose(rotation, current);
    }
    return result;
}

struct Placement {
    Matrix orientation;
    Point shift;
    Bits coverage = 0;
    int inverse = -1;
    Mask conflicts;
};

int population(const Mask &mask) {
    int total = 0;
    for (Bits word : mask) total += std::popcount(word);
    return total;
}

bool test(const Mask &mask, int id) {
    return (mask[id / 64] & (Bits{1} << (id % 64))) != 0;
}

void set_bit(Mask &mask, int id) {
    mask[id / 64] |= Bits{1} << (id % 64);
}

struct Search {
    std::vector<Placement> placements;
    std::vector<Mask> coverers;
    int halo_size = 0;
    Bits full = 0;
    int work;
    int initial_work;
    int completed_depth = 0;
    int remaining = 0;

    Search(const std::vector<Point> &shape, bool hex, int budget)
        : work(budget), initial_work(budget) {
        std::set<Point> core(shape.begin(), shape.end());
        std::set<Point> halo;
        std::vector<Point> steps = hex
            ? std::vector<Point>{{1,0},{0,1},{-1,1},{-1,0},{0,-1},{1,-1}}
            : std::vector<Point>{{1,0},{0,1},{-1,0},{0,-1},{1,1},{-1,1},{-1,-1},{1,-1}};
        for (auto [x,y] : shape) for (auto [u,v] : steps)
            if (!core.contains({x+u,y+v})) halo.emplace(x+u,y+v);
        if (halo.size() > 64) throw std::runtime_error("halo width over 64");
        std::map<Point, int> halo_index;
        for (auto p : halo) halo_index[p] = halo_size++;
        full = halo_size == 64 ? ~Bits{0} : ((Bits{1} << halo_size) - 1);
        std::map<Point, std::vector<int>> cell_owners;
        std::map<std::pair<Matrix,Point>, int> ids;
        for (const auto &orientation : orientations(hex)) {
            std::vector<Point> turned;
            for (auto p : shape) turned.push_back(transform(orientation,p));
            std::set<Point> offsets;
            for (auto [x,y] : halo) for (auto [u,v] : turned)
                offsets.emplace(x-u,y-v);
            for (auto [dx,dy] : offsets) {
                Bits coverage = 0;
                bool occupied = false;
                for (auto [u,v] : turned) {
                    const Point p{u+dx,v+dy};
                    if (core.contains(p)) { occupied = true; break; }
                    auto found = halo_index.find(p);
                    if (found != halo_index.end()) coverage |= Bits{1} << found->second;
                }
                if (occupied || coverage == 0) continue;
                const int id = static_cast<int>(placements.size());
                placements.push_back({orientation,{dx,dy},coverage});
                ids[{orientation,{dx,dy}}] = id;
                for (auto [u,v] : turned) cell_owners[{u+dx,v+dy}].push_back(id);
            }
        }
        const int words = (static_cast<int>(placements.size()) + 63) / 64;
        coverers.resize(halo_size, Mask(words));
        for (int id = 0; id < static_cast<int>(placements.size()); ++id) {
            auto &p = placements[id];
            const auto [a,b,d,e] = p.orientation;
            const int determinant = a*e - b*d;
            const Matrix inverse{determinant*e,-determinant*b,-determinant*d,determinant*a};
            const auto [ix,iy] = transform(inverse,p.shift);
            p.inverse = ids.at({inverse,{-ix,-iy}});
            p.conflicts.resize(words);
            for (Bits covered = p.coverage; covered; covered &= covered-1)
                set_bit(coverers[std::countr_zero(covered)], id);
        }
        for (const auto &[cell, owners] : cell_owners) {
            Mask all(words);
            for (int id : owners) set_bit(all,id);
            for (int id : owners) {
                auto &conflicts = placements[id].conflicts;
                for (int k = 0; k < words; ++k) conflicts[k] |= all[k];
            }
        }
    }

    // 1 = cover, 0 = impossible, -1 = work limit. Mark all members of each
    // found cover so subsequent support queries can skip them.
    int cover(Bits uncovered, const Mask &available, Mask &supported) {
        if (uncovered == 0) return 1;
        if (--work < 0) return -1;
        int best = -1, smallest = 2147483647;
        for (Bits cells = uncovered; cells; cells &= cells-1) {
            const int index = std::countr_zero(cells);
            int count = 0;
            for (size_t i = 0; i < available.size(); ++i)
                count += std::popcount(available[i] & coverers[index][i]);
            if (count == 0) return 0;
            if (count < smallest) { smallest = count; best = index; }
        }
        for (int i = 0; i < static_cast<int>(available.size()); ++i) {
            for (Bits bits = available[i] & coverers[best][i]; bits; bits &= bits-1) {
                const int id = 64*i + std::countr_zero(bits);
                const auto &p = placements[id];
                Mask next(available.size());
                for (size_t k = 0; k < next.size(); ++k)
                    next[k] = available[k] & ~p.conflicts[k];
                const int result = cover(uncovered & ~p.coverage, next, supported);
                if (result == 1) set_bit(supported,id);
                if (result != 0) return result;
            }
        }
        return 0;
    }

    std::string run(int max_depth) {
        const int count = static_cast<int>(placements.size());
        Mask allowed((count + 63) / 64);
        for (int i = 0; i < count; ++i) set_bit(allowed,i);
        for (int depth = 1; depth <= max_depth; ++depth) {
            Mask supported(allowed.size());
            const int any = cover(full, allowed, supported);
            if (any < 0) return "UNKNOWN";
            if (!any) return "EXCLUDED";
            if (depth == max_depth) {
                completed_depth = depth;
                remaining = population(allowed);
                return "SURVIVED";
            }
            for (int id = 0; id < count; ++id) {
                if (!test(allowed,id) || test(supported,id)) continue;
                const auto &p = placements[id];
                Mask available(allowed.size());
                for (size_t k = 0; k < available.size(); ++k)
                    available[k] = allowed[k] & ~p.conflicts[k];
                const int valid = cover(full & ~p.coverage,available,supported);
                if (valid < 0) return "UNKNOWN";
                if (valid == 1) set_bit(supported,id);
            }
            Mask next(allowed.size());
            for (int id = 0; id < count; ++id)
                if (test(supported,id) && test(supported,placements[id].inverse))
                    set_bit(next,id);
            completed_depth = depth;
            remaining = population(next);
            if (next == allowed) {
                completed_depth = max_depth;
                return "SURVIVED";
            }
            allowed = std::move(next);
        }
        return "SURVIVED";
    }
};

int main(int argc, char **argv) {
    const int budget = argc > 1 ? std::stoi(argv[1]) : 30000;
    const int depth = argc > 2 ? std::stoi(argv[2]) : 5;
    std::string line;
    while (std::getline(std::cin,line)) {
        std::istringstream in(line);
        std::string id, grid;
        in >> id >> grid;
        std::vector<Point> shape;
        int x, y;
        while (in >> x >> y) shape.emplace_back(x,y);
        if (shape.empty() || (grid != "O?" && grid != "H?")) return 2;
        Search search(shape, grid == "H?", budget);
        const std::string result = search.run(depth);
        std::cout << id << ' ' << result << ' ' << search.completed_depth << ' '
                  << search.remaining << ' ' << (budget - search.work) << '\n';
    }
}
