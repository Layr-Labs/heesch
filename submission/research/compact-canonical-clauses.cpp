// Restore the encoder's literal order to a core written in DRAT watch order.
// Clause numbers and contents are unchanged. Tautological input is invalid.
#include <algorithm>
#include <charconv>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
int main(int argc,char**argv){if(argc!=3)return 1;std::ifstream in(argv[1]);std::ofstream out(argv[2]);std::string s;long rows=0;while(std::getline(in,s)){const char*p=s.data(),*end=p+s.size();std::vector<int>lits;while(p<end){if(*p==' '||*p=='\r'||*p=='\t'){++p;continue;}int x;auto[n,err]=std::from_chars(p,end,x);if(err!=std::errc())return 2;p=n;if(!x)break;lits.push_back(x);}std::sort(lits.begin(),lits.end(),[](int a,int b){if(abs(a)==abs(b))return a<b;return abs(a)<abs(b);});auto last=std::unique(lits.begin(),lits.end());for(auto i=lits.begin();i!=last;++i){if(i!=lits.begin()&&*i==-*(i-1))return 3;out<<*i<<' ';}out<<"0\n";++rows;}std::cerr<<"Normalized "<<rows<<" clause texts\n";}
