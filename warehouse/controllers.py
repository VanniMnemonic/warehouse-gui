from sqlmodel import select, col
from warehouse.database import get_session
from warehouse.models import User
from rapidfuzz import process, fuzz, utils

async def get_all_users():
    async with get_session() as session:
        result = await session.execute(select(User))
        return list(result.scalars().all())

def filter_users(query: str, users: list[User]) -> list[User]:
    if not query:
        return users
    
    # Map user objects to search strings
    choices = [f"{user.first_name} {user.last_name} {user.custom_id} {user.title or ''} {user.workplace or ''}" for user in users]
    
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
            
        user = User(first_name=first_name, last_name=last_name, custom_id=new_id, **kwargs)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
