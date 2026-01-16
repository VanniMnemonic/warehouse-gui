from sqlmodel import select, col
from warehouse.database import get_session
from warehouse.models import User, Withdrawal, Material
from rapidfuzz import process, fuzz, utils

async def get_all_users():
    async with get_session() as session:
        result = await session.execute(select(User))
        return list(result.scalars().all())

async def get_user_withdrawals(user_id: int):
    async with get_session() as session:
        # Join with Material to get denomination
        statement = select(Withdrawal, Material).join(Material).where(Withdrawal.user_id == user_id).order_by(col(Withdrawal.withdrawal_date).desc())
        result = await session.execute(statement)
        # Returns list of (Withdrawal, Material) tuples
        return result.all()

def filter_users(query: str, users: list[User]) -> list[User]:
    if not query:
        return users
    
    choices = [
        f"{user.first_name} {user.last_name} {user.custom_id} {user.title or ''} {user.workplace or ''} {user.code or ''}"
        for user in users
    ]
    
    results = process.extract(query, choices, limit=None, scorer=fuzz.WRatio, processor=utils.default_process)
    
    # results is list of (match_string, score, index) when choices is list
    return [users[index] for match, score, index in results if score > 50]

async def create_user(first_name: str, last_name: str, **kwargs):
    prefix = (first_name[0] + last_name[0]).upper()
    
    async with get_session() as session:
        # Find all users whose custom_id starts with prefix
        # We need to escape % and _ in prefix if they were allowed, but here only letters
        statement = select(User).where(col(User.custom_id).startswith(prefix))
        result = await session.execute(statement)
        existing = result.scalars().all()
        
        count = 1
        new_id = f"{prefix}{count}"
        existing_ids = {u.custom_id for u in existing}
        while new_id in existing_ids:
            count += 1
            new_id = f"{prefix}{count}"
            
        if "code" not in kwargs or kwargs["code"] is None:
            kwargs["code"] = new_id
        user = User(first_name=first_name, last_name=last_name, custom_id=new_id, **kwargs)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def update_user(user_id: int, **kwargs) -> User:
    async with get_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return user
