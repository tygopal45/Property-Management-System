"""The one thing a screen needs to know about other people: who the contractors are.

Deliberately narrow. There is no route that lists every user, and no route that returns an email
address or anything else about one — the assignment control needs a name and an id to put in a
dropdown, and that is all this gives it.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_manager
from app.models import Role, User
from app.schemas.auth import ContractorOut

router = APIRouter(prefix="/api/contractors", tags=["contractors"])


@router.get("", response_model=list[ContractorOut])
def list_contractors(
    db: Session = Depends(get_db), _: User = Depends(require_manager)
) -> list[User]:
    """Manager-only, because only a manager can assign. Requirement 5.

    A contractor has no use for it either: the requests they can see already carry the names of
    everyone on them, so listing the workforce would be an extra thing to expose for no gain.
    """
    return list(
        db.scalars(select(User).where(User.role == Role.contractor).order_by(User.name))
    )
