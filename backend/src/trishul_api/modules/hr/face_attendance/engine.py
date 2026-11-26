"""Server face engine: YuNet finds the face, SFace turns it into a 128-number vector (OpenCV Zoo models).

    yunet  face_detection_yunet_2023mar.onnx   MIT         (Shiqi Yu)
    sface  face_recognition_sface_2021dec.onnx Apache 2.0  (OpenCV Zoo)

The .onnx files are not in git: scripts/download_face_models.py puts them in backend/var/face_models (or
TRISHUL_FACE_MODELS_DIR) and checks their SHA-256. Same vector on the phone (ONNX Runtime) and here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from cv2.typing import MatLike
from numpy.typing import NDArray

DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[5] / "var" / "face_models"
DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"
MODEL_FILES = {
    DETECTOR_FILE: "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    RECOGNIZER_FILE: "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
}
VECTOR_SIZE = 128

# The detector's own confidence; below this a "face" is usually a shadow or a pattern.
_DETECT_SCORE = 0.8
# Large photos are scaled down first: a face needs far fewer pixels than a 12 MP camera gives.
_MAX_SIDE = 1280
# YuNet looks for the face on a copy no bigger than this. It is trained on small faces: a close-up whose face
# is 450+ px wide scores below the 0.85 quality line (a clear selfie at 1280 scored 0.84, the same photo at
# 640 scored 0.92) and picks up stray low-score "faces". The box is scaled back for the full-size photo.
_DETECT_MAX_SIDE = 640

FloatVector = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class FaceAnalysis:
    """What the engine saw in one photo. ``vector`` is set only when exactly one face was found."""

    face_count: int
    confidence: float | None
    face_width_px: int | None
    sharpness: float | None
    brightness: float | None
    vector: FloatVector | None
    jpeg: bytes
    """The photo re-encoded as JPEG (rotation applied, metadata such as GPS stripped): what is stored."""


class FaceEngine(Protocol):
    def analyse(self, image: bytes) -> FaceAnalysis: ...


class FaceEngineUnavailable(RuntimeError):
    """The model files are missing or unreadable."""


class ImageUnreadable(ValueError):
    """The bytes are not a JPEG or PNG photo the engine can read."""


def similarity(a: FloatVector, b: FloatVector) -> float:
    """Cosine similarity of two face vectors: 1 = same direction; SFace's same-person line is about 0.36."""
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class OpenCvFaceEngine:
    """YuNet + SFace through OpenCV's DNN module. OpenCV networks are not thread-safe, so one lock."""

    def __init__(self, models_dir: Path) -> None:
        detector, recognizer = models_dir / DETECTOR_FILE, models_dir / RECOGNIZER_FILE
        for path in (detector, recognizer):
            if not path.is_file():
                raise FaceEngineUnavailable(f"Face model file is missing: {path.name}")
        self._detector = cv2.FaceDetectorYN.create(str(detector), "", (320, 320), _DETECT_SCORE, 0.3, 5000)
        self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer), "")
        self._lock = threading.Lock()

    def analyse(self, image: bytes) -> FaceAnalysis:
        picture = _decode(image)
        height, width = picture.shape[:2]
        scale = min(1.0, _MAX_SIDE / max(height, width))
        if scale < 1.0:
            picture = cv2.resize(picture, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
            height, width = picture.shape[:2]
        ok, encoded = cv2.imencode(".jpg", picture, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ImageUnreadable("The photo could not be processed.")
        jpeg = encoded.tobytes()

        detect_scale = min(1.0, _DETECT_MAX_SIDE / max(height, width))
        small = picture
        if detect_scale < 1.0:
            size = (round(width * detect_scale), round(height * detect_scale))
            small = cv2.resize(picture, size, interpolation=cv2.INTER_AREA)

        with self._lock:
            self._detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = self._detector.detect(small)
            if faces is not None and detect_scale < 1.0:
                faces = np.array(faces, dtype=np.float32)
                faces[:, :14] = faces[:, :14] / detect_scale  # box and 5 landmarks, back in full-size pixels
            if faces is None or len(faces) == 0:
                return FaceAnalysis(0, None, None, None, None, None, jpeg)
            if len(faces) > 1:
                best = float(max(face[-1] for face in faces))
                return FaceAnalysis(len(faces), best, None, None, None, None, jpeg)
            face = faces[0]
            aligned = self._recognizer.alignCrop(picture, face)
            feature = self._recognizer.feature(aligned)

        x, y, w, h = (int(v) for v in face[:4])
        crop = picture[max(0, y) : max(0, y) + max(1, h), max(0, x) : max(0, x) + max(1, w)]
        gray = cv2.cvtColor(crop if crop.size else aligned, cv2.COLOR_BGR2GRAY)
        # Sharpness on the 112x112 aligned face the matcher itself uses: the same blur scores the same
        # whatever the photo size. On the raw crop a large, sharp face (a webcam or phone photo taken
        # close) scored as "blurred", because per-pixel detail falls as the face gets bigger.
        aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        vector = np.asarray(feature, dtype=np.float32).reshape(-1)
        return FaceAnalysis(
            face_count=1,
            confidence=float(face[-1]),
            face_width_px=w,
            sharpness=float(cv2.Laplacian(aligned_gray, cv2.CV_64F).var()),
            brightness=float(gray.mean()),
            vector=vector,
            jpeg=jpeg,
        )


def _decode(image: bytes) -> MatLike:
    if not image.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
        raise ImageUnreadable("The photo must be a JPEG or PNG image.")
    # IMREAD_COLOR applies the EXIF orientation, so a phone photo taken sideways is upright here.
    picture = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    if picture is None:
        raise ImageUnreadable("The photo could not be read.")
    return picture


_engines: dict[Path, OpenCvFaceEngine] = {}
_engines_lock = threading.Lock()


def load_engine(models_dir: Path | None = None) -> OpenCvFaceEngine:
    """One engine per models folder for the life of the process (loading takes about a second)."""
    folder = (models_dir or DEFAULT_MODELS_DIR).resolve()
    with _engines_lock:
        engine = _engines.get(folder)
        if engine is None:
            engine = _engines[folder] = OpenCvFaceEngine(folder)
        return engine
