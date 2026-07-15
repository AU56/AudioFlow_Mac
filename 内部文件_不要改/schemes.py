from __future__ import annotations

from raw_loader import exec_raw


exec_raw("schemes.rawcode", globals())


def _mac_pitch_chain(pitch):
    base_rate = 48000
    shifted_rate = max(8000, int(round(base_rate * float(pitch))))
    tempo = 1.0 / float(pitch)
    return f"aresample={base_rate},asetrate={shifted_rate},aresample={base_rate},atempo={tempo:.6f}"


def _replace_rubberband_filter(af):
    text = str(af or "")
    replacements = {
        "rubberband=pitch=0.975": _mac_pitch_chain(0.975),
        "rubberband=pitch=0.98": _mac_pitch_chain(0.98),
        "rubberband=pitch=0.978": _mac_pitch_chain(0.978),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


for _scheme in SCHEMES:
    if str(_scheme.get("engine", "")).lower() == "ffmpeg" and "rubberband" in str(_scheme.get("af", "")):
        _scheme["af"] = _replace_rubberband_filter(_scheme.get("af", ""))

SCHEME_BY_ID = {scheme["index"]: scheme for scheme in SCHEMES}
DISPLAY_SCHEMES = [SCHEME_BY_ID[i] for i in DISPLAY_SCHEME_IDS if i in SCHEME_BY_ID]
