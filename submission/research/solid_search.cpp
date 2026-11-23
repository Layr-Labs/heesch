// Search polyhex corona witnesses by exact halo covering and recursive adjacency support.
// Every emitted witness must independently pass heesch_verify. Search pruning is heuristic.
#include <algorithm>
#include <bit>
#include <chrono>
#include <cstring>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <random>
#include <vector>
#include "grid.h"
#include "cloud.h"
#include "boundary.h"
#include "isohedral.h"

using Grid = OminoGrid<int16_t>;
using Transform = Grid::xform_t;
using Point = Grid::point_t;
using Domain = xform_set<int16_t>;
using Clock = std::chrono::steady_clock;
using Mask = uint64_t;
struct TimeLimit {};

class Search {
  const Shape<Grid>& shape;
  const int depth;
  Cloud<Grid> cloud;
  std::vector<Domain> support;
  std::vector<std::pair<int,Transform>> patch;
  std::mt19937 random;
  const Clock::time_point deadline;
  uint64_t nodes = 0;
  bool hole_restriction;
  int deepest = 0;
  std::string output;
  bool verbose;

  void tick() {
    if ((++nodes & 1023) == 0 && Clock::now() > deadline) throw TimeLimit{};
  }
  bool touches(const Transform& rel) const {
    return cloud.adjacent_.count(rel) || cloud.adjacent_culled_.count(rel) || cloud.adjacent_hole_.count(rel);
  }
  bool incompatible(const Transform& first, int first_depth, const Transform& second, int second_depth) const {
    const auto rel = first.invert() * second;
    if (rel.isIdentity() || cloud.isOverlap(rel)) return true;
    if (!touches(rel)) return false;
    if (hole_restriction && cloud.isHoleAdjacent(rel)) return true;
    if (first_depth > 0 && !support[first_depth].count(rel)) return true;
    return second_depth > 0 && !support[second_depth].count(rel.invert());
  }
  struct Local {
    std::vector<Transform> transforms;
    std::vector<Mask> covers;
    std::vector<std::vector<int>> conflicts, bycell;
    std::vector<int> disabled;
    std::vector<int> selected;
    Mask all = 0;
  };
  void select(Local& l, int i, int delta) {
    for (int j : l.conflicts[i]) l.disabled[j] += delta;
  }
  bool local_complete(Local& l, Mask remaining) {
    tick();
    if (!remaining) return true;
    int smallest = INT_MAX, cell = -1;
    for (Mask s = remaining; s; s &= s-1) {
      int j = std::countr_zero(s), count = 0;
      for (int i : l.bycell[j]) if (!l.disabled[i] && ++count >= smallest) break;
      if (!count) return false;
      if (count < smallest) { smallest = count; cell = j; }
    }
    for (int i : l.bycell[cell]) if (!l.disabled[i]) {
      select(l, i, 1); l.selected.push_back(i);
      bool success = local_complete(l, remaining & ~l.covers[i]);
      select(l, i, -1);
      if (success) return true;
      l.selected.pop_back();
    }
    return false;
  }
  void build_support() {
    if (cloud.halo_.size() >= 64) throw std::runtime_error("Unsupported halo size");
    point_map<int16_t,int> halo;
    for (auto p : cloud.halo_) { auto j=halo.size(); halo.emplace(p,j); }
    support.resize(depth+1);
    for (int d=1; d<=depth; ++d) {
      Local l;
      const Domain& prior = d==1 ? cloud.adjacent_ : support[d-1];
      for (const auto& t : prior) {
        if (d>1 && !prior.count(t.invert())) continue;
        Mask m=0;
        for (auto p : shape) { auto it=halo.find(t*p); if(it!=halo.end()) m |= Mask{1}<<it->second; }
        if (!m) continue;
        l.transforms.push_back(t); l.covers.push_back(m);
      }
      const int n=l.transforms.size();
      l.bycell.resize(halo.size()); l.conflicts.resize(n); l.disabled.resize(n);
      l.all=(Mask{1}<<halo.size())-1;
      for (int i=0;i<n;i++) {
        for(Mask s=l.covers[i];s;s&=s-1) l.bycell[std::countr_zero(s)].push_back(i);
        l.conflicts[i].push_back(i);
        for(int j=0;j<i;j++) if(incompatible(l.transforms[i],d-1,l.transforms[j],d-1)) {
          l.conflicts[i].push_back(j); l.conflicts[j].push_back(i);
        }
      }
      for(int i=0;i<n;i++) if(!support[d].count(l.transforms[i])) {
        select(l,i,1); l.selected={i};
        if(local_complete(l,l.all & ~l.covers[i]))
          for(int j:l.selected) support[d].insert(l.transforms[j]);
        select(l,i,-1);
      }
      if (verbose) std::cerr << ' ' << support[d].size();
    }
    if (verbose) std::cerr << '\n';
  }
  bool holefree() const {
    // Connected union of closed grid squares. V-E+F counts one minus
    // the number of diagonally separated pockets (empty cells use edge contact).
    point_set<int16_t> cells, corners;
    for(const auto& [level,tile]:patch) for(auto c:shape) cells.insert(tile*c);
    std::int64_t adjacent=0;
    for(auto c:cells) {
      adjacent+=cells.count(c+Point{1,0})+cells.count(c+Point{0,1});
      for (int16_t x=0;x<=1;++x) for (int16_t y=0;y<=1;++y) corners.insert(c+Point{x,y});
    }
    return std::int64_t(corners.size()) - 3*std::int64_t(cells.size()) + adjacent == 1;
  }
  void save(int level) const {
    std::ofstream file(output+".d"+std::to_string(level)+".heesch");
    file<<"O"; for(auto p:shape) file<<' '<<int(p.x_)<<' '<<int(p.y_);
    file<<"\n~ "<<level<<' '<<level<<" 1\n"<<patch.size()<<'\n';
    for (const auto& [n,t]:patch) file<<n<<' '<<t<<'\n';
  }
  struct Ring {
    std::vector<Transform> transforms;
    std::vector<std::vector<int>> covers, bycell, conflicts;
    std::vector<int> disabled, covered;
  };
  bool fill(Ring& r,int level,int remaining) {
    tick();
    if (!remaining) {
      if(!holefree()) return false;
      if(level>deepest) {
        deepest=level;
        if (verbose || level==depth) save(level);
        if (verbose) std::cerr<<" level "<<level<<" nodes "<<nodes<<'\n';
      }
      return level==depth || make_ring(level+1);
    }
    int smallest=INT_MAX, cell=-1;
    for(size_t j=0;j<r.covered.size();j++) if(!r.covered[j]) {
      int count=0;
      for(int i:r.bycell[j]) if(!r.disabled[i] && ++count>=smallest) break;
      if(!count) return false;
      if(count<smallest) {smallest=count;cell=j;}
    }
    for(int i:r.bycell[cell]) if(!r.disabled[i]) {
      for(int j:r.conflicts[i]) ++r.disabled[j];
      for(int j:r.covers[i]) ++r.covered[j];
      patch.emplace_back(level,r.transforms[i]);
      bool found=fill(r,level,remaining-r.covers[i].size());
      if(found) return true;
      patch.pop_back();
      for(int j:r.covers[i]) --r.covered[j];
      for(int j:r.conflicts[i]) --r.disabled[j];
    }
    return false;
  }
  bool make_ring(int level) {
    tick();
    if(Clock::now()>deadline) throw TimeLimit{};
    point_set<int16_t> occupied;
    point_map<int16_t,int> required;
    Domain candidates;
    for(auto& [r,t]:patch) for(auto p:shape) occupied.insert(t*p);
    for(auto& [r,t]:patch) if(r==level-1) {
      for(auto p:cloud.halo_) if(!occupied.count(t*p) && !required.count(t*p)) {
        auto id=required.size(); required.emplace(t*p,id);
      }
      for(auto& u:support[depth-r]) candidates.insert(t*u);
    }
    Ring ring;
    ring.bycell.resize(required.size());ring.covered.resize(required.size());
    std::vector<Transform> ordered(candidates.begin(),candidates.end()); std::shuffle(ordered.begin(),ordered.end(),random);
    for(const auto& candidate:ordered) {
      bool ok=true;
      for(const auto& [r,t]:patch) if(incompatible(t,depth-r,candidate,depth-level)) {ok=false;break;}
      if(!ok) continue;
      const int id=ring.transforms.size(); ring.transforms.push_back(candidate);
      ring.covers.emplace_back();
      for(auto p:shape) {
        auto it=required.find(candidate*p); if(it!=required.end()) {ring.covers.back().push_back(it->second);ring.bycell[it->second].push_back(id);}
      }
    }
    const int n=ring.transforms.size();
    ring.conflicts.resize(n); ring.disabled.resize(n);
    for(int i=0;i<n;i++) {
      ring.conflicts[i].push_back(i);
      for(int j=0;j<i;j++) if(incompatible(ring.transforms[i],depth-level,ring.transforms[j],depth-level)) {
        ring.conflicts[i].push_back(j);ring.conflicts[j].push_back(i);
      }
    }
    return fill(ring, level, required.size());
  }
public:
  Search(const Shape<Grid>& s,int d,int seed,int seconds,std::string path,bool detailed=true):shape(s),depth(d),cloud(s,ALL,false,false),random(seed),deadline(Clock::now()+std::chrono::seconds(seconds)),hole_restriction(false),output(std::move(path)),verbose(detailed){
       cloud.adjacent_.insert(cloud.adjacent_hole_.begin(),cloud.adjacent_hole_.end());
    }
  std::string run() {
    try {
      if (verbose) std::cerr<<"domains raw="<<cloud.adjacent_.size()<<" depth";
      build_support();
      if(support[depth].empty()) {
        if (verbose) std::cerr<<"no deep contact\n";
        return "NO_DEEP_CONTACT";
      }
      patch.emplace_back(0,Transform{});
      bool success=make_ring(1);
      std::string result=success?"FOUND":"EXHAUSTED";
      if (verbose) std::cerr<<result.c_str()<<" nodes="<<nodes<<" deepest="<<deepest<<'\n';
      return result;
    } catch(const TimeLimit&) {
      if (verbose) std::cerr<<"TIMEOUT nodes="<<nodes<<" deepest="<<deepest<<'\n';
      return "TIMEOUT";
    }
  }
  int best() const { return deepest; }
  uint64_t visits() const { return nodes; }
};
bool isohedral(const Shape<Grid>& shape) {
  auto b=getTileBoundary(shape);
  std::vector<point<int8_t>> word;
  for (size_t i=0; i<b.size(); ++i) word.push_back(b[(i+1)%b.size()]-b[i]);
  return IsohedralChecker().tilesIsohedrally(word,4);
}
Shape<Grid> read_shape(std::istream& in) {
  std::string marker; in>>marker;
  if (marker!="O?" && marker!="O") throw std::runtime_error("Input shape must use O? or O");
  Shape<Grid> shape;
  int x,y;
  while(in>>x) {
    if (!(in>>y)) throw std::runtime_error("Unpaired input coordinate");
    shape.add(x,y);
  }
  if(shape.size()==0) throw std::runtime_error("Empty input shape");
  shape.complete();
  return shape;
}
int main(int argc,char** argv) {
  if(argc==7 && std::string(argv[1])=="--batch") {
    std::ifstream input(argv[2]);
    if (!input) { std::cerr<<"No such input: "<<argv[2]<<'\n'; return 1; }
    std::filesystem::path output_dir(argv[3]);
    std::filesystem::create_directories(output_dir);
    auto depth=std::stoi(argv[4]), seed=std::stoi(argv[5]), seconds=std::stoi(argv[6]);
    std::string text;
    while(std::getline(input,text)) {
      if(text.empty()) continue;
      std::istringstream line(text);
      std::string id; line>>id;
      if (id.empty() || id.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-")!=std::string::npos) throw std::runtime_error("Invalid id");
      auto shape=read_shape(line);
      if(isohedral(shape)) {
        std::cout<<id.c_str()<<"\tISOHEDRAL\t0\t0\n";
      } else {
        Search s(shape,depth,seed,seconds,(output_dir/id).string(),false);
        auto result=s.run();
        std::cout<<id.c_str()<<'\t'<<result.c_str()<<'\t'<<s.best()<<'\t'<<s.visits()<<'\n';
        if(result=="FOUND") std::cout.flush();
      }
    }
    return 0;
  }
  if(argc!=6) {std::cerr<<"search shape_file depth seed time_seconds output_prefix\nsearch --batch id_shape_file output_dir depth seed time_seconds\n";return 1;}
  std::ifstream in(argv[1]); std::string text; std::getline(in,text);std::istringstream line(text);
  auto shape=read_shape(line);
  Search s(shape,std::stoi(argv[2]),std::stoi(argv[3]),std::stoi(argv[4]),argv[5]); s.run();
}
