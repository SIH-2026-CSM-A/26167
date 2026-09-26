"""The model identity this backend expects the inference Space to serve.

Recorded demo answers carry the identity that produced them. The cached-demo path compares
it with these values (and with the last identity a live Space call reported), so a recording
made with other weights cannot pass as current. tests/inference/test_identity.py keeps
base_revision in sync with app.models.internvl.INTERNVL_REVISION and the hashes in sync with
inference_space/app.py.
"""

EXPECTED_MODEL_IDENTITY = {
    "base_model": "OpenGVLab/InternVL3-2B",
    "base_revision": "899155015275a9b7338c7f4677e19c784e0e5a21",
    "adapter_sha256": "796d3c25d883d7798c3d7634f855c86f5ae2c0107922c7d5d80f216298dde405",
    "bit_sha256": "c159ba76143447f58c9f367ce8126a0014f2e4ba218cdb97cca173952c38cb3b",
}


def identity_mismatches(recorded: dict | None, current: dict | None) -> list[str]:
    """Keys of EXPECTED_MODEL_IDENTITY on which `recorded` differs from `current`."""
    if recorded is None or current is None:
        return []
    return [key for key in EXPECTED_MODEL_IDENTITY if recorded.get(key) != current.get(key)]
