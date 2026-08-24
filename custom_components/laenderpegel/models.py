from dataclasses import dataclass


@dataclass(frozen=True)
class GaugeStation:
    id: str
    name: str
    wasser: str
    stand: str = ""
    wert: str = ""
    warnstufe: str = ""
    warnstufe_aktiv: bool = False
