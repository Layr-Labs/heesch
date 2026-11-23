#include "cadical.hpp"

extern "C" {
void *first_solver() {
    auto solver = new CaDiCaL::Solver;
    solver->set("quiet", 1);
    return solver;
}
const char *first_load(void *solver, const char *path) {
    int n;
    return static_cast<CaDiCaL::Solver*>(solver)->read_dimacs(path, n, 1);
}
void first_clause(void *solver, const int *values, int n) {
    auto s = static_cast<CaDiCaL::Solver*>(solver);
    for (int i=0; i<n; ++i) s->add(values[i]);
    s->add(0);
}
int first_solve(void *solver) {
    return static_cast<CaDiCaL::Solver*>(solver)->solve();
}
void first_phase(void *solver, int value) {
    static_cast<CaDiCaL::Solver*>(solver)->phase(value);
}
void first_model(void *solver, int *values, int n) {
    auto s = static_cast<CaDiCaL::Solver*>(solver);
    for (int i=0; i<n; ++i) values[i]=s->val(i+1);
}
}
