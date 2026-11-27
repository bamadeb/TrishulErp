"""Holiday master reads and writes. Records stay on hr.holiday."""

import threading
from datetime import UTC, date, datetime

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import AlreadyExists, ApiError, Conflict, NotFound
from trishul_api.db.models import Branch, Holiday, State
from trishul_api.modules.hr.leave.holiday_schemas import (
    HolidayCalendarQuery,
    HolidayCategory,
    HolidayCategoryOption,
    HolidayFilters,
    HolidayItem,
    HolidayListQuery,
    HolidayOption,
    HolidaySummary,
    HolidaySummaryQuery,
    HolidayWrite,
)

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_NATIONAL = (
    ("Republic Day", 1, 26),
    ("May Day", 5, 1),
    ("Independence Day", 8, 15),
    ("Gandhi Jayanti", 10, 2),
)
_FESTIVALS = (
    "New Year",
    "Mahashivratri",
    "Holi",
    "Raja Sankranti",
    "Rath Yatra",
    "Janmashtami",
    "Durga Puja",
    "Dussehra",
    "Deepawali",
    "Ras Purnima",
)
_STATE = Holiday.__table__.c.state_id
_ENSURE = threading.Lock()
_NOTICE = Holiday.__table__.c.source_notification_no
_NOTICE_ON = Holiday.__table__.c.source_notification_date
_DESCRIPTION = Holiday.__table__.c.description


def db_holiday_type(category: str) -> str:
    """Regional holidays stay on the existing Festival value, limited to a state or branch."""
    return "Festival" if category in {"Festival", "Regional"} else category


def api_category(holiday_type: str, state_id: int | None = None, branch_id: int | None = None) -> HolidayCategory:
    if holiday_type == "Optional":
        return "Optional"
    if holiday_type == "Festival":
        return "Regional" if state_id is not None or branch_id is not None else "Festival"
    return "National"


def applies_to_branch(branch_id: int, state_id: int | None):
    """National holidays apply everywhere. A state holiday applies only in that state."""
    return or_(
        Holiday.branch_id == branch_id,
        and_(Holiday.branch_id.is_(None), or_(_STATE.is_(None), state_id == _STATE)),
    )


class HolidayRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def filters(self) -> HolidayFilters:
        states = self._db.execute(
            select(State.id, State.name).where(State.is_active == True).order_by(State.name)  # noqa: E712
        ).all()
        branches = self._db.execute(
            select(Branch.id, Branch.name, Branch.state_id)
            .where(Branch.is_active == True)  # noqa: E712
            .order_by(Branch.name)
        ).all()
        years = {
            row[0].year if row[0].month >= 4 else row[0].year - 1
            for row in self._db.execute(select(Holiday.holiday_date)).all()
        }
        today = date.today()
        years.add(today.year if today.month >= 4 else today.year - 1)
        return HolidayFilters(
            categories=[HolidayCategoryOption(id=item, name=item) for item in ("National", "Festival", "Regional", "Optional")],
            states=[HolidayOption(id=row[0], name=row[1]) for row in states],
            locations=[HolidayOption(id=row[0], name=row[1], state_id=row[2]) for row in branches],
            financial_years=sorted(years),
            policy_festivals=list(_FESTIVALS),
        )

    def summary(self, query: HolidaySummaryQuery, today: date | None = None) -> HolidaySummary:
        self.ensure_national(_years(query))
        rows = self._rows(query)
        current = today or date.today()
        return HolidaySummary(
            total=len(rows),
            upcoming=sum(1 for row in rows if row.holiday_date >= current),
            national=sum(1 for row in rows if row.category == "National"),
            festival=sum(1 for row in rows if row.category == "Festival"),
            regional=sum(1 for row in rows if row.category == "Regional"),
            optional=sum(1 for row in rows if row.optional),
        )

    def calendar(self, query: HolidayCalendarQuery) -> list[HolidayItem]:
        if query.end_date < query.start_date:
            raise ApiError("The calendar end date is before the start date.")
        self.ensure_national(_years(query))
        return self._rows(query, start=query.start_date, end=query.end_date)

    def page(self, query: HolidayListQuery) -> tuple[list[HolidayItem], int]:
        self.ensure_national(_years(query))
        rows = self._rows(query, descending=query.sort == "-holidayDate")
        if query.sort in {"name", "-name"}:
            rows.sort(key=lambda row: row.name.lower(), reverse=query.sort.startswith("-"))
        start = (query.page - 1) * query.page_size
        return rows[start : start + query.page_size], len(rows)

    def get(self, holiday_id: int) -> HolidayItem:
        row = self._one(holiday_id)
        if row is None:
            raise NotFound("Holiday not found.")
        return row

    def create(self, actor: CurrentUser, data: HolidayWrite) -> HolidayItem:
        state_id, branch_id, holiday_type = self._checked(data, None)
        result = self._db.execute(
            Holiday.__table__.insert()
            .values(
                branch_id=branch_id,
                state_id=state_id,
                holiday_date=data.holiday_date,
                name=data.name.strip(),
                holiday_type=holiday_type,
                description=(data.description or "").strip() or None,
                is_active=data.is_active,
                created_by_user_id=actor.id,
            )
            .returning(Holiday.id)
        )
        created_id = int(result.scalar_one())
        self._db.flush()
        item = self._one(created_id)
        if item is None:
            raise NotFound("Holiday not found.")
        return item

    def update(self, actor: CurrentUser, holiday_id: int, expected: bytes, data: HolidayWrite) -> HolidayItem:
        current = self._db.get(Holiday, holiday_id)
        if current is None:
            raise NotFound("Holiday not found.")
        if current.row_version != expected:
            raise Conflict()
        state_id, branch_id, holiday_type = self._checked(data, holiday_id)
        updated = self._db.execute(
            Holiday.__table__.update()
            .where(Holiday.id == holiday_id, Holiday.row_version == expected)
            .values(
                branch_id=branch_id,
                state_id=state_id,
                holiday_date=data.holiday_date,
                name=data.name.strip(),
                holiday_type=holiday_type,
                description=(data.description or "").strip() or None,
                is_active=data.is_active,
                updated_at=datetime.now(UTC).replace(tzinfo=None),
                updated_by_user_id=actor.id,
            )
        )
        if updated.rowcount != 1:
            raise Conflict()
        self._db.flush()
        item = self._one(holiday_id)
        if item is None:
            raise NotFound("Holiday not found.")
        return item

    def delete(self, holiday_id: int, expected: bytes) -> None:
        current = self._db.get(Holiday, holiday_id)
        if current is None:
            raise NotFound("Holiday not found.")
        if current.row_version != expected:
            raise Conflict()
        removed = self._db.execute(
            Holiday.__table__.delete().where(Holiday.id == holiday_id, Holiday.row_version == expected)
        )
        if removed.rowcount != 1:
            raise Conflict()

    def ensure_national(self, years: set[int]) -> None:
        """Insert the four fixed TTPL national dates when that calendar year is opened.

        Festival dates are not inserted here. HR enters those and leaves them inactive until published.
        """
        if not years:
            return
        with _ENSURE:
            inserted = False
            for year in years:
                for name, month, day in _NATIONAL:
                    when = date(year, month, day)
                    existing = self._db.scalar(
                        select(Holiday.id)
                        .where(Holiday.holiday_date == when, func.lower(Holiday.name) == name.lower())
                        .limit(1)
                    )
                    if existing is not None:
                        continue
                    self._db.execute(
                        Holiday.__table__.insert().values(
                            branch_id=None,
                            state_id=None,
                            holiday_date=when,
                            name=name,
                            holiday_type="National",
                            description="TTPL national holiday",
                            is_active=True,
                        )
                    )
                    inserted = True
            if inserted:
                self._db.commit()

    def _checked(self, data: HolidayWrite, holiday_id: int | None) -> tuple[int | None, int | None, str]:
        name = data.name.strip()
        if data.category in {"National", "Festival"}:
            if data.state_id is not None or data.location_id is not None:
                label = "National" if data.category == "National" else "Festival"
                raise ApiError(f"{label} holidays apply to every location.")
            state_id, branch_id = None, None
        else:
            if data.state_id is None:
                raise ApiError("State is mandatory for a regional or optional holiday.")
            state = self._db.get(State, data.state_id)
            if state is None or not state.is_active:
                raise ApiError("Select a valid state.")
            branch_id = data.location_id
            if branch_id is not None:
                branch = self._db.get(Branch, branch_id)
                if branch is None or not branch.is_active:
                    raise ApiError("Select a valid location.")
                if branch.state_id != data.state_id:
                    raise ApiError("The location is not in the selected state.")
            state_id = data.state_id
        duplicate = self._db.scalar(
            select(Holiday.id)
            .where(Holiday.holiday_date == data.holiday_date, func.lower(Holiday.name) == name.lower())
            .limit(1)
        )
        if duplicate is not None and duplicate != holiday_id:
            raise AlreadyExists("A holiday with this name already exists on this date.")
        return state_id, branch_id, db_holiday_type(data.category)

    def _rows(
        self,
        query: HolidaySummaryQuery | HolidayListQuery,
        *,
        start: date | None = None,
        end: date | None = None,
        descending: bool = False,
    ) -> list[HolidayItem]:
        statement = self._filtered(query, start=start, end=end).order_by(
            Holiday.holiday_date.desc() if descending else Holiday.holiday_date, Holiday.id
        )
        rows = self._db.execute(statement).all()
        return [self._item(row) for row in rows]

    def _filtered(self, query: HolidaySummaryQuery | HolidayListQuery, *, start: date | None, end: date | None):
        statement = (
            select(
                Holiday.id,
                Holiday.name,
                Holiday.holiday_date,
                Holiday.holiday_type,
                Holiday.is_active,
                Holiday.row_version,
                Holiday.branch_id,
                _STATE,
                _NOTICE,
                _NOTICE_ON,
                _DESCRIPTION,
                State.name.label("state_name"),
                Branch.name.label("location_name"),
            )
            .select_from(Holiday)
            .outerjoin(State, State.id == _STATE)
            .outerjoin(Branch, Branch.id == Holiday.branch_id)
        )
        if query.active_only:
            statement = statement.where(Holiday.is_active == True)  # noqa: E712
        if query.holiday_category == "Festival":
            statement = statement.where(
                Holiday.holiday_type == "Festival", Holiday.branch_id.is_(None), _STATE.is_(None)
            )
        elif query.holiday_category == "Regional":
            statement = statement.where(
                Holiday.holiday_type == "Festival",
                or_(Holiday.branch_id.is_not(None), _STATE.is_not(None)),
            )
        elif query.holiday_category is not None:
            statement = statement.where(Holiday.holiday_type == db_holiday_type(query.holiday_category))
        if query.search:
            statement = statement.where(Holiday.name.contains(query.search.strip(), autoescape=True))
        statement = statement.where(self._scope(query.state_id, query.location_id))
        range_start, range_end = _bounds(query.financial_year, query.calendar_year)
        if start is not None:
            range_start = start if range_start is None else max(range_start, start)
        if end is not None:
            range_end = end if range_end is None else min(range_end, end)
        if range_start is not None:
            statement = statement.where(Holiday.holiday_date >= range_start)
        if range_end is not None:
            statement = statement.where(Holiday.holiday_date <= range_end)
        return statement

    def _scope(self, state_id: int | None, location_id: int | None):
        national = and_(Holiday.branch_id.is_(None), _STATE.is_(None))
        if location_id is not None:
            branch_state = select(Branch.state_id).where(Branch.id == location_id).scalar_subquery()
            return or_(
                national,
                and_(Holiday.branch_id.is_(None), branch_state == _STATE),
                Holiday.branch_id == location_id,
            )
        if state_id is not None:
            branches = select(Branch.id).where(Branch.state_id == state_id)
            return or_(
                national,
                and_(Holiday.branch_id.is_(None), state_id == _STATE),
                Holiday.branch_id.in_(branches),
            )
        return true()

    def _one(self, holiday_id: int) -> HolidayItem | None:
        statement = self._filtered(HolidaySummaryQuery(active_only=False), start=None, end=None).where(
            Holiday.id == holiday_id
        )
        row = self._db.execute(statement).one_or_none()
        return None if row is None else self._item(row)

    def _item(self, row) -> HolidayItem:
        category = api_category(row.holiday_type, row.state_id, row.branch_id)
        return HolidayItem(
            id=row.id,
            name=row.name,
            holiday_date=row.holiday_date,
            day=_WEEKDAYS[row.holiday_date.weekday()],
            category=category,
            state_id=row.state_id,
            state_name=row.state_name,
            location_id=row.branch_id,
            location_name=row.location_name or "All Locations",
            description=row.description,
            optional=category == "Optional",
            is_active=row.is_active,
            source_notification_no=row.source_notification_no,
            source_notification_date=row.source_notification_date,
            row_version=row.row_version,
        )


def _years(query: HolidaySummaryQuery | HolidayListQuery) -> set[int]:
    years: set[int] = set()
    if query.calendar_year is not None:
        years.add(query.calendar_year)
    if query.financial_year is not None:
        years.add(query.financial_year)
        years.add(query.financial_year + 1)
    return years


def _bounds(financial_year: int | None, calendar_year: int | None) -> tuple[date | None, date | None]:
    start = end = None
    if financial_year is not None:
        start, end = date(financial_year, 4, 1), date(financial_year + 1, 3, 31)
    if calendar_year is not None:
        year_start, year_end = date(calendar_year, 1, 1), date(calendar_year, 12, 31)
        start = year_start if start is None else max(start, year_start)
        end = year_end if end is None else min(end, year_end)
    return start, end
