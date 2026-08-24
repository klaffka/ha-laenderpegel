from __future__ import annotations

from . import bb, bw, by, hb, he, mv, ni, nw, rp, sh, sl, sn, st, th
from .base import BaseProvider

PROVIDERS: dict[str, BaseProvider] = {
    p.code: p
    for p in (
        bb.Provider(),
        bw.Provider(),
        by.Provider(),
        hb.Provider(),
        he.Provider(),
        mv.Provider(),
        ni.Provider(),
        nw.Provider(),
        rp.Provider(),
        sh.Provider(),
        sl.Provider(),
        sn.Provider(),
        st.Provider(),
        th.Provider(),
    )
}


def get_provider(code: str) -> BaseProvider:
    return PROVIDERS[code]


def provider_names() -> list[tuple[str, str]]:
    return [(code, provider.name) for code, provider in sorted(PROVIDERS.items(), key=lambda item: item[1].name)]
