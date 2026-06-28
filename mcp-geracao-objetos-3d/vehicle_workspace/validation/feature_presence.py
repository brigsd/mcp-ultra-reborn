"""Valida presenca de features pedidas na spec, por nome de objeto (Fase 5).

No MVP, presenca = existe objeto cujo nome contem o marcador da feature. Isso
funciona porque os geradores usam ids estaveis (vehicle_aero_*, vehicle_light_*).
"""

# feature da spec -> marcador no nome do objeto
_FEATURE_MARKERS = {
    "front_splitter": "aero_front_splitter",
    "large_rear_diffuser": "aero_rear_diffuser",
    "active_rear_wing": "aero_rear_wing",
    "side_intakes": "intake_side",
}

# sempre esperados num modelo standard/high
_ALWAYS = {
    "body": "body_main",
    "canopy_glass": "glass_canopy",
    "headlights": "light_headlight",
    "taillights": "light_taillight",
    "mirrors": "mirror_",
    "wheels": "wheel_",
}


def audit_feature_presence(spec, object_names):
    names = list(object_names or [])
    results = {}

    for key, marker in _ALWAYS.items():
        results[key] = any(marker in n for n in names)

    feats = spec.get("features", {})
    for key, marker in _FEATURE_MARKERS.items():
        if feats.get(key):
            results[key] = any(marker in n for n in names)

    missing = [k for k, ok in results.items() if not ok]
    return {
        "feature_results": results,
        "missing": missing,
        "pass": len(missing) == 0,
    }
