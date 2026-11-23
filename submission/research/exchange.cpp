// Exchange occupied cells of a grain-boundary tile while simultaneously requiring an unlabeled corona.
#define main original_generator
#include "generate.cpp"
#undef main
#include <sstream>
#include <string>
#include <bitset>
using Board = std::bitset<1024>;
using Small = uint64_t;
std::vector<std::string> split(std::string s,char delim){std::istringstream stream(s);std::vector<std::string> out;std::string token;while(getline(stream,token,delim))out.push_back(token);return out;}
std::vector<int> numbers(std::string s,char delim){std::vector<int> a;for(auto i:split(s,delim))a.push_back(stoi(i));return a;}
std::vector<Pose> motions(std::string s){std::vector<Pose> out;for(auto m:split(s,' ')){auto a=numbers(m,',');Pose p;std::copy(a.begin(),a.end(),p.begin());out.push_back(p);}return out;}
Shape shape(std::string s){Shape a;for(auto i:split(s,' ')){auto xy=numbers(i,',');a.emplace_back(xy[0],xy[1]);}std::sort(a.begin(),a.end());return a;}
int pos(Pt p){int x=p.first+12,y=p.second+12;return x<0||x>=32||y<0||y>=32?-1:y*32+x;}
Board occupy(const Shape&s,Pose t){Board b;for(auto p:s){int i=pos(apply(t,p));if(i<0)return {};b.set(i);}return b;}
int idx(Small x){return std::countr_zero(x);}
struct Star {
 const Shape& poly; Shape halo; Board central; std::vector<Pose> poses;std::vector<Board> tile;std::vector<Small> cover;std::vector<std::vector<int>> at;std::vector<int> selected;long nodes=0;
 Star(const Shape&s,const std::vector<Pose>&atlas):poly(s),central(occupy(s,ori[0])){
  std::set<Pt> h;for(auto [x,y]:s)for(int dx=-1;dx<=1;dx++)for(int dy=-1;dy<=1;dy++){Pt q{x+dx,y+dy};if(!central.test(pos(q)))h.insert(q);}halo.assign(h.begin(),h.end());if(halo.size()>=64)return;at.resize(halo.size());
  std::set<Board,decltype([](const Board&a,const Board&b){for(auto i=0;i<1024;i++)if(a[i]!=b[i])return a[i]<b[i];return false;})>seen;
  for(auto t:atlas){Board b=occupy(s,t);if(b.none()||(central&b).any())continue;Small mask=0;for(int i=0;i<int(halo.size());i++)if(b[pos(halo[i])])mask|=Small(1)<<i;if(!mask||!seen.insert(b).second)continue;for(auto m=mask;m;m&=m-1)at[idx(m)].push_back(poses.size());poses.push_back(t);tile.push_back(b);cover.push_back(mask);}
 }
 bool search(Small required,Board taken){if(!required)return true;if(++nodes>500)return false;int smallest=999,id=-1;for(auto m=required;m;m&=m-1){int j=idx(m),n=0;for(int i:at[j])if(!(tile[i]&taken).any())n++;if(n==0)return false;if(n<smallest){smallest=n;id=j;}}for(int i:at[id])if(!(tile[i]&taken).any()){selected.push_back(i);if(search(required&~cover[i],taken|tile[i]))return true;selected.pop_back();}return false;}
 bool run(){return !at.empty()&&search((Small(1)<<halo.size())-1,central);}
};
#ifndef ONLY_ATLAS
int main(int argc,char**argv){if(argc!=7&&argc!=8)return 2;int maxExtra=argc==8?atoi(argv[7]):2;std::ifstream in(argv[1]);if(!in)return 3;std::ofstream bank(argv[2]),routes(argv[3]),log(argv[4]);int maximum=atoi(argv[5]);std::mt19937 rng(atoi(argv[6]));std::string line;std::set<Shape> keys;long attempts=0,disks=0,passed=0;
 while(getline(in,line)){
  auto cols=split(line,'|');auto id=cols[0];auto abc=numbers(cols[1],' ');auto par=shape(cols[2]);auto quotient=motions(cols[3]),first=motions(cols[4]),atlas=motions(cols[5]);int A=abc[0],B=abc[1],C=abc[2];int oldn=par.size(), gain=20-oldn;if(gain!=0 && gain!=1)return 5;auto res=[&](Pt p){auto [x,y]=p;int rem=mod(y,C);return rem*A+mod(x-((y-rem)/C)*B,A);};
  auto images=[&](Pt p){Bits b=0;for(auto m:quotient)b|=Bits(1)<<res(apply(m,p));return b;};std::vector<Bits> old;for(auto p:par)old.push_back(images(p));std::set<Pt> seed(par.begin(),par.end()),env;
  for(auto [x,y]:par)for(int dx=-2;dx<=2;dx++)for(int dy=-2;dy<=2;dy++)if(abs(dx)+abs(dy)<=2&&!seed.count({x+dx,y+dy}))env.insert({x+dx,y+dy});std::vector<Pt> cs;std::vector<Bits> img;std::vector<unsigned> evict;
  for(auto p:env){auto b=images(p);if(pop(b)!=quotient.size())continue;int mask=0;for(int i=0;i<oldn;i++)if(old[i]&b)mask|=1u<<i;cs.push_back(p);img.push_back(b);evict.push_back(mask);}
  std::vector<Pose> pool=first;std::set<Pose> already(first.begin(),first.end());for(auto m:atlas)if(already.insert(m).second)pool.push_back(m);for(auto m:atlas)for(auto d:D){m[2]+=d.first;m[5]+=d.second;if(already.insert(m).second)pool.push_back(m);m[2]-=d.first;m[5]-=d.second;}
  long local=0,geoms=0,stars=0;std::set<std::pair<unsigned,Small>> seen;std::vector<int> adds;
  auto test=[&](unsigned cut,Small add){if(!seen.emplace(cut,add).second)return;Bits retained=0;for(int i=0;i<oldn;i++)if(!(cut>>i&1u))retained|=old[i];if(pop(retained)!=(oldn-std::popcount(cut))*int(quotient.size()))return;local++;Shape child;for(int i=0;i<oldn;i++)if(!(cut>>i&1u))child.push_back(par[i]);for(auto m=add;m;m&=m-1)child.push_back(cs[idx(m)]);if(!solid(child))return;geoms++;auto k=norm(child);if(keys.count(k))return;Star star(child,pool);if(!star.run())return;stars++;keys.insert(k);bank<<keys.size()<<" O?";for(auto[x,y]:k)bank<<' '<<x<<' '<<y;bank<<'\n';routes<<keys.size()<<'|'<<id<<'|'<<cols[1]<<'|'<<cols[3]<<'|';for(auto[x,y]:child)routes<<x<<','<<y<<' ';routes<<'|';for(int i:star.selected){auto t=star.poses[i];routes<<t[0]<<','<<t[1]<<','<<t[2]<<','<<t[3]<<','<<t[4]<<','<<t[5]<<' ';}routes<<'\n';};
  auto grow=[&](auto&& self,int lo,Small add,Bits used,unsigned cut,int k,int target)->void{int forced=std::popcount(cut);if(forced>target-gain)return;if(k==target){int free=target-gain-forced;if(free==0)test(cut,add);else if(free==1){for(int j=0;j<oldn;j++)if(!(cut>>j&1u))test(cut|(1u<<j),add);}else if(free==2 && maxExtra>=2){for(int j=0;j<oldn;j++)if(!(cut>>j&1u))for(int l=j+1;l<oldn;l++)if(!(cut>>l&1u))test(cut|(1u<<j)|(1u<<l),add);}return;}for(int i=lo;i<int(cs.size());i++){if(!(used&img[i]))self(self,i+1,add|(Small(1)<<i),used|img[i],cut|evict[i],k+1,target);}};
  if(cs.size()>63)throw std::runtime_error("large triangular envelope");for(int m=1;m<=maximum;m++)grow(grow,0,0,0,0,0,m);log<<id<<' '<<pool.size()<<' '<<cs.size()<<' '<<local<<' '<<geoms<<' '<<stars<<' '<<keys.size()<<std::endl;bank.flush();routes.flush();attempts+=local;disks+=geoms;passed+=stars;
 }std::cerr<<"exchanges "<<attempts<<" disks "<<disks<<" admitted "<<passed<<" unique "<<keys.size()<<'\n';}

#endif
