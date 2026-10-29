"""Customer master management (core.customer): list, view, add, update and activate/deactivate.

Customer code is unique across all customers (UX_core_customer_code); this checks it up front for a
clear error and still catches a concurrent duplicate on commit. core.customer is an audited table, so
every write is recorded in core.audit_log through the session's audit context.
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import Company, Customer, State
from trishul_api.modules.core.customers.repository import CustomerRepository
from trishul_api.modules.core.customers.schemas import CustomerCreate, CustomerDetail, CustomerUpdate

_DUPLICATE = "Another customer already has this code."
# Fields copied straight from the request to the row (code and email are handled separately).
_PLAIN_FIELDS = (
    "name",
    "customer_type",
    "company_id",
    "primary_phone",
    "alternate_phone",
    "pan",
    "gstin",
    "gst_registration_type",
    "billing_address",
    "billing_state_id",
    "priority_tier",
    "is_asc_customer",
)


class CustomerService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = CustomerRepository(db)

    def get(self, customer_id: int) -> CustomerDetail:
        self._require(customer_id)
        return self._detail(customer_id)

    def create(self, actor: CurrentUser, data: CustomerCreate) -> CustomerDetail:
        code = data.code.strip()
        self._check_unique_code(code, None)
        self._check_references(data)

        customer = Customer(
            code=code,
            email=str(data.email) if data.email else None,
            created_by_user_id=actor.id,
            **{field: getattr(data, field) for field in _PLAIN_FIELDS},
        )
        self._repo.add(customer)
        new_id = self._save(customer)
        return self._detail(new_id)

    def update(
        self, actor: CurrentUser, customer_id: int, expected_row_version: bytes, data: CustomerUpdate
    ) -> CustomerDetail:
        customer = self._require(customer_id)
        check_row_version(customer.row_version, expected_row_version)
        changed = data.model_fields_set

        if "code" in changed and data.code:
            code = data.code.strip()
            self._check_unique_code(code, customer.id)
            customer.code = code
        if "email" in changed:
            customer.email = str(data.email) if data.email else None
        self._check_references(data)
        for field in _PLAIN_FIELDS:
            if field in changed:
                setattr(customer, field, getattr(data, field))

        self._touch(customer, actor)
        self._save(customer)
        return self._detail(customer_id)

    def deactivate(self, actor: CurrentUser, customer_id: int) -> CustomerDetail:
        customer = self._require(customer_id)
        if customer.is_active:
            customer.is_active = False
            self._touch(customer, actor)
            self._db.commit()
        return self._detail(customer_id)

    def activate(self, actor: CurrentUser, customer_id: int) -> CustomerDetail:
        customer = self._require(customer_id)
        if not customer.is_active:
            customer.is_active = True
            self._touch(customer, actor)
            self._db.commit()
        return self._detail(customer_id)

    # ------------------------------------------------------------------ helpers

    def _require(self, customer_id: int) -> Customer:
        customer = self._repo.get(customer_id)
        if customer is None:
            raise NotFound("Customer not found.")
        return customer

    def _detail(self, customer_id: int) -> CustomerDetail:
        return CustomerDetail.model_validate(self._repo.detail_row(customer_id))

    def _save(self, customer: Customer) -> int:
        try:
            self._repo.flush()
            customer_id = customer.id
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(_DUPLICATE) from error
        return customer_id

    def _check_unique_code(self, code: str, customer_id: int | None) -> None:
        owner = self._repo.code_owner(code)
        if owner is not None and owner != customer_id:
            raise AlreadyExists(f"Customer code '{code}' is already in use.")

    def _check_references(self, data: CustomerCreate | CustomerUpdate) -> None:
        changed = data.model_fields_set
        errors: dict[str, list[str]] = {}
        if "company_id" in changed and data.company_id is not None and self._repo.missing(Company, [data.company_id]):
            errors["companyId"] = [f"Unknown or inactive company {data.company_id}"]
        # States are a fixed master with no active flag; check existence only.
        if (
            "billing_state_id" in changed
            and data.billing_state_id is not None
            and self._repo.missing(State, [data.billing_state_id], active=False)
        ):
            errors["billingStateId"] = [f"Unknown state {data.billing_state_id}"]
        if errors:
            raise ApiError("Some of the selected references don't exist.", errors=errors)

    @staticmethod
    def _touch(customer: Customer, actor: CurrentUser) -> None:
        customer.updated_at = datetime.now(UTC).replace(tzinfo=None)
        customer.updated_by_user_id = actor.id
