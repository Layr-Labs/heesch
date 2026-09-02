"""heesch_encoder — frozen CNF encoder for corona-existence formulas.

Companion to heesch_verify (see docs/heesch-cnf-encoder-spec.md). This package is
the trust boundary of the exactness claim: a proof certifies that one
specific formula is unsatisfiable, and only the theorems and round-trip
tests behind this encoder connect that formula to the geometry.

Imports from heesch_verify are restricted to patch/grids/transform (the
shared contact relation and Stage 5 oracle — obligation E5). Never import
gates, score, or anything with solver dependencies; the shipped encoder is
stdlib-only.
"""

ENCODER_VERSION = "heesch-encoder/v1"
REVISION = 1

from .api import EncodingResult, encode  # noqa: E402
from .types import Formula, Placement  # noqa: E402
