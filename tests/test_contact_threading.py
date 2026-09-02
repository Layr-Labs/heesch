"""§11.1: the one-contact-relation invariant, enforced by test.

Two tests: (1) the identical relation object (`is`, not equality) reaches
every corona call site; (2) flipping the convention at config level moves the
level assignment and the surround check TOGETHER."""

from util import monomino_hc1, witness_text, xf_t

from heesch_verify import GRIDS, VerifyConfig, VerifyError, verify_witness
from heesch_verify.grids import Contact
from heesch_verify import patch as patch_mod


def test_contact_object_identity_across_call_sites():
    """Wrap Contact.neighbors with a recorder and verify every call during a
    verification run goes through one single object."""
    seen_ids = set()
    orig = Contact.neighbors

    def recording(self, cell):
        seen_ids.add(id(self))
        return orig(self, cell)

    Contact.neighbors = recording
    try:
        verify_witness(monomino_hc1())
    finally:
        Contact.neighbors = orig
    assert len(seen_ids) == 1, f"{len(seen_ids)} distinct Contact objects reached call sites"


def test_no_module_level_contact_default():
    import inspect

    for fn in (patch_mod.check_corona, patch_mod.contact_neighbors,
               patch_mod.touches, patch_mod.required_set):
        sig = inspect.signature(fn)
        p = sig.parameters.get("contact")
        assert p is not None, f"{fn.__name__} does not take contact"
        assert p.default is inspect.Parameter.empty, f"{fn.__name__} has a contact default"


def test_convention_flip_moves_levels_and_surround_together():
    """A monomino witness covering only the 4 edge neighbors: under edge
    contact it is a complete 1-corona; under point contact the 4 diagonal
    cells are gaps. If only one of recompute_levels/surround honored the
    flip, one of these assertions would fail."""
    placements = [(0, xf_t(0, 0))]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        placements.append((1, xf_t(dx, dy)))
    text = witness_text("O", [(0, 0)], 1, 1, [placements])

    edge_cfg = VerifyConfig(contact_mode="edge")
    out = verify_witness(text, edge_cfg)
    assert out.result.hc_verified == 1

    point_cfg = VerifyConfig(contact_mode="point")
    try:
        r = verify_witness(text, point_cfg)
        # Lenient mode may downgrade instead of rejecting; either way the
        # claim must NOT verify at hc=1.
        assert r.result.hc_verified == 0
    except VerifyError as e:
        assert e.code.value in ("PATCH_GAP", "CLAIM_WEAKER_THAN_STATED")
