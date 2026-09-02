"""heesch_verify — exact, deterministic verifier for Heesch-number witnesses.

The witness path (this package minus gates.py) is stdlib-only and side-effect
free: agents import it and call `verify_witness` in their inner search loop;
identical code runs server-side. See docs/heesch-verifier-architecture.md.
"""

from .canonical import canonical_digest, canonical_form, symmetry_order
from .grids import GRIDS, Cell, Contact, Grid, Symmetry
from .parse import Submission, parse_submission
from .patch import CoronaResult, check_corona, contact_neighbors, required_set, touches
from .result import ErrorCode, Result, Status, VerifyError
from .shape import check_shape, connected, holes_of, is_hole_free
from .transform import Xform, check_symmetry
from .witness import CONVENTIONS_REVISION, VerifyConfig, WitnessOutcome, verify_witness

__version__ = "1.0.0.dev0"
