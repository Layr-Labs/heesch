// Non-equivariant two- and three-copy near packings. A rotation is deliberately incompatible with the
// period lattice: two representatives of one residue can map to different residues in the second grain.
#define main many_rows_main
#include "generate.cpp"
#undef main
int main(int argc,char**argv){if(argc!=7)return 2;std::ofstream bank(argv[1]),routes(argv[2]),log(argv[3]);int trials=atoi(argv[4]);std::mt19937 rng(atoi(argv[5]));int k=atoi(argv[6]);auto draw=[&](int n){return int(rng()%n);};std::set<Shape>seen;int models=0,feas=0;long long visited=0;std::map<int,int> byvac;
    for(int trial=0;trial<trials;trial++){int n=17+draw(4),vac=1+draw(3),N=k*n+vac;std::vector<int> as;for(int f=1;f<=N;f++)if(N%f==0)as.push_back(f);int A=as[draw(as.size())],C=N/A,B=draw(A);auto res=[&](int x,int y){int z=mod(y,C);return z*A+mod(x-((y-z)/C)*B,A);};
        int w=3+draw(4),h=3+draw(4);std::vector<Pose> poses={ori[0]};bool anisotropic=false;
        for(int j=1;j<k;j++){int r=1+draw(7);auto t=ori[r];int shiftx=draw(2*w+3)-w-1,shifty=draw(2*h+3)-h-1;t=registered(r,shiftx,shifty,w,h);poses.push_back(t);anisotropic|= res(t[0]*A,t[3]*A)!=0 || res(t[0]*B+t[1]*C,t[3]*B+t[4]*C)!=0;}
        if(!anisotropic)continue;models++;Problem prob{n,k,N,A,B,C,2500,poses,{},{},{},rng,{}};prob.run(w,h,18);visited+=prob.nodes;if(!prob.results.empty())feas++;
        log<<trial<<' '<<n<<' '<<A<<' '<<B<<' '<<C<<' '<<vac<<' '<<prob.nodes<<' '<<prob.results.size()<<'\n';for(auto&s:prob.results){auto key=norm(s);if(!seen.insert(key).second)continue;int id=seen.size();bank<<id<<" O?";for(auto[x,y]:key)bank<<' '<<x<<' '<<y;bank<<'\n';routes<<id<<' '<<trial<<' '<<n<<' '<<A<<' '<<B<<' '<<C<<' '<<vac<<" poses";for(auto m:poses)routes<<' '<<m[0]<<','<<m[1]<<','<<m[2]<<','<<m[3]<<','<<m[4]<<','<<m[5];routes<<" outline";for(auto[x,y]:s)routes<<' '<<x<<','<<y;routes<<'\n';byvac[vac]++;}}
    std::cerr<<"proposals "<<trials<<" mismatched_rotation_templates "<<models<<" solved "<<feas<<" distinct "<<seen.size()<<" nodes "<<visited<<'\n';for(auto [v,n]:byvac)std::cerr<<v<<' '<<n<<'\n';}
