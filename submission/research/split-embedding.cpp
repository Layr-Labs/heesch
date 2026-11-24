// Replace selected cells of a finite donor by adjacent pairs, then draw the
// resulting graph again on the triangular lattice of hex centers.
#define ARCS_LIBRARY
#include "../ribbon-word/arcs.cpp"
#include <filesystem>
#include <numeric>

using Edge = std::pair<int,int>;
struct Split {
    int vertex, mask, shared;
};
struct Graph {
    std::vector<std::vector<int>> neighbors;
    std::vector<std::vector<int>> distance;
    explicit Graph(int n,const std::set<Edge>& edges): neighbors(n), distance(n,std::vector<int>(n,100)) {
        for(auto [i,j]:edges){neighbors[i].push_back(j);neighbors[j].push_back(i);}
        for(int i=0;i<n;++i){
            distance[i][i]=0;
            for(int j:neighbors[i])distance[i][j]=1;
        }
        for(int k=0;k<n;++k)for(int i=0;i<n;++i)for(int j=0;j<n;++j)
            distance[i][j]=std::min(distance[i][j],distance[i][k]+distance[k][j]);
    }
};
int separation(Point a,Point b){
    auto [x,y]=sub(a,b);
    return std::max({std::abs(x),std::abs(y),std::abs(x+y)});
}
struct Geometry {
    const Graph& graph;
    Shape at;
    std::vector<bool> assigned;
    std::set<Point> used;
    int nodes=0,solutions=0,node_cap,solution_cap;
    bool stopped=false;
    Geometry(const Graph& graph,int node_cap,int solution_cap):
        graph(graph),at(graph.neighbors.size()),assigned(at.size()),node_cap(node_cap),solution_cap(solution_cap){}
    void put(int i,Point p){assigned[i]=true;at[i]=p;used.insert(p);}
    void pop(int i){assigned[i]=false;used.erase(at[i]);}
    Shape choices(int i) const {
        int anchor=-1;
        for(int j:graph.neighbors[i])if(assigned[j]){anchor=j;break;}
        if(anchor<0)return {};
        Shape found;
        for(auto d:dirs){
            auto p=add(at[anchor],d);
            if(used.contains(p))continue;
            bool valid=true;
            for(int j=0;j<at.size();++j)if(assigned[j] && separation(at[j],p)>graph.distance[i][j]){
                valid=false;break;
            }
            if(valid)found.push_back(p);
        }
        return found;
    }
    template<class Emit>void search(int remaining,Emit& emit){
        if(nodes++>=node_cap || solutions>=solution_cap){stopped=true;return;}
        if(!remaining){++solutions;emit(at);return;}
        int best=-1,weight=100;
        Shape opts;
        for(int i=0;i<assigned.size();++i)if(!assigned[i]){
            int placed=0;
            for(int j:graph.neighbors[i])placed+=assigned[j];
            if(!placed)continue;
            auto available=choices(i);
            if(available.empty())return;
            int measure=int(available.size())*10-int(graph.neighbors[i].size());
            if(measure<weight){best=i;weight=measure;opts=available;}
        }
        for(auto p:opts){
            put(best,p);search(remaining-1,emit);pop(best);
            if(stopped)return;
        }
    }
    template<class Emit>void draw(Emit emit){
        int first=0;
        for(int i=1;i<at.size();++i)if(graph.neighbors[i].size()>graph.neighbors[first].size())first=i;
        int second=graph.neighbors[first].front();
        for(int v:graph.neighbors[first])if(graph.neighbors[v].size()>graph.neighbors[second].size())second=v;
        put(first,{0,0});put(second,{1,0});search(at.size()-2,emit);
    }
};
Edge unordered_edge(int i,int j){return {std::min(i,j),std::max(i,j)};}
struct Source {
    const Row& row;
    std::map<Point,int> index;
    std::set<Edge> edges;
    std::vector<std::vector<Split>> options;
    explicit Source(const Row& row):row(row),options(row.cells.size()){
        int n=row.cells.size();
        for(int i=0;i<n;++i)index[row.cells[i]]=i;
        for(int i=0;i<n;++i){
            int link=0;
            for(int k=0;k<6;++k){
                auto it=index.find(add(row.cells[i],dirs[k]));
                if(it!=index.end()){link|=1<<k;edges.insert(unordered_edge(i,it->second));}
            }
            std::set<std::pair<int,int>> done;
            for(int start=0;start<6;++start)for(int len=1;len<=5;++len){
                int arc=0;
                for(int k=0;k<len;++k)arc|=1<<((start+k)%6);
                int center=arc&link,other=link^center;
                if(!center||!other)continue;
                // Link neighbors adjacent to the cut in cyclic order may keep both incident bonds.
                int boundaries=(1<<start)|(1<<((start+len-1)%6))|(1<<((start+5)%6))|(1<<((start+len)%6));
                int shared_options=link&boundaries;
                for(int sh=shared_options;;sh=(sh-1)&shared_options){
                    int one=other|sh, two=center|sh;
                    if(one<two && std::popcount(static_cast<unsigned>(one))<=5
                               && std::popcount(static_cast<unsigned>(two))<=5
                               && std::popcount(static_cast<unsigned>(sh))<=2 && done.insert({one,two}).second)
                        options[i].push_back({i,two,sh});
                    if(!sh)break;
                }
            }
        }
    }
    std::set<Edge> building(const std::vector<Split>& split) const{
        auto ret=edges;
        for(int j=0;j<split.size();++j){
            auto [v,m,s]=split[j];
            int w=row.cells.size()+j;
            ret.insert(unordered_edge(v,w));
            for(int k=0;k<6;++k)if(m&(1<<k)){
                int u=index.at(add(row.cells[v],dirs[k]));
                if(!(s&(1<<k)))ret.erase(unordered_edge(v,u));
                ret.insert(unordered_edge(u,w));
            }
        }
        return ret;
    }
};
#ifndef SPLIT_LIBRARY
int main(int argc,char** argv){
    if(argc!=6)return 1;
    auto rows=load(argv[1]);
    std::filesystem::path out(argv[2]);std::filesystem::create_directories(out);
    int schedule=std::stoi(argv[3]),nodecap=std::stoi(argv[4]),solcap=std::stoi(argv[5]);
    std::ofstream bank(out/"bank.tsv"),conditions(out/"systems.tsv"),routes(out/"routes.tsv");
    std::set<Shape> seen;
    for(auto& r:rows)seen.insert(norm(r.cells));
    std::mt19937 rng(1237481);
    int configs=0,total=0;
    for(auto& row:rows){
        const int n=row.cells.size();
        if(n<15||n>=20)continue;
        Source source(row);std::set<std::set<Edge>> tested;
        for(int trial=0;trial<schedule;++trial){
            int count=std::max(1,18-n)+trial%(21-n-std::max(1,18-n));
            std::vector<int> queue(n);std::iota(queue.begin(),queue.end(),0);std::shuffle(queue.begin(),queue.end(),rng);
            std::vector<Split> split;
            for(auto v:queue){
                if(split.size()==count)break;
                if(source.options[v].empty())continue;
                if(std::any_of(split.begin(),split.end(),[&](auto s){return source.edges.contains(unordered_edge(v,s.vertex));}))continue;
                const auto& list=source.options[v];
                split.push_back(list[rng()%list.size()]);
            }
            if(split.size()!=count)continue;
            std::sort(split.begin(),split.end(),[](auto x,auto y){return x.vertex<y.vertex;});
            auto edges=source.building(split);
            if(!tested.insert(edges).second)continue;
            Graph graph(n+count,edges);Geometry geometry(graph,nodecap,solcap);
            ++configs;int wins=0;
            geometry.draw([&](const Shape& cells){
                auto key=norm(cells);
                if(seen.contains(key)||outline(key).empty())return;
                int xmax=0,ymax=0;
                for(auto [x,y]:key){xmax=std::max(xmax,x);ymax=std::max(ymax,y);}
                if(xmax+ymax+2>29)return;
                ++wins;++total;seen.insert(key);
                bank<<total<<" H?";
                for(auto [x,y]:key)bank<<' '<<x<<' '<<y;
                bank<<'\n';
                routes<<total<<' '<<configs;
                for(auto [x,y]:cells)routes<<' '<<x<<' '<<y;
                routes<<'\n';
            });
            conditions<<configs<<' '<<row.id<<' '<<trial<<' '<<geometry.nodes<<' '<<geometry.solutions
                      <<' '<<wins<<' '<<geometry.stopped;
            for(auto [v,m,s]:split)conditions<<' '<<v<<','<<m<<','<<s;
            conditions<<'\n';
        }
        std::cerr<<row.id<<' '<<configs<<" systems "<<total<<" distinct disk outlines\n";
    }
    std::ofstream meta(out/"summary.json");
    meta<<"{\"counts\":{\"unique\":"<<total<<"},\"systems\":"<<configs<<",\"trials_per_donor\":"<<schedule
        <<",\"node_cap\":"<<nodecap<<",\"embedding_cap\":"<<solcap<<"}\n";
    std::cout<<total<<" unique candidates\n";
}
#endif
