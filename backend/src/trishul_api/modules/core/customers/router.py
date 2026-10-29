from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.core.customers.repository import CustomerRepository
from trishul_api.modules.core.customers.schemas import (
    CustomerCreate,
    CustomerDetail,
    CustomerFormOptions,
    CustomerListItem,
    CustomerQuery,
    CustomerUpdate,
)
from trishul_api.modules.core.customers.service import CustomerService

router = APIRouter(prefix="/core", tags=["customers"])

CAN_VIEW = Depends(require_permission("core.customer.view", "core.customer.manage"))
CAN_MANAGE = Depends(require_permission("core.customer.manage"))

CustomerId = Annotated[int, Path(alias="customerId")]


def get_customer_service(db: DbSession) -> CustomerService:
    return CustomerService(db)


def get_customer_repository(db: DbSession) -> CustomerRepository:
    return CustomerRepository(db)


Customers = Annotated[CustomerService, Depends(get_customer_service)]
CustomerRepo = Annotated[CustomerRepository, Depends(get_customer_repository)]


@router.get("/customers", summary="Customers, filtered and paged", dependencies=[CAN_VIEW])
def list_customers(query: Annotated[CustomerQuery, Query()], repo: CustomerRepo) -> Page[CustomerListItem]:
    return repo.search(query)


# Declared before /customers/{customerId} so "form-options" is not parsed as a customer id.
@router.get("/customers/form-options", summary="Dropdown values for the customer form", dependencies=[CAN_MANAGE])
def get_customer_form_options(repo: CustomerRepo) -> CustomerFormOptions:
    return CustomerFormOptions(companies=repo.companies(), states=repo.states())


@router.get("/customers/{customerId}", summary="One customer", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE)
def get_customer(customer_id: CustomerId, customers: Customers) -> CustomerDetail:
    return customers.get(customer_id)


@router.post("/customers", summary="Add a customer", status_code=201, dependencies=[CAN_MANAGE])
def create_customer(
    data: CustomerCreate, actor: CurrentUserDep, customers: Customers, response: Response
) -> CustomerDetail:
    created = customers.create(actor, data)
    response.headers["Location"] = f"customers/{created.id}"
    return created


@router.patch(
    "/customers/{customerId}",
    summary="Change a customer's details",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_customer(
    customer_id: CustomerId,
    data: CustomerUpdate,
    actor: CurrentUserDep,
    customers: Customers,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> CustomerDetail:
    return customers.update(actor, customer_id, row_version, data)


@router.post(
    "/customers/{customerId}/deactivate",
    summary="Mark a customer inactive",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_customer(customer_id: CustomerId, actor: CurrentUserDep, customers: Customers) -> CustomerDetail:
    return customers.deactivate(actor, customer_id)


@router.post(
    "/customers/{customerId}/activate",
    summary="Mark a customer active again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_customer(customer_id: CustomerId, actor: CurrentUserDep, customers: Customers) -> CustomerDetail:
    return customers.activate(actor, customer_id)
