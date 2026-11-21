#pragma once
// Small API adapter for Kaplan's reference searcher. Search results must
// still pass the unmodified benchmark verifier and non-tiler proof gate.
#include <cadical.hpp>
#include <cstdint>
#include <vector>

namespace CMSat {
enum lbool { l_False = 0, l_True = 1, l_Undef = 2 };

class Lit {
 public:
  Lit() : dimacs_(0) {}
  Lit(uint32_t variable, bool negative)
      : dimacs_(negative ? -int(variable + 1) : int(variable + 1)) {}
  int dimacs() const { return dimacs_; }
 private:
  int dimacs_;
};

class SATSolver {
 public:
  SATSolver() { solver_.set("quiet", 1); }
  void new_vars(uint32_t count) {
    count_ += count;
    solver_.reserve(int(count_));
  }
  bool add_clause(const std::vector<Lit>& clause) {
    for (const auto& literal : clause) solver_.add(literal.dimacs());
    solver_.add(0);
    return true;
  }
  lbool solve() {
    const int result = solver_.solve();
    model_.assign(count_, l_Undef);
    if (result == 10) {
      for (uint32_t i = 0; i < count_; ++i) {
        const int value = solver_.val(int(i + 1));
        model_[i] = value > 0 ? l_True : value < 0 ? l_False : l_Undef;
      }
      return l_True;
    }
    return result == 20 ? l_False : l_Undef;
  }
  const std::vector<lbool>& get_model() const { return model_; }

 private:
  CaDiCaL::Solver solver_;
  uint32_t count_ = 0;
  std::vector<lbool> model_;
};
}
