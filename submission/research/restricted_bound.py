"""Test whether any extension of the supplied third-ring footprint beats 145/152."""
from pathlib import Path
from types import SimpleNamespace
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"solver"))
from joint import run


if __name__ == "__main__":
    # Only a terminal INFEASIBLE result establishes a bound. If a model returns
    # a valid better arrangement, joint.py saves it with the seed's certificate.
    options = SimpleNamespace(source=HERE.parent/"best.heesch", output=Path("strict-improvement.heesch"),
                              complete_four=False, outer_reference=None, conditional_support=True,
                              distinct4=False, distinct_domain=False, maximize=False, sample_domains=1,
                              target=1, comparison=(7,152), boundary_min=None, boundary_max=None,
                              damage_max=None, seconds=180, workers=3)
    run(options)
