#include "geometry.h"

using Tiles = std::set<Point>;
struct Chart { int id; Shape s; std::vector<Motion> neighbors; };
struct Slide { int index; Point offset; };

std::vector<Chart> read_charts(const char *path) {
    std::ifstream f(path);
    std::vector<Chart> result;
    int id,count;
    while (f>>id>>count) {
        Chart chart{id,{},{}};
        for (int j=0,x,y;j<count;++j) { f>>x>>y; chart.s.emplace_back(x,y); }
        f>>count;
        for (int j=0;j<count;++j) {
            Motion m;
            for (auto& x : m) f>>x;
            chart.neighbors.push_back(m);
        }
        result.push_back(std::move(chart));
    }
    return result;
}

Shape void_at(const Tiles& occupied, Point seed) {
    if (occupied.count(seed)) return {};
    std::vector<Point> queue{seed};
    Tiles visited{seed};
    for (size_t i=0;i<queue.size();++i) {
        for (auto delta : steps(queue[i])) {
            Point next=add(queue[i],delta);
            if (occupied.count(next) || !visited.insert(next).second) continue;
            if (visited.size()>45) return {};
            queue.push_back(next);
        }
    }
    return queue;
}

bool surround(const Chart& chart,const Tiles& tile,const std::vector<Slide>& shifts,Tiles& occupied) {
    std::vector<Point> offsets(chart.neighbors.size());
    for (auto slide : shifts) offsets[slide.index]=slide.offset;
    for (size_t k=0;k<chart.neighbors.size();++k)
        for (auto cell : tile) {
            auto world=add(place(chart.neighbors[k],cell),offsets[k]);
            if(!occupied.insert(world).second)return false;
        }
    return true;
}

std::vector<Point> rim(const Tiles& s) {
    std::vector<Point> result;
    for(auto p:s)
        for(auto d:steps(p))if(!s.count(add(p,d))) {result.push_back(p);break;}
    return result;
}

int main(int argc,char **argv) {
    if(argc!=5)return 2;
    auto charts=read_charts(argv[1]);
    std::ofstream bank(argv[2]), origins(argv[3]);
    int trials=std::stoi(argv[4]);
    if(charts.empty()||!bank||!origins)return 2;
    std::mt19937 rng(638329);
    std::set<Shape> seen;
    long returned=0, shared=0, closed=0, vacant=0;
    for(const auto& chart:charts) {
        Tiles old(chart.s.begin(),chart.s.end()),control;
        if(!surround(chart,old,{},control))return 3;
        if(representations(void_at(control,*old.begin())).first!=representations(chart.s).first)return 4;
        for(int trial=0;trial<trials;++trial) {
            Tiles changed=old;
            std::vector<Point> deleted,inserted;
            const int ncut=1+rng()%std::min<size_t>(8,old.size()/3);
            for(int k=0;k<ncut;++k) {
                auto options=rim(changed);
                if(!deleted.empty() && rng()%2) {
                    std::vector<Point> nearby;
                    for(auto p:options)for(auto d:steps(deleted.back()))
                        if(add(deleted.back(),d)==p)nearby.push_back(p);
                    if(!nearby.empty())options=std::move(nearby);
                }
                auto p=options[rng()%options.size()];
                changed.erase(p);deleted.push_back(p);
            }
            const int nadd=trial%3==0 ? 1+(rng()%2) : 0;
            for(int k=0;k<nadd;++k) {
                Tiles space;
                for(auto p:changed)for(auto d:steps(p))if(!old.count(add(p,d))&&!changed.count(add(p,d)))space.insert(add(p,d));
                auto p=*std::next(space.begin(),rng()%space.size());
                changed.insert(p);inserted.push_back(p);
            }
            Shape edited(changed.begin(),changed.end());
            if(!solid(edited))continue;
            std::vector<Slide> slides;
            const int nslide=trial%4==0 ? 0 : 1+rng()%2;
            for(int k=0;k<nslide;++k) {
                int j=rng()%chart.neighbors.size();
                if(k && j==slides.front().index)j=(j+1)%chart.neighbors.size();
                slides.push_back({j,shifts[rng()%6]});
            }
            Tiles occupied;
            if(!surround(chart,changed,slides,occupied))continue;
            ++vacant;
            auto anchor=chart.s[rng()%chart.s.size()];
            Shape hole=void_at(occupied,anchor);
            if(hole.size()<19||!solid(hole))continue;
            ++closed;
            int original=0;
            for(auto p:hole)original+=old.count(p);
            if(original<8||size_t(original)==hole.size()&&hole.size()==old.size())continue;
            const auto [key,reps]=representations(hole); if(reps.empty())continue;
            if(!seen.insert(key).second)continue;
            const bool same=representations(edited).first==key;
            ++returned;shared+=same;
            bank<<returned<<" I?";
            for(auto [x,y]:reps)bank<<' '<<x<<' '<<y;
            bank<<'\n';
            origins<<returned<<' '<<chart.id<<' '<<original<<' '<<int(same)<<' '<<anchor.first<<' '<<anchor.second;
            for(auto [x,y]:deleted)origins<<" cut "<<x<<' '<<y;
            for(auto [x,y]:inserted)origins<<" add "<<x<<' '<<y;
            for(auto s:slides)origins<<" move "<<s.index<<' '<<s.offset.first<<' '<<s.offset.second;
            origins<<'\n';
        }
    }
    std::cerr<<"charts "<<charts.size()<<" trials/chart "<<trials<<" disjoint "<<vacant
             <<" enclosed in size band "<<closed<<" retained "<<returned<<" same tile "<<shared<<'\n';
}
