"""Import all models so Alembic can detect them for migrations."""

from app.models.account import Account
from app.models.user import User
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.import_record import ImportRecord
from app.models.import_template import ImportTemplate
from app.models.activity import Activity

__all__ = [
    "Account",
    "User",
    "Customer",
    "Invoice",
    "ImportRecord",
    "ImportTemplate",
    "Activity",
]
