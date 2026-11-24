// Replace a disjoint matching of donor vertices by triangular three-cell
// motifs. Their internal and external bonds are embedded jointly.
#define SPLIT_LIBRARY
#include "generate.cpp"
struct Lift {
    int u,v,stencil;
    int masks[3];
};
int main(int argc,char**argv){
    if(argc!=6)return 1;
    auto rows=load(argv[1]);
    std::filesystem::path dest(argv[2]);std::filesystem::create_directories(dest);
    int schedule=std::stoi(argv[3]),nodecap=std::stoi(argv[4]),solcap=std::stoi(argv[5]);
    std::ofstream bank(dest/"bank.tsv"),cond(dest/"systems.tsv"),trace(dest/"routes.tsv");
    std::set<Shape> seen;
    for(auto&r:rows)seen.insert(norm(r.cells));
    std::mt19937 rng(548773);int systems=0,outlines=0;
    for(auto& r:rows){
        int n=r.cells.size();
        if(n<15||n>=20)continue;
        Source input(r);
        std::vector<Edge> edges(input.edges.begin(),input.edges.end());
        std::set<std::set<Edge>> visited;
        for(int trial=0;trial<schedule;++trial){
            int count=std::max(1,18-n)+trial%(21-n-std::max(1,18-n));
            std::shuffle(edges.begin(),edges.end(),rng);
            std::set<int> used;
            auto model=input.edges;
            std::vector<Lift> lifts;
            for(auto [u,v]:edges){
                if(lifts.size()==count)break;
                if(used.contains(u)||used.contains(v))continue;
                // All contacts of the two-cell core are expressed in a
                // single 10-edge rim, in counter-clockwise boundary order.
                Shape core{r.cells[u],r.cells[v]};
                auto loop=outline(core);
                if(loop.size()!=10)throw std::runtime_error("domino boundary");
                std::vector<std::pair<int,int>> neighbors;
                for(int j=0;j<10;++j){
                    auto x=loop[j],y=loop[(j+1)%10];
                    // Get the other owner of this exact directed unit edge.
                    int current=-1,other=-1;
                    for(auto z:{u,v}){
                        auto [a,b]=r.cells[z];Point center{3*a,a+2*b};
                        for(int k=0;k<6;++k)if(add(center,corner[k])==x && add(center,corner[(k+1)%6])==y){
                            current=z;
                            auto it=input.index.find(add(r.cells[z],dirs[k]));
                            if(it!=input.index.end())other=it->second;
                        }
                    }
                    if(current<0)throw std::runtime_error("unregistered boundary");
                    neighbors.emplace_back(current,other);
                }
                bool touch=false;
                for(auto [own,q]:neighbors)if(used.contains(q))touch=true;
                if(touch)continue;
                // Split the ten perimeter incidences into three contiguous
                // sectors. A joint may couple the neighboring sectors to
                // the same exterior cell; new side contacts remain free.
                int start=rng()%10, a=2+rng()%3,b=2+rng()%3;
                int w=n+lifts.size();
                int masks[3]{};
                std::array<int,3> core_id={u,v,w};
                int joints[3]={start,(start+a)%10,(start+a+b)%10};
                for(int step=0;step<10;++step){
                    int k=(start+step)%10,sector=step<a?0:step<a+b?1:2;
                    masks[sector]|=1<<k;
                    if(k==joints[sector] && rng()%3==0)masks[(sector+2)%3]|=1<<k;
                }
                for(auto [own,q]:neighbors)if(q>=0)model.erase(unordered_edge(own,q));
                for(int i=0;i<3;++i){
                    model.insert(unordered_edge(core_id[i],core_id[(i+1)%3]));
                    for(int k=0;k<10;++k)if((masks[i]&(1<<k)) && neighbors[k].second>=0)
                        model.insert(unordered_edge(core_id[i],neighbors[k].second));
                }
                lifts.push_back({u,v,start,{masks[0],masks[1],masks[2]}});
                used.insert(u);used.insert(v);
            }
            if(lifts.size()!=count||!visited.insert(model).second)continue;
            Graph graph(n+count,model);
            if(std::any_of(graph.neighbors.begin(),graph.neighbors.end(),[](auto&neigh){return neigh.size()>6;}))continue;
            Geometry geo(graph,nodecap,solcap);++systems;int fresh=0;
            geo.draw([&](const Shape& at){
                auto shape=norm(at);
                if(seen.contains(shape)||outline(shape).empty())return;
                int mx=0,my=0;for(auto [x,y]:shape){mx=std::max(mx,x);my=std::max(my,y);}
                if(mx+my+2>29)return;
                seen.insert(shape);++fresh;bank<<++outlines<<" H?";
                for(auto [x,y]:shape)bank<<' '<<x<<' '<<y;
                bank<<'\n';trace<<outlines<<' '<<systems;
                for(auto [x,y]:at)trace<<' '<<x<<' '<<y;
                trace<<'\n';
            });
            cond<<systems<<' '<<r.id<<' '<<trial<<' '<<geo.nodes<<' '<<geo.solutions<<' '<<fresh<<' '<<geo.stopped;
            for(auto l:lifts)cond<<' '<<l.u<<','<<l.v<<','<<l.stencil<<','<<l.masks[0]<<','<<l.masks[1]<<','<<l.masks[2];
            cond<<'\n';
        }
        std::cerr<<r.id<<' '<<systems<<' '<<outlines<<'\n';
    }
    std::ofstream info(dest/"summary.json");
    info<<"{\"counts\":{\"unique\":"<<outlines<<"},\"systems\":"<<systems<<",\"trials_per_donor\":"<<schedule
        <<",\"node_cap\":"<<nodecap<<",\"embedding_cap\":"<<solcap<<"}\n";
    std::cout<<outlines<<" unique disks\n";
}
