// Transplant a directed boundary word without moving either endpoint.
#define main ringfilter_main
#include "../alternate-lane/ringfilter.cpp"
#undef main
#include <fstream>
#include <random>
#include <unordered_map>
using Shape=std::vector<Point>;
const std::array<Point,6> corner={{{2,0},{1,1},{-1,1},{-2,0},{-1,-1},{1,-1}}};
const std::array<Point,6> dirs={{{1,0},{0,1},{-1,1},{-1,0},{0,-1},{1,-1}}};
const auto transforms=orientations(true);
Point add(Point a,Point b){return {a.first+b.first,a.second+b.second};}
Point sub(Point a,Point b){return {a.first-b.first,a.second-b.second};}
int area(const Shape&s){int twice=0;for(int i=0;i<s.size();i++){auto [x,y]=s[i];auto [u,v]=s[(i+1)%s.size()];twice+=x*v-y*u;}return twice;}
Shape outline(const Shape&s){std::set<std::pair<Point,Point>> edges;for(auto [x,y]:s){Point c{3*x,x+2*y};for(int j=0;j<6;j++){auto u=add(c,corner[j]),v=add(c,corner[(j+1)%6]);if(!edges.erase({v,u}))edges.insert({u,v});}}std::map<Point,Point> links;for(auto [u,v]:edges)links[u]=v;Shape loop;auto cursor=links.begin()->first;do{loop.push_back(cursor);cursor=links.at(cursor);}while(cursor!=loop.front()&&loop.size()<=edges.size());if(loop.size()!=edges.size())return {};return loop;}
Shape norm(const Shape&s){Shape best;for(auto const&m:transforms){Shape tmp;int xmin=500,ymin=500;for(auto p:s){auto q=transform(m,p);tmp.push_back(q);xmin=std::min(xmin,q.first);ymin=std::min(ymin,q.second);}for(auto &[x,y]:tmp){x-=xmin;y-=ymin;}std::sort(tmp.begin(),tmp.end());if(best.empty()||tmp<best)best=tmp;}return best;}
struct Row{std::string id;Shape cells;};
std::vector<Row> load(const char*path){std::ifstream f(path);std::vector<Row> rows;std::string line;while(getline(f,line)){Row r;std::istringstream ss(line);ss>>r.id;int x,y;while(ss>>x>>y)r.cells.emplace_back(x,y);rows.push_back(r);}return rows;}
// A simple closed honeycomb edge loop has one connected interior. Cell centers
// never lie on an edge, so a horizontal ray classifies them without ties.
Shape inside(const Shape&poly){int xmin=999,xmax=-999,ymin=999,ymax=-999;for(auto [x,y]:poly){xmin=std::min(xmin,x);xmax=std::max(xmax,x);ymin=std::min(ymin,y);ymax=std::max(ymax,y);}Shape out;for(int u=xmin/3-2;u<=xmax/3+2;u++)for(int v=(ymin-u)/2-2;v<=(ymax-u)/2+2;v++){int x=3*u,y=u+2*v;bool in=false;for(int i=0;i<poly.size();++i){auto [ax,ay]=poly[i];auto [bx,by]=poly[(i+1)%poly.size()];if((ay>y)!=(by>y) && ((ay<by)?(ax*(by-ay)+(bx-ax)*(y-ay)>x*(by-ay)):(ax*(by-ay)+(bx-ax)*(y-ay)<x*(by-ay))))in=!in;}if(in)out.emplace_back(u,v);}return out;}
struct Arc{Shape vs;std::string donor;int start,orientation;};
using Group=std::tuple<int,int,int>; // displacement and honeycomb start-vertex type
int side(Point p){return (p.first%3+3)%3;}
#ifndef ARCS_LIBRARY
int main(int argc,char**argv){if(argc!=6)return 2;auto parents=load(argv[1]);auto donors=load(argv[2]);std::ofstream shapes(argv[3]),origin(argv[4]);int cap=std::stoi(argv[5]);std::mt19937 rng(181855);
 std::map<Group,std::map<Shape,Arc>> dictionary;for(auto&r:donors)for(int si=0;si<12;si++){Shape s;for(auto p:r.cells)s.push_back(transform(transforms[si],p));auto loop=outline(s);for(int start=0;start<loop.size();start++){auto anchor=loop[start];Shape path{{0,0}};for(int len=1;len<=24 && len<loop.size()-4;len++){path.push_back(sub(loop[(start+len)%loop.size()],anchor));if(len<4)continue;auto [x,y]=path.back();auto &mp=dictionary[{x,y,side(anchor)}];if(!mp.count(path))mp.emplace(path,Arc{path,r.id,start,si});}}}
 size_t entries=0;for(auto &[g,d]:dictionary)entries+=d.size();std::cerr<<"dictionary "<<entries<<" words across "<<dictionary.size()<<" endpoints\n";
 std::set<Shape> done;int id=0;for(auto&r:parents){auto loop=outline(r.cells);for(int start=0;start<loop.size();start++)for(int len=4;len<=22&&len<loop.size()-5;len++){Shape rest;for(int i=len;i<loop.size();i++)rest.push_back(loop[(start+i)%loop.size()]);Point a=loop[start], delta=sub(rest.front(),a);auto it=dictionary.find({delta.first,delta.second,side(a)});if(it==dictionary.end())continue;auto& mp=it->second;std::vector<const Arc*> options;for(auto &[k,w]:mp)options.push_back(&w);if(options.size()>cap){std::shuffle(options.begin(),options.end(),rng);options.resize(cap);}std::set<Point> forbidden(rest.begin(),rest.end());for(auto*o:options){Shape path;bool collision=false;for(int i=0;i<o->vs.size()-1;i++){auto q=add(a,o->vs[i]);if(forbidden.count(q)){collision=true;break;}path.push_back(q);}if(collision)continue;path.insert(path.end(),rest.begin(),rest.end());int ar=area(path);if(ar%12||ar<17*12||ar>20*12)continue;auto shape=inside(path);if(shape.size()!=ar/12)continue;int change=0;for(auto p:shape)if(std::find(r.cells.begin(),r.cells.end(),p)==r.cells.end())change++;if(change<2||change>11)continue;Shape key=norm(shape);if(!done.insert(key).second)continue;++id;shapes<<id<<" H?";for(auto [x,y]:key)shapes<<' '<<x<<' '<<y;shapes<<'\n';origin<<id<<' '<<r.id<<' '<<start<<' '<<len<<' '<<o->donor<<' '<<o->orientation<<' '<<o->start<<' '<<o->vs.size()-1<<' '<<change<<'\n';}}
 shapes.flush();origin.flush();std::cerr<<r.id<<' '<<id<<'\n';} }

#endif
