"""Downloads the face attendance models (OpenCV Zoo YuNet + SFace) and checks their SHA-256.

    uv run python scripts/download_face_models.py [target folder]

Default folder: backend/var/face_models (what the API uses unless TRISHUL_FACE_MODELS_DIR is set).
Licences: YuNet MIT, SFace Apache 2.0; both licence files are saved next to the models.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

from trishul_api.modules.hr.face_attendance.engine import DEFAULT_MODELS_DIR, MODEL_FILES

_HF = "https://huggingface.co/opencv"
SOURCES = {
    "face_detection_yunet_2023mar.onnx": f"{_HF}/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": (
        f"{_HF}/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx"
    ),
    "YUNET_LICENSE.txt": f"{_HF}/face_detection_yunet/resolve/main/LICENSE",
    "SFACE_LICENSE.txt": f"{_HF}/face_recognition_sface/resolve/main/LICENSE",
}


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MODELS_DIR
    target.mkdir(parents=True, exist_ok=True)
    failed = False
    for name, url in SOURCES.items():
        path = target / name
        expected = MODEL_FILES.get(name)
        if not (expected and path.is_file() and _sha256(path) == expected):
            print(f"downloading {name} ...")
            with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - fixed https URLs
                path.write_bytes(response.read())
        if expected and _sha256(path) != expected:
            print(f"CHECKSUM MISMATCH: {name}")
            path.unlink()
            failed = True
        else:
            print(f"ok  {name}  {path.stat().st_size:,} bytes")
    return 1 if failed else 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
