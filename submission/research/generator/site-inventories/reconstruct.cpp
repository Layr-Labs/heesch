// Reconstruct a polyhex given only the multiset of its six-neighbor patterns.
// A bit describes one occupied neighbor. Each site can rotate or reflect its
// pattern independently. Specifying a pattern fixes the occupancy of all six
// neighbors and creates new required sites on the growing frontier.
#define ARCS_LIBRARY
#include "../ribbon-word/arcs.cpp"
#include <bit>
#include <cstdint>
#include <limits>

using MaskList = uint64_t;
using Inventory = std::array<int,64>;
constexpr int stride=64, origin=32*stride+32;
std::array<int,6> step{};
std::array<unsigned,64> orbit{};
std::array<MaskList,64> variants{};
std::array<std::array<MaskList,64>,64> compatible{};

void prepare_patterns() {
    for (int i=0;i<6;++i) step[i]=dirs[i].first*stride+dirs[i].second;
    for (unsigned mask=0;mask<64;++mask) {
        unsigned best=mask;
        for (int start=0;start<6;++start) for (int sign:{1,-1}) {
            unsigned oriented=0;
            for (int i=0;i<6;++i) if (mask&(1u<<i))
                oriented|=1u<<((start+sign*i+6)%6);
            best=std::min(best,oriented);
        }
        orbit[mask]=best;
        variants[best]|=MaskList{1}<<mask;
        for (unsigned yes=0;yes<64;++yes) for (unsigned no=0;no<64;++no)
            if ((mask&yes)==yes&&!(mask&no)) compatible[yes][no]|=MaskList{1}<<mask;
    }
}

struct Builder {
    // 0 unknown, 1 empty, 2 required and unassigned, 3 assigned and occupied.
    std::array<unsigned char,stride*stride> state{};
    std::vector<int> sites{origin};
    Inventory left{};
    int area, node_limit, shape_limit;
    std::string system;
    std::set<Shape> &seen;
    std::ostream &bank,&routes;
    int nodes=0,completed=0,new_shapes=0;
    bool node_cut=false,shape_cut=false;

    Builder(const Inventory &counts,int n,int max_nodes,int max_shapes,
            const std::string &key,std::set<Shape> &all,std::ostream &b,std::ostream &r):
            left(counts),area(n),node_limit(max_nodes),shape_limit(max_shapes),
            system(key),seen(all),bank(b),routes(r) {
        state[origin]=2;
        MaskList available=0;
        int root=-1;
        for (int k=0;k<64;++k) if (left[k]) {
            available|=variants[k];
            if (root<0||std::make_tuple(left[k],-std::popcount(unsigned(k)),k)
                       <std::make_tuple(left[root],-std::popcount(unsigned(root)),root)) root=k;
        }
        place(origin,unsigned(root),available,0);
    }

    void place(int center,unsigned mask,MaskList available,int assigned) {
        if (nodes>=node_limit) { node_cut=true;return; }
        if (new_shapes>=shape_limit) { shape_cut=true;return; }
        ++nodes;
        size_t old=sites.size();
        int changed[6],count=0;
        state[center]=3;
        for (int i=0;i<6;++i) {
            int next=center+step[i];
            if (state[next]) continue;
            changed[count++]=next;
            state[next]=(mask&(1u<<i))?2:1;
            if (state[next]==2) sites.push_back(next);
        }
        unsigned base=orbit[mask];
        if (--left[base]==0) available&=~variants[base];
        if (int(sites.size())<=area) {
            if (assigned+1==area) {
                ++completed;
                Shape outline_cells;
                for (int i:sites) outline_cells.emplace_back(i/stride-32,i%stride-32);
                Shape key=norm(outline_cells);
                if (!seen.contains(key)&&!outline(key).empty()) {
                    seen.insert(key);
                    ++new_shapes;
                    bank<<seen.size()<<" H?";
                    for (auto [x,y]:key) bank<<' '<<x<<' '<<y;
                    bank<<'\n';
                    routes<<seen.size()<<'\t'<<system<<'\n';
                }
            } else {
                int best=-1,minimum=65;
                MaskList options=0;
                for (int site:sites) if (state[site]==2) {
                    unsigned yes=0,no=0;
                    for (int d=0;d<6;++d) {
                        auto neighbor=state[site+step[d]];
                        if (neighbor>=2) yes|=1u<<d;
                        if (neighbor==1) no|=1u<<d;
                    }
                    MaskList allowed=compatible[yes][no]&available;
                    int choices=std::popcount(allowed);
                    if (choices<minimum) {
                        minimum=choices;best=site;options=allowed;
                        if (!choices) break;
                    }
                }
                for (;options;options&=options-1) {
                    place(best,std::countr_zero(options),available,assigned+1);
                    if (node_cut||shape_cut) break;
                }
            }
        }
        ++left[base];
        state[center]=2;
        for (int i=0;i<count;++i) state[changed[i]]=0;
        sites.resize(old);
    }
};

int main(int argc,char **argv) {
    if (argc!=5) return 2;
    prepare_patterns();
    std::string path=argv[1];
    std::ifstream in(path+"/systems.tsv");
    std::ofstream bank(path+"/bank.tsv"),routes(path+"/origins.tsv"),log(path+"/outcomes.tsv");
    if (!in||!bank||!routes||!log) return 3;
    int max_nodes=std::stoi(argv[2]),max_per=std::stoi(argv[3]),overall=std::stoi(argv[4]);
    std::set<Shape> seen;
    std::string row;
    int examined=0;
    while (int(seen.size())<overall&&std::getline(in,row)) {
        std::istringstream tokens(row);
        std::string key;
        tokens>>key;
        Inventory counts{};
        int mask,area=0;
        while (tokens>>mask) {
            if (mask<0||mask>63||orbit[mask]!=unsigned(mask)) return 4;
            ++counts[mask];++area;
        }
        // At area 28 a connected tile and its one-cell border still fit
        // around the origin in the 64 by 64 coordinate array.
        if (!area||area>28) return 5;
        Builder b(counts,area,max_nodes,std::min(max_per,overall-int(seen.size())),key,seen,bank,routes);
        log<<key<<'\t'<<b.nodes<<'\t'<<b.completed<<'\t'<<b.new_shapes<<'\t'
           <<b.node_cut<<'\t'<<b.shape_cut<<'\n';
        ++examined;
    }
    std::ofstream report(path+"/summary.json");
    report<<"{\"counts\":{\"unique\":"<<seen.size()<<"},\"inventories_examined\":"<<examined
          <<",\"node_limit\":"<<max_nodes<<",\"per_system_new_limit\":"<<max_per<<"}\n";
    std::cout<<examined<<" inventories built "<<seen.size()<<" distinct outlines\n";
}
