// Extract local frozen AMOs and use RUP-strengthened surround clauses.
// Setting the conditioned tile true unit-propagates every overlapping pose
// false in the original per-cell AMOs, deriving each shortened surround.
#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using Cell=std::pair<int,int>;
using Off=std::array<int,3>;
struct Pose {int level,o,x,y;};
std::vector<Cell> shapes[12];
std::map<Cell,std::vector<Off>> halo[12];
std::vector<Off> touch[12];
std::vector<Pose> poses(1);
std::array<int,4*12*128*128> ids{};
int id(int level,int orient,int x,int y) {
    if(x<-64||x>=64||y<-64||y>=64||level<1||level>4) return 0;
    return ids[((level-1)*12+orient)*128*128+(y+64)*128+x+64];
}
void load(const std::string& d) {
    std::ifstream s(d+"/shapes.tsv"),h(d+"/adjacent.tsv"),u(d+"/universe.tsv");
    if(!s||!h) throw std::runtime_error("Missing geometry");
    std::string l;
    while(getline(s,l)) {
        std::istringstream r(l);int o,x,y;r>>o;while(r>>x>>y) shapes[o].emplace_back(x,y);
    }
    int o,x,y,j,dx,dy,level;
    while(h>>o>>x>>y>>j>>dx>>dy) halo[o][{x,y}].push_back({j,dx,dy});
    for(int i=0;i<12;++i) {
        std::set<Off> all;
        for(auto& [cell,offsets]:halo[i]) all.insert(offsets.begin(),offsets.end());
        touch[i].assign(all.begin(),all.end());
    }
    while(u>>level>>o>>x>>y) {
        if(x<-64||x>=64||y<-64||y>=64) throw std::runtime_error("Grid bound");
        int slot=((level-1)*12+o)*128*128+(y+64)*128+x+64;
        if(ids[slot]) throw std::runtime_error("Duplicate frozen ID");
        ids[slot]=poses.size();
        poses.push_back({level,o,x,y});
    }
}
void fast_universe(const std::string& output) {
    // Pose stencils describe every disjoint contacting neighbor. Translation
    // equivariance lets each frozen frontier be expanded in its own frame.
    constexpr int capacity=12*128*128;
    auto key=[](Off p) {
        if(p[1]<-64||p[1]>=64||p[2]<-64||p[2]>=64)throw std::runtime_error("Pose limit");
        return (p[0]*128+p[2]+64)*128+p[1]+64;
    };
    std::array<char,capacity> forbidden{},seen{};
    for(auto p:touch[0])forbidden[key(p)]=1;
    for(int j=0;j<12;++j)for(auto [x,y]:shapes[0])for(auto [u,v]:shapes[j])forbidden[key({j,x-u,y-v})]=1;
    std::vector<Off> level=touch[0];
    std::ofstream file(output);
    for(int i=1;i<=4;++i) {
        std::sort(level.begin(),level.end(),[&](Off a,Off b){return key(a)<key(b);});
        for(auto p:level)file<<i<<' '<<p[0]<<' '<<p[1]<<' '<<p[2]<<'\n';
        std::cout<<i<<' '<<level.size()<<'\n';
        if(i==4)break;
        std::vector<Off> next;seen.fill(0);
        for(auto p:level)for(auto v:touch[p[0]]) {
            v[1]+=p[1];v[2]+=p[2];int k=key(v);
            if(!forbidden[k]&&!seen[k]){seen[k]=1;next.push_back(v);}
        }
        level.swap(next);
    }
}
// Keep the input row-major order (y, x) for all sliding AMO groups.
using RowMajor = std::pair<int,int>;
struct Formula {
    std::ofstream output;
    std::set<Cell> origin;
    std::map<RowMajor,std::vector<int>> covering;
    std::map<Cell,int> distances;
    int radius; bool adjacency,separation; long long clauses=0,required=0,amo=0,f4=0,f5=0,f6=0;
    Formula(const std::string& d,int r,bool a,bool b):output(d+"/model.cnf"),radius(r),adjacency(a),separation(b) {
        // Fixed-width header can be updated in place with the exact count.
        output<<std::string(72,' ')<<'\n';
        origin.insert(shapes[0].begin(),shapes[0].end());
        for(int i=1;i<int(poses.size());++i) {
            auto p=poses[i];
            for(auto [x,y]:shapes[p.o])covering[{y+p.y,x+p.x}].push_back(i);
        }
    }
    bool active(int x,int y) {
        auto [it,added]=distances.emplace(Cell{x,y},1000);
        if(added) for(auto [ox,oy]:origin)it->second=std::min(it->second,
                std::max({std::abs(x-ox),std::abs(y-oy),std::abs(x+y-ox-oy)}));
        return it->second<=radius;
    }
    void emit(std::vector<int>& v) {
        std::sort(v.begin(),v.end(),[](int a,int b){return std::abs(a)<std::abs(b);});
        for(int k:v)output<<k<<' ';
        output<<"0\n";++clauses;
    }
    void binary(int a,int b) {
        if(std::abs(b)<std::abs(a))std::swap(a,b);
        output<<a<<' '<<b<<" 0\n";++clauses;
    }
    void build() {
        for(auto& [xy,unused]:halo[0]) {
            auto [x,y]=xy;auto& vs=covering[{y,x}];std::vector<int> root;
            for(int v:vs)if(poses[v].level==1)root.push_back(v);
            emit(root);++required;
        }
        int aux=poses.size();
        for(auto& [yx,vs]:covering) {
            auto [y,x]=yx;int n=vs.size(); if(n<2)continue;
            bool keep=active(x,y);
            if(n<=20) {
                if(keep)for(int i=0;i<n;++i)for(int j=0;j<i;++j)binary(-vs[j],-vs[i]);
            } else {
                if(keep) {
                    binary(-vs[0],aux);
                    for(int i=1;i<n-1;++i) {
                        binary(-vs[i],aux+i);binary(-aux-i+1,aux+i);binary(-vs[i],-aux-i+1);
                    }
                    binary(-vs[n-1],-aux-n+2);
                }
                aux+=n-1;
            }
        }
        if(aux-1!=1327939)throw std::runtime_error("Frozen aux IDs disagree");
        amo=clauses-required;
        for(int i=1;i<int(poses.size());++i) {
            auto p=poses[i];bool included=false;
            for(auto [x,y]:shapes[p.o])if(active(x+p.x,y+p.y)){included=true;break;}
            if(adjacency&&p.level>1&&included) {
                std::vector<int> clause{-i};
                for(auto [o,x,y]:touch[p.o])if(int v=id(p.level-1,o,p.x+x,p.y+y))clause.push_back(v);
                emit(clause);++f4;
            }
            if(separation&&p.level>2&&included) {
                for(auto [o,x,y]:touch[p.o])for(int other=1;other<p.level-1;++other)
                    if(int v=id(other,o,p.x+x,p.y+y)){binary(-i,-v);++f5;}
            }
            if(p.level==4)continue;
            for(auto& [q,offsets]:halo[p.o]) {
                auto [x,y]=q;x+=p.x;y+=p.y;
                if(origin.count({x,y})||!active(x,y))continue;
                std::vector<int> clause{-i};
                for(auto [o,dx,dy]:offsets)for(int lev=std::max(1,p.level-1);lev<=p.level+1;++lev)
                    if(int v=id(lev,o,p.x+dx,p.y+dy))clause.push_back(v);
                emit(clause);++f6;
            }
        }
        output.seekp(0);output<<"p cnf "<<(aux-1)<<' '<<clauses;
        std::cout<<clauses<<" total / "<<required<<" root / "<<amo<<" AMO / "<<f4
                 <<" adjacency / "<<f5<<" separation / "<<f6<<" disjoint surrounds\n";
    }
};
int main(int argc,char** argv) {
    if(argc==4&&std::string(argv[1])=="--universe"){
        load(argv[2]);fast_universe(argv[3]);return 0;
    }
    if(argc!=6)return 2;
    load(argv[1]); Formula f(argv[2],std::stoi(argv[3]),bool(std::stoi(argv[4])),bool(std::stoi(argv[5]))); f.build();
}
