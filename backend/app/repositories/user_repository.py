from sqlalchemy import func, or_, select

from app.domain.pagination import PageRequest, PageResult
from app.models import Role, User
from app.repositories.base import BaseRepository
from app.schemas.users import UserFilter


class UserRepository(BaseRepository[User]):
    model = User
    sortable = {  # noqa: RUF012
        "username": User.username,
        "full_name": User.full_name,
        "created_at": User.created_at,
        "last_login_at": User.last_login_at,
    }
    default_sort = (User.full_name,)

    def find_by_username(self, username: str) -> User | None:
        return self.session.scalar(
            select(User).where(func.lower(User.username) == username.lower())
        )

    def exists_with_email(self, email: str, *, exclude_id: int | None = None) -> bool:
        statement = select(User.id).where(func.lower(User.email) == email.lower())
        if exclude_id is not None:
            statement = statement.where(User.id != exclude_id)
        return self.session.scalar(statement) is not None

    def search(self, filters: UserFilter, page: PageRequest) -> PageResult[User]:
        statement = select(User).join(User.role)
        if filters.role:
            statement = statement.where(Role.code == filters.role)
        if filters.is_active is not None:
            statement = statement.where(User.is_active == filters.is_active)
        if filters.q:
            pattern = f"%{filters.q.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(User.username).like(pattern),
                    func.lower(User.full_name).like(pattern),
                    func.lower(User.email).like(pattern),
                )
            )
        return self.paginate(statement, page)


class RoleRepository(BaseRepository[Role]):
    model = Role

    def find_by_code(self, code: str) -> Role | None:
        return self.session.scalar(select(Role).where(Role.code == code))

    def list_all(self) -> list[Role]:
        return list(self.session.scalars(select(Role).order_by(Role.id)))
