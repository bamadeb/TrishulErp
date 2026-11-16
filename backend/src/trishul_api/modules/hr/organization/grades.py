"""The grades a designation can carry. A grade is not its own table."""

from trishul_api.common.errors import ApiError

SUPPORTED_GRADES = ("E1", "E2", "E3", "E4", "E5", "G1", "G2", "G3", "G4", "G5", "G6")
_SUPPORTED = frozenset(SUPPORTED_GRADES)


def require_grade(grade: str | None, *, field: str = "grade") -> None:
    """Reject a grade outside the designation master. Blank is not a grade."""
    if grade in _SUPPORTED:
        return
    raise ApiError(
        "Choose a grade from the grade list.",
        errors={field: ["Use E1, E2, E3, E4, E5, G1, G2, G3, G4, G5 or G6."]},
    )
