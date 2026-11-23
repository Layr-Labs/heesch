// Retain the additions in a checked binary DRAT. Without deletions a purely RUP
// derivation is monotone. The candidate is checked independently against the complete CNF.
#include <fstream>
#include <iostream>
#include <cstdint>
int main(int argc,char**argv){if(argc!=3)return 2;std::ifstream src(argv[1],std::ios::binary);std::ofstream dst(argv[2],std::ios::binary);int op;uint64_t kept=0,removed=0;while((op=src.get())!=EOF){if(op!='a'&&op!='d')return 3;if(op=='a'){dst.put(op);kept++;}else removed++;int n;do{n=src.get();if(n==EOF)return 4;if(op=='a')dst.put(n);}while(n!=0);}std::cout<<"retained additions "<<kept<<", ignored deletions "<<removed<<'\n';}
