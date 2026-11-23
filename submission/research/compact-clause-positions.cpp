// Translate submitted core clauses to their exact original DIMACS positions.
// The authoritative Python gate separately checks membership of the same retained lines.
#include <fstream>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>
#include <cstdint>
using namespace std;
int main(int argc,char**argv){if(argc!=4)return 2;ifstream core(argv[1]),full(argv[2],ios::binary);ofstream ids(argv[3]);if(!core||!full||!ids)return 3;
 string text;unordered_map<string,vector<uint32_t>>wanted;vector<uint64_t>matched;while(getline(core,text)){wanted[text].push_back(matched.size());matched.push_back(0);}getline(full,text);uint64_t row=0;while(!wanted.empty()&&getline(full,text)){row++;auto it=wanted.find(text);if(it==wanted.end())continue;for(auto j:it->second)matched[j]=row;wanted.erase(it);}if(!wanted.empty())return 4;for(auto j:matched)ids<<j<<'\n';cout<<"Recovered exact ordered DIMACS positions for "<<matched.size()<<" submitted clauses through original clause "<<row<<"\n";}
