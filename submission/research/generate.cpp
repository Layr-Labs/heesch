// Bicrystal: join two periodic arrays of rectangular square-grid tiles at a horizontal interface.
// Coalesced group registrations are independently shifted, leaving a small grain-boundary defect.
// Solve for a new common outline whose k placements miss just one to three quotient cells.
#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <tuple>
#include <utility>
#include <vector>
using Pt=std::pair<int,int>;using Shape=std::vector<Pt>;using Pose=std::array<int,6>;using Bits=__uint128_t;
Pt apply(Pose m,Pt p){auto [a,b,c,d,e,f]=m;auto [x,y]=p;return {a*x+b*y+c,d*x+e*y+f};}
const std::array<Pose,8> ori={{{1,0,0,0,1,0},{0,-1,0,1,0,0},{-1,0,0,0,-1,0},{0,1,0,-1,0,0},{-1,0,0,0,1,0},{1,0,0,0,-1,0},{0,1,0,1,0,0},{0,-1,0,-1,0,0}}};const std::array<Pt,4> D={{{1,0},{-1,0},{0,1},{0,-1}}};
Pt add(Pt p,Pt q){return{p.first+q.first,p.second+q.second};}int mod(int a,int n){return(a%n+n)%n;}
Shape norm(Shape s){Shape best;for(auto m:ori){Shape t;int x=999,y=999;for(auto p:s){auto q=apply(m,p);x=std::min(x,q.first);y=std::min(y,q.second);t.push_back(q);}for(auto&[a,b]:t){a-=x;b-=y;}std::sort(t.begin(),t.end());if(best.empty()||t<best)best=t;}return best;}
Pose registered(int i,int x,int y,int w,int h){auto m=ori[i];int xmin=500,ymin=500;for(auto p:Shape{{0,0},{w-1,0},{0,h-1},{w-1,h-1}}){auto [u,v]=apply(m,p);xmin=std::min(xmin,u);ymin=std::min(ymin,v);}m[2]=x-xmin;m[5]=y-ymin;return m;}
int pop(Bits a){return std::popcount(uint64_t(a))+std::popcount(uint64_t(a>>64));}int bit(Bits a){return uint64_t(a)?std::countr_zero(uint64_t(a)):64+std::countr_zero(uint64_t(a>>64));}int first(Bits a){return bit(a);}
bool solid(const Shape&s){std::set<Pt> base(s.begin(),s.end());Shape queue={s[0]};std::set<Pt> seen(queue.begin(),queue.end());int xmin=100,xmax=-100,ymin=100,ymax=-100;for(auto[x,y]:s){xmin=std::min(xmin,x);xmax=std::max(xmax,x);ymin=std::min(ymin,y);ymax=std::max(ymax,y);}for(size_t i=0;i<queue.size();i++)for(auto d:D){auto p=add(queue[i],d);if(base.count(p)&&seen.insert(p).second)queue.push_back(p);}if(seen.size()!=s.size())return false;queue={{xmin-1,ymin-1}};seen={queue.front()};for(size_t i=0;i<queue.size();i++)for(auto d:D){auto p=add(queue[i],d);auto [x,y]=p;if(x>=xmin-1&&x<=xmax+1&&y>=ymin-1&&y<=ymax+1&&!base.count(p)&&seen.insert(p).second)queue.push_back(p);}return int(seen.size()+s.size())==(xmax-xmin+3)*(ymax-ymin+3);}
struct Problem {int n,k,N,A,B,C,limit;std::vector<Pose> poses;Shape env;std::vector<Bits> images,bycell;std::mt19937 &rng;std::vector<Shape> results;int nodes=0;
    int residue(Pt p)const{auto[x,y]=p;int yr=mod(y,C);return yr*A+mod(x-B*((y-yr)/C),A);}
    void dfs(Bits available,Bits covered,Bits skip,Bits selected,int maxout){if(++nodes>limit||int(results.size())>=maxout)return;int num=pop(selected),vac=N-n*k;if(num==n){Shape child;while(selected){int i=bit(selected);selected&=selected-1;child.push_back(env[i]);}if(solid(child))results.push_back(child);return;}if(pop(available)<n-num)return;Bits best=0;int goal=-1,bestn=200;for(int site=0;site<N;site++)if(!((covered|skip)>>site&1)){Bits v=available&bycell[site];int nv=pop(v);if(nv<bestn||(nv==bestn&&(rng()&15)==0)){bestn=nv;goal=site;best=v;}}
        if(goal<0)return;while(best){int i=bit(best);best&=best-1;Bits keep=available;Bits img=images[i];while(img){int j=bit(img);img&=img-1;keep&=~bycell[j];}dfs(keep,covered|images[i],skip,selected|(Bits(1)<<i),maxout);if(nodes>limit||int(results.size())>=maxout)return;}
        if(pop(skip)<vac)dfs(available&~bycell[goal],covered,skip|(Bits(1)<<goal),selected,maxout);
    }
    void run(int w,int h,int maxout){std::vector<std::pair<Pt,Bits>>opts;for(int x=-2;x<=w+1;x++)for(int y=-2;y<=h+1;y++){Bits occ=0;for(auto m:poses)occ|=Bits(1)<<residue(apply(m,{x,y}));if(pop(occ)==k)opts.emplace_back(Pt{x,y},occ);}std::shuffle(opts.begin(),opts.end(),rng);bycell.resize(N);for(auto[p,oc]:opts){int i=env.size();env.push_back(p);images.push_back(oc);for(int j=0;j<N;j++)if(oc>>j&1)bycell[j]|=Bits(1)<<i;}if(env.size()>=128)return;dfs((Bits(1)<<env.size())-1,0,0,0,maxout);}
};
int main(int argc,char**argv){if(argc!=6)return 2;std::ofstream bank(argv[1]),route(argv[2]),diag(argv[3]);int trials=atoi(argv[4]);std::mt19937 rng(atoi(argv[5]));auto rnd=[&](int n){return int(rng()%n);};std::set<Shape>seen;std::map<std::pair<int,int>,int> counts;int templates=0,solved=0,tnodes=0;
    // Independent rows may use their own rotational/reflection phase. To keep 128-bit exact masks bounded,
    // designs use 4–6 placements and base rectangles of area 16–20.
    for(int trial=0;trial<trials;trial++){int w=4+rnd(2),h=4;int cols=2+rnd(2),rows=2,k=cols*rows,baseA=w*cols,baseC=h*rows;int n=w*h-rnd(2);int A=baseA,B=rnd(5)-2,C=baseC,N=A*C,vac=N-k*n;int mode=rnd(4);
        // Twist a nearly rectangular lattice by modifying one transverse span; vacancy count follows the determinant.
        if(mode==1){A=baseA-1;C=baseC+1;}if(mode==2){A=baseA+1;C=baseC-1;}if(mode==3){A=baseA+2;C=baseC-1;}N=A*C;vac=N-k*n;if(vac<1||vac>6||N>=128||n<16||n>20)continue;
        std::vector<Pose>poses;int lower=rnd(w),shiftx=rnd(3)-1,shifty=rnd(3)-1;int hi[4]={0,2,4,5},lo[4]={0,2,4,5};if(w==h){for(int j=0;j<4;j++)lo[j]=2*j+1;}
        for(int y=0;y<rows;y++)for(int x=0;x<cols;x++){int g=y?lo[rnd(4)]:hi[rnd(4)];if(!x&&!y)g=0;int px=x*w+(y?lower:0),py=y*h;if(y&&x>=1){px+=shiftx;py+=shifty;}poses.push_back(registered(g,px,py,w,h));}
        templates++;Problem prob{n,k,N,A,B,C,1800,poses,{},{},{},rng,{}};prob.run(w,h,12);tnodes+=prob.nodes;if(!prob.results.empty())solved++;diag<<trial<<' '<<n<<' '<<k<<' '<<A<<' '<<B<<' '<<C<<' '<<vac<<' '<<prob.nodes<<' '<<prob.results.size()<<'\n';for(auto&s:prob.results){Shape key=norm(s);if(!seen.insert(key).second)continue;int id=seen.size();bank<<id<<" O?";for(auto[x,y]:key)bank<<' '<<x<<' '<<y;bank<<'\n';route<<id<<' '<<trial<<' '<<n<<' '<<A<<' '<<B<<' '<<C<<' '<<vac<<" poses";for(auto m:poses)route<<' '<<m[0]<<','<<m[1]<<','<<m[2]<<','<<m[3]<<','<<m[4]<<','<<m[5];route<<" outline";for(auto[x,y]:s)route<<' '<<x<<','<<y;route<<'\n';counts[{k,vac}]++;}}
    std::cerr<<"trials "<<trials<<" templates "<<templates<<" solved "<<solved<<" outlines "<<seen.size()<<" nodes "<<tnodes<<'\n';for(auto [pair,n]:counts)std::cerr<<pair.first<<','<<pair.second<<' '<<n<<'\n';}
