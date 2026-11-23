// Cover all HNF quotients of orders 41,42,43 with all two-copy non-equivariant actions.
// Keep the lowest-collision registrations of each source. A second mode retains more defective registrations.
#define ONLY_ATLAS
#include "exchange.cpp"
#undef ONLY_ATLAS
struct Template{int A,B,C;Pose second;int collision;uint32_t tie;};
int main(int argc,char**v){std::ifstream in(v[1]);std::ofstream out(v[2]),logs(v[3]);int cap=atoi(v[4]),allowed=atoi(v[5]);std::mt19937 rng(624824);std::string line;while(getline(in,line)){auto e=split(line,'|');auto s=shape(e[1]);std::vector<Template> options;long tried=0;
for(int V:{41,42,43})for(int A=1;A<=V;A++)if(V%A==0){int C=V/A;for(int B=0;B<A;B++){auto res=[&](Pt p){int rem=mod(p.second,C);return rem*A+mod(p.first-((p.second-rem)/C)*B,A);};Small base=0;for(auto p:s)base|=Small(1)<<res(p);if(19-std::popcount(base)>allowed)continue;
for(int o=1;o<8;o++){auto t=ori[o];if(!res({t[0]*A,t[3]*A})&&!res({t[0]*B+t[1]*C,t[3]*B+t[4]*C}))continue;std::vector<Pt> transformed;for(auto p:s)transformed.push_back(apply(t,p));for(int x=0;x<A;x++)for(int y=0;y<C;y++){Small bits=base;for(auto p:transformed)bits|=Small(1)<<res({x+p.first,y+p.second});int miss=38-std::popcount(bits);tried++;if(miss<=allowed){t[2]=x;t[5]=y;options.push_back({A,B,C,t,miss,rng()});}}}}}
std::sort(options.begin(),options.end(),[](const Template&a,const Template&b){return std::tie(a.collision,a.tie)<std::tie(b.collision,b.tie);});int n=0;std::vector<int> cnt(10);for(auto&z:options){if(n>=cap)break;if(++cnt[z.collision]>(cap/2+1))continue;auto t=z.second;out<<e[0]<<"_"<<n++<<'|'<<z.A<<' '<<z.B<<' '<<z.C<<'|'<<e[1]<<"|1,0,0,0,1,0 "<<t[0]<<','<<t[1]<<','<<t[2]<<','<<t[3]<<','<<t[4]<<','<<t[5]<<'|'<<e[2]<<'|'<<e[3]<<'\n';}logs<<e[0]<<' '<<tried<<' '<<options.size()<<' '<<n<<std::endl;}}
