// Evaluate every original DIMACS clause against the SAT solver's complete assignment.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
using namespace std;
int main(int n,char **args){
    if(n!=3){cerr<<"usage: check_model formula.cnf model.txt\n";return 1;}
    auto f=fopen(args[1],"r");if(!f)return 2;unsigned vars,clauses;char head[256];if(!fgets(head,sizeof head,f)||sscanf(head,"p cnf %u %u",&vars,&clauses)!=2)return 3;
    ifstream model(args[2]);vector<signed char> val(vars+1,0);string line;unsigned assignments=0;
    while(getline(model,line))if(line.rfind("v ",0)==0){istringstream literals(line.substr(2));int v;while(literals>>v)if(v){unsigned k=abs(v);if(k>vars||val[k])return 4;val[k]=v>0?1:-1;++assignments;}}
    if(assignments!=vars)return 5;unsigned passed=0;bool satisf=false,started=false,negative=false;unsigned number=0;
    vector<unsigned char> buf(1U<<21);size_t count;
    while((count=fread(buf.data(),1,buf.size(),f))){for(size_t i=0;i<count;++i){unsigned char c=buf[i];if(c>='0'&&c<='9'){number=10*number+c-'0';started=true;}else if(c=='-'){negative=true;}else if(started){if(number){if(number>vars)return 6;satisf|=(val[number]==(negative?-1:1));}else{if(!satisf){cerr<<"violated clause "<<passed+1<<'\n';return 7;}++passed;satisf=false;}started=negative=false;number=0;}}}
    if(passed!=clauses||started||ferror(f))return 8;cout<<"VERIFIED "<<passed<<" clauses on "<<assignments<<" assignments\n";
}
