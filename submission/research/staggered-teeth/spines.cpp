// Enumerate two dense axial rows with separated one-cell-wide teeth on both sides.
#include <algorithm>
#include <bit>
#include <cstdint>
#include <iostream>
#include <set>
#include <string>

using Bits = std::uint64_t;

struct Board {
    int width;
    Bits row, all, left, right, rim;
    explicit Board(int w) : width(w), row((Bits{1}<<w)-1), all((Bits{1}<<(4*w))-1) {
        left = 1 | (Bits{1}<<w) | (Bits{1}<<(2*w)) | (Bits{1}<<(3*w));
        right = left << (w-1);
        rim = left | right | row | (row<<(3*w));
    }
    Bits flood(Bits seed, Bits allowed) const {
        Bits previous;
        do {
            previous = seed;
            seed |= (((seed & ~right) << 1) | ((seed & ~left) >> 1)
                   | (seed << width) | (seed >> width)
                   | ((seed & ~left) << (width-1)) | ((seed & ~right) >> (width-1))) & allowed;
        } while (seed != previous);
        return seed;
    }
    std::set<Bits> dense() const {
        std::set<Bits> out;
        for (int a=0; a<width; a++) for (int b=a+4; b<width; b++) {
            Bits span = ((Bits{1}<<(b+1)) - 1) ^ ((Bits{1}<<a)-1);
            out.insert(span);
            for (int c=a+1; c<b; c++) out.insert(span ^ (Bits{1}<<c));
        }
        return out;
    }
};

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    const int width = std::stoi(argv[1]), modulus = std::stoi(argv[2]);
    if (width < 6 || width > 11 || modulus < 1) return 2;
    Board board(width);
    const auto middles = board.dense();
    for (Bits bottom=1; bottom<=board.row; bottom++) {
        // At least two separated runs of teeth along each exterior row.
        if (std::popcount(bottom & ~(bottom<<1)) < 2) continue;
        for (Bits top=1; top<=board.row; top++) {
            if (std::popcount(top & ~(top<<1)) < 2) continue;
            for (auto middle1 : middles) for (auto middle2 : middles) {
                const Bits shape = bottom | (middle1<<width) | (middle2<<(2*width)) | (top<<(3*width));
                const int size = std::popcount(shape);
                if (size < 19 || size > 20 || !(shape & board.left) || !(shape & board.right)) continue;
                // Deterministic sampling before the flood checks for wider regions.
                Bits key = shape;
                key = (key^(key>>30)) * 0xbf58476d1ce4e5b9ULL;
                key = (key^(key>>27)) * 0x94d049bb133111ebULL;
                if ((key^(key>>31)) % modulus) continue;
                if (board.flood(shape & -shape, shape) != shape) continue;
                const Bits empty = board.all ^ shape;
                if (board.flood(board.rim & empty, empty) != empty) continue;
                // Opposite ends under a half-turn have the same shape.
                Bits turned=0;
                for (int i=0;i<4*width;i++) if (shape & (Bits{1}<<i)) turned |= Bits{1}<<(4*width-1-i);
                // The sampling hash can select either frame, so retain the
                // representative that passed, with a common identity for deduplication.
                std::cout<<"sp"<<width<<"_"<<std::hex<<std::min(shape,turned)<<std::dec<<" H?";
                for (int x=0;x<width;x++) for (int y=0;y<4;y++)
                    if (std::min(shape,turned)&(Bits{1}<<(x+width*y))) std::cout<<' '<<x<<' '<<y;
                std::cout<<'\n';
            }
        }
    }
}
