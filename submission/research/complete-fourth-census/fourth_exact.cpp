#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <vector>
using Cell=std::pair<int,int>;
using Word=unsigned long long;
using Shape=std::vector<Cell>;
const std::array<Cell,6> dirs={{{1,0},{0,1},{-1,1},{-1,0},{0,-1},{1,-1}}};
struct Mask {std::vector<Word> data;};
struct Tile {Shape cells; Mask incompatible, hits;};
struct Domain {
  Shape inside, need, tile;
  int ncols,ntiles,xlo,xhi,ylo,yhi,W,H;
  std::vector<Tile> ts;std::vector<Mask> providers;std::vector<int> chosen;
  std::vector<unsigned char> base,filled,voids; std::vector<int> queue;
  std::vector<Word> covers;
  std::map<int,std::uint64_t> histogram;
  std::uint64_t completions=0,small_trapped=0,viable=0;
  int min_holes=1<<20;
  std::string dir;
  int location(Cell p){return (p.first-xlo)+(p.second-ylo)*W;}
  void inspect(){
    ++completions;filled=base;for(auto j:chosen)for(auto p:ts[j].cells)filled[location(p)]=1;
    voids=filled;queue.clear();queue.push_back(0);voids[0]=1;
    for(size_t k=0;k<queue.size();++k){int c=queue[k],x=c%W,y=c/W;for(auto[dx,dy]:dirs){int xx=x+dx,yy=y+dy,j=c+dx+W*dy;if(xx>=0&&xx<W&&yy>=0&&yy<H&&!voids[j]){voids[j]=1;queue.push_back(j);}}}
    int holes=0;bool small=false;
    for(int i=0;i<W*H;++i)if(!voids[i]){queue.clear();queue.push_back(i);voids[i]=1;for(size_t k=0;k<queue.size();++k){int c=queue[k];for(auto [dx,dy]:dirs){int j=c+dx+W*dy;if(!voids[j]){voids[j]=1;queue.push_back(j);}}}holes+=queue.size();small|=queue.size()<tile.size();}
    histogram[holes]++;small_trapped+=small;
    if(holes<min_holes){min_holes=holes;std::ofstream best(dir+"/best-complete.txt");best<<holes<<' '<<completions<<'\n';for(auto j:chosen)best<<j<<' ';best<<'\n';std::cout<<"lowest "<<holes<<" at "<<completions<<'\n'<<std::flush;}
    if(!small){++viable;std::ofstream f(dir+"/viable.txt",std::ios::app);f<<holes;for(auto j:chosen)f<<' '<<j;f<<'\n';}
  }
  void visit(const Mask& req,const Mask& free){
    int col=-1,min=100000;
    for(int w=0;w<req.data.size();++w){Word x=req.data[w];while(x){int bit=std::countr_zero(x);x&=x-1;int c=64*w+bit;int count=0;for(int k=0;k<free.data.size();++k)count+=std::popcount(providers[c].data[k]&free.data[k]);if(!count)return;if(count<min){min=count;col=c;}}}
    if(col<0){inspect();return;}
    for(int k=0;k<free.data.size();++k){Word choices=providers[col].data[k]&free.data[k];while(choices){int i=64*k+std::countr_zero(choices);choices&=choices-1;Mask a=req,b=free;for(int j=0;j<a.data.size();++j)a.data[j]&=~ts[i].hits.data[j];for(int j=0;j<b.data.size();++j)b.data[j]&=~ts[i].incompatible.data[j];chosen.push_back(i);visit(a,b);chosen.pop_back();}}
  }
  void run(std::ifstream& inp){
    auto shape=[&](){Shape s;int n;inp>>n;while(n--){int x,y;inp>>x>>y;s.emplace_back(x,y);}return s;};
    tile=shape();inside=shape();need=shape();ncols=need.size();inp>>ntiles;int wc=(ncols+63)/64,wt=(ntiles+63)/64;
    std::map<Cell,std::vector<int>> owner;std::map<Cell,int> idx;for(int i=0;i<ncols;i++)idx[need[i]]=i;
    providers.resize(ncols,Mask{std::vector<Word>(wt)}); xlo=ylo=999;xhi=yhi=-999;
    for(int i=0;i<ntiles;i++){Tile t{shape(),Mask{std::vector<Word>(wt)},Mask{std::vector<Word>(wc)}};for(auto p:t.cells){owner[p].push_back(i);auto[x,y]=p;xlo=std::min(xlo,x);xhi=std::max(xhi,x);ylo=std::min(ylo,y);yhi=std::max(yhi,y);if(idx.contains(p)){int j=idx[p];t.hits.data[j/64]|=Word(1)<<(j%64);providers[j].data[i/64]|=Word(1)<<(i%64);}}ts.push_back(std::move(t));}
    xlo-=2;ylo-=2;xhi+=2;yhi+=2;W=xhi-xlo+1;H=yhi-ylo+1;base.resize(W*H);for(auto p:inside)base[location(p)]=1;
    for(int i=0;i<ntiles;i++)for(auto p:ts[i].cells)for(auto j:owner[p])ts[i].incompatible.data[j/64]|=Word(1)<<(j%64);
    Mask req{std::vector<Word>(wc)},free{std::vector<Word>(wt)};for(int i=0;i<ncols;i++)req.data[i/64]|=Word(1)<<(i%64);for(int i=0;i<ntiles;i++)free.data[i/64]|=Word(1)<<(i%64);visit(req,free);
    std::ofstream res(dir+"/counts.tsv");res<<"raw_placements "<<completions<<"\nsmall_trapped "<<small_trapped<<"\nremaining "<<viable<<'\n';for(auto [h,n]:histogram)res<<h<<' '<<n<<'\n';std::cout<<"EXHAUSTED "<<completions<<" with "<<small_trapped<<" immediately excluding a fifth; remaining "<<viable<<'\n';
  }
};
int main(int argc,char**argv){std::ifstream f(argv[1]);Domain d;d.dir=argv[2];d.run(f);}
