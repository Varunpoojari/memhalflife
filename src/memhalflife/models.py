"""Core data models."""

from __future__ import annotations

from dataclasses import dataclass, field

STATUS_VALUE = {"Y": 1.0, "P": 0.5, "N": 0.0}
# "NA" = the plugin output needed to judge this artefact was missing. It is
# excluded from scores (never silently counted as absent) and surfaced in reports.
VALID_STATUS = set(STATUS_VALUE) | {"NA"}


@dataclass(frozen=True)
class ArtefactSpec:
    """One piece of evidence we expect a technique to leave in memory."""

    id: str
    category: str  # execution | injection | network | credential | persistence | cloud
    weight: float  # 3 = direct/high-fidelity, 2 = corroborating, 1 = contextual
    plugin: str  # full Volatility 3 plugin name, e.g. windows.cmdline.CmdLine
    match: dict[str, str]  # field -> regex; ALL must match on one row => Y
    partial: dict[str, str] = field(default_factory=dict)  # weaker conditions => P
    description: str = ""
    min_rows: int = 1
    synthetic: dict = field(default_factory=dict)  # used only by `memhalflife synth`


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    technique: str  # MITRE ATT&CK technique / sub-technique ID
    tactic: str
    platform: str  # windows | linux
    environment: str  # onprem | cloud-vm | cloud-container ...
    timepoints: tuple[float, ...]  # minutes after attack completion
    artefacts: tuple[ArtefactSpec, ...]
    reboot_at: float | None = None  # timepoint at/after which the host had rebooted
    notes: str = ""


@dataclass(frozen=True)
class ArtefactResult:
    artefact_id: str
    category: str
    weight: float
    status: str  # Y | P | N | NA

    @property
    def value(self) -> float | None:
        return STATUS_VALUE.get(self.status)
