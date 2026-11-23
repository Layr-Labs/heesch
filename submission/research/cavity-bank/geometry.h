#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <random>
#include <set>
#include <sstream>
#include <utility>
#include <vector>
using Point=std::pair<int,int>;
using Shape=std::vector<Point>;
using Motion=std::array<int,6>;
Point add(Point a,Point b){return {a.first+b.first,a.second+b.second};}
int mod3(int x){return (x%3+3)%3;}
std::array<Point,3> steps(Point p){
    if(mod3(p.first)==0)return {{{1,1},{-2,1},{1,-2}}};
    return {{{-1,-1},{2,-1},{-1,2}}};
}
const std::array<Point,6> shifts={{{3,0},{0,3},{-3,3},{-3,0},{0,-3},{3,-3}}};
const std::array<Motion,12> syms={{{1,0,0,0,1,0},{-1,-1,0,1,0,0},{0,1,0,-1,-1,0},{1,0,0,-1,-1,0},{0,1,0,1,0,0},{-1,-1,0,0,1,0},{0,-1,1,-1,0,1},{-1,0,1,1,1,1},{1,1,1,0,-1,1},{1,1,1,-1,0,1},{-1,0,1,0,-1,1},{0,-1,1,1,1,1}}};
Point place(const Motion&m,Point p){auto [x,y]=p;return {m[0]*x+m[1]*y+m[2],m[3]*x+m[4]*y+m[5]};}
std::array<int,4> bounds(const Shape&s){int lo=10000,ro=-10000,bo=10000,to=-10000;for(auto [x,y]:s){lo=std::min(lo,x);ro=std::max(ro,x);bo=std::min(bo,y);to=std::max(to,y);}return {lo,ro,bo,to};}
std::pair<Shape,Shape> representations(const Shape&s){Shape key,best;int minspan=10000;
    for(auto m:syms){Shape q;for(auto p:s)q.push_back(place(m,p));auto [lo,ro,bo,to]=bounds(q);int span=ro-lo+to-bo+2;
        for(auto&[x,y]:q){x-=lo-mod3(lo);y-=bo-mod3(bo);}std::sort(q.begin(),q.end());
        if(key.empty()||q<key)key=q;if(span<minspan||(span==minspan&&q<best)){best=q;minspan=span;}}
    if(minspan>29)best.clear();return {key,best};}
bool solid(const Shape&s){std::set<Point> shape(s.begin(),s.end());
    if(shape.empty())return false;Shape stack={*shape.begin()};std::set<Point> reached(stack.begin(),stack.end());
    for(size_t i=0;i<stack.size();++i)for(auto d:steps(stack[i])){auto q=add(stack[i],d);if(shape.count(q)&&reached.insert(q).second)stack.push_back(q);}if(reached.size()!=shape.size())return false;
    // Every edge-neighbor vacancy must be able to reach the unbounded component.
    // Work one vacancy component at a time to avoid scanning a large filled box.
    auto [lo,ro,bo,to]=bounds(s);std::set<Point> exterior;
    for(auto p:s)for(auto d:steps(p)){auto q=add(p,d);if(shape.count(q)||exterior.count(q))continue;bool open=false;
        Shape queue={q}; std::set<Point> seen{q};
        for(size_t k=0;k<queue.size()&&!open;++k){auto here=queue[k];if(here.first<lo||here.first>ro||here.second<bo||here.second>to){open=true;break;}
            for(auto n:steps(here)){auto next=add(here,n);if(exterior.count(next)){open=true;break;}if(!shape.count(next)&&seen.insert(next).second)queue.push_back(next);}}
        if(!open)return false;exterior.insert(seen.begin(),seen.end());}
    return true;}
