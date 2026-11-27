"""Reading uploaded files safely, for every endpoint that takes a file.

An upload is read with a byte limit (one byte past it, so an oversized file is refused without reading the
rest), and an Office Open XML file (.xlsx, .docx) is a zip that is checked before anything parses it: it must
not expand past MAX_UNPACKED_BYTES (a zip bomb) and must not carry macros.
"""

import io
import zipfile

from fastapi import UploadFile

from trishul_api.common.errors import ApiError

# A real ERP workbook or document unpacks to a few megabytes; this is far above any of them.
MAX_UNPACKED_BYTES = 100 * 1024 * 1024


def read_upload(file: UploadFile, limit: int, too_large: str) -> bytes:
    """The upload's bytes, at most `limit` of them; `too_large` is the message for a bigger file."""
    content = file.file.read(limit + 1)
    if not content:
        raise ApiError("The uploaded file is empty.")
    if len(content) > limit:
        raise ApiError(too_large)
    return content


def check_office_archive(raw: bytes, root: str, invalid: ApiError) -> None:
    """A .docx / .xlsx must be a real Office Open XML zip (its main part under `root`, e.g. "xl/"),
    without macros, and not unpack to more than MAX_UNPACKED_BYTES. `invalid` is raised otherwise."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if "[Content_Types].xml" not in names or not any(n.startswith(root) for n in names):
                raise invalid
            _check_archive(archive)
    except zipfile.BadZipFile as error:
        raise invalid from error


def check_workbook_archive(raw: bytes) -> None:
    """For the Excel imports: refuses a workbook with macros or one that unpacks past the limit. A file that
    is not a zip at all is left to the import's own parser, which explains what file it expected."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            _check_archive(archive)
    except zipfile.BadZipFile:
        return


def _check_archive(archive: zipfile.ZipFile) -> None:
    # Declared sizes bound what zipfile will decompress, so summing them is a safe check.
    if any(n.lower().endswith("vbaproject.bin") for n in archive.namelist()):
        raise ApiError("Files with macros cannot be uploaded. Save the file without macros first.")
    if sum(info.file_size for info in archive.infolist()) > MAX_UNPACKED_BYTES:
        raise ApiError("The file is too large once unpacked.")
