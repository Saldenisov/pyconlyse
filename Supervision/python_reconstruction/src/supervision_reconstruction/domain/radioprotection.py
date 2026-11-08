"""Sampled radioprotection-graph semantics from ``2_SUP_Graph _Radioprot.vi``.

This module exposes invalid EPC bitmasks without inventing a shutdown state.
The native 0, Default frame passes through the incoming state ordinate; it does
not assign zero. The unsampled outer False frame performs no indicator/local
write, so stored output state must be supplied separately from graph input.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EpcState:
    """The four OK bits read by the radioprotection graph VI."""

    arret_ok: bool
    veille_ok: bool
    pretir_ok: bool
    tir_ok: bool
    arret_not_veille: bool
    pretir_not_veille: bool
    tir_not_pretir: bool

    @property
    def bitmask(self) -> int:
        """LabVIEW Boolean Array To Number order: ARRET, VEILLE, PRETIR, TIR."""

        return (
            int(self.arret_ok)
            | (int(self.veille_ok) << 1)
            | (int(self.pretir_ok) << 2)
            | (int(self.tir_ok) << 3)
        )

    @property
    def state_is_one_hot(self) -> bool:
        return self.bitmask in (1, 2, 4, 8)

    @property
    def transition_detected(self) -> bool:
        return self.arret_not_veille or self.pretir_not_veille or self.tir_not_pretir


@dataclass(frozen=True)
class RadioprotectionGraph:
    """The four fields in the legacy ``Graphe Radioprot`` cluster."""

    sommateur: float
    tir_pretir_veille_arret: float
    vide_section: float
    transition: float


@dataclass(frozen=True)
class RadioprotectionGraphUpdate:
    """Graph output plus an explicit validity signal absent from the legacy UI."""

    graph: RadioprotectionGraph
    sampled: bool
    state_bitmask: int
    state_is_one_hot: bool


def _legacy_state_ordinate(state_bitmask: int, incoming_ordinate: float) -> float:
    """Map one-hot states; default tunnel 245 → 2016 retains input ordinate."""

    return {1: 0.0, 2: 1.0, 4: 2.0, 8: 3.0}.get(state_bitmask, incoming_ordinate)


def update_radioprotection_graph(
    btim: float,
    previous: RadioprotectionGraph,
    somme_radioprotection: bool,
    epc: EpcState,
    jauge_vide_section: float,
    *,
    stored_output: RadioprotectionGraph | None = None,
) -> RadioprotectionGraphUpdate:
    """Apply the VI's ``BTIM mod 10 == 0`` sampling and graph rules.

    An unsampled call retains the explicitly supplied stored output, not the
    graph input (``previous``). Missing stored state fails closed. On a sampled call,
    ``transition`` is the *incoming* state ordinate only when any of the three
    explicit EPC transition booleans is true; otherwise it is the evidenced
    ``-1`` sentinel.  The current ordinate is wired separately to
    ``tir_pretir_veille_arret``.
    """

    sampled = btim % 10 == 0
    bitmask = epc.bitmask
    if not sampled:
        if not isinstance(stored_output, RadioprotectionGraph):
            raise ValueError("unsampled graph requires explicit stored_output")
        return RadioprotectionGraphUpdate(
            graph=stored_output,
            sampled=False,
            state_bitmask=bitmask,
            state_is_one_hot=epc.state_is_one_hot,
        )

    ordinate = _legacy_state_ordinate(bitmask, previous.tir_pretir_veille_arret)
    return RadioprotectionGraphUpdate(
        graph=RadioprotectionGraph(
            sommateur=float(int(somme_radioprotection)),
            tir_pretir_veille_arret=ordinate,
            vide_section=jauge_vide_section,
            transition=(
                previous.tir_pretir_veille_arret if epc.transition_detected else -1.0
            ),
        ),
        sampled=True,
        state_bitmask=bitmask,
        state_is_one_hot=epc.state_is_one_hot,
    )
