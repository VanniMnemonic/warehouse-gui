from sqlmodel import select, col
from warehouse.database import get_session
from warehouse.models import User, Withdrawal, Material, Batch, MaterialType
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
        f"{user.first_name or ''} {user.last_name or ''} {user.custom_id or ''} {user.title or ''} {user.workplace or ''} {user.code or ''} {user.notes or ''} {user.email or ''} {user.mobile or ''}"
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


async def get_user_dependencies(user_id: int) -> int:
    """Returns the number of withdrawals associated with the user."""
    async with get_session() as session:
        statement = select(Withdrawal).where(Withdrawal.user_id == user_id)
        result = await session.execute(statement)
        return len(result.scalars().all())


async def delete_user(user_id: int):
    """Deletes a user and their associated withdrawals."""
    async with get_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        
        # Delete withdrawals first
        statement = select(Withdrawal).where(Withdrawal.user_id == user_id)
        result = await session.execute(statement)
        withdrawals = result.scalars().all()
        for w in withdrawals:
            await session.delete(w)
            
        await session.delete(user)
        await session.commit()



async def create_withdrawal(
    user_id: int,
    material_id: int,
    amount: int,
    notes: str | None = None,
    return_date=None,
    efficient_at_return: bool | None = None,
) -> Withdrawal:
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    async with get_session() as session:
        # Check material type and stock for consumables
        material = await session.get(Material, material_id)
        if not material:
            raise ValueError("Material not found")

        if material.material_type == MaterialType.ITEM:
            # Check if item is already withdrawn (active withdrawal exists)
            active_withdrawal_stmt = select(Withdrawal).where(
                Withdrawal.material_id == material_id,
                Withdrawal.return_date == None
            )
            result = await session.execute(active_withdrawal_stmt)
            if result.scalars().first():
                raise ValueError(f"L'oggetto '{material.denomination}' è già stato prelevato e non ancora restituito.")

        if material.material_type == MaterialType.CONSUMABLE:
            # Get batches sorted by expiration (FEFO)
            statement = select(Batch).where(Batch.material_id == material_id).where(Batch.amount > 0).order_by(Batch.expiration)
            result = await session.execute(statement)
            batches = result.scalars().all()
            
            total_stock = sum(b.amount for b in batches)
            if total_stock < amount:
                raise ValueError(f"Insufficient stock. Available: {total_stock}, Requested: {amount}")
            
            remaining_to_withdraw = amount
            for batch in batches:
                if remaining_to_withdraw <= 0:
                    break
                
                deduct = min(batch.amount, remaining_to_withdraw)
                batch.amount -= deduct
                remaining_to_withdraw -= deduct
                session.add(batch)
                
        withdrawal = Withdrawal(
            user_id=user_id,
            material_id=material_id,
            amount=amount,
            notes=notes,
            return_date=return_date,
            efficient_at_return=efficient_at_return,
        )
        session.add(withdrawal)
        await session.commit()
        await session.refresh(withdrawal)
        return withdrawal


async def get_all_withdrawals():
    async with get_session() as session:
        statement = select(Withdrawal, User, Material).join(User).join(Material).order_by(col(Withdrawal.withdrawal_date).desc())
        result = await session.execute(statement)
        # Returns list of (Withdrawal, User, Material) tuples
        return result.all()


async def return_withdrawal_item(withdrawal_id: int, efficient: bool) -> Withdrawal:
    from datetime import datetime
    async with get_session() as session:
        withdrawal = await session.get(Withdrawal, withdrawal_id)
        if not withdrawal:
            raise ValueError("Withdrawal not found")
        
        withdrawal.return_date = datetime.now()
        withdrawal.efficient_at_return = efficient
        session.add(withdrawal)
        
        # Update material efficiency status
        material = await session.get(Material, withdrawal.material_id)
        if material:
            material.is_efficient = efficient
            session.add(material)
            
        await session.commit()
        await session.refresh(withdrawal)
        return withdrawal

async def get_active_item_withdrawals() -> set[int]:
    async with get_session() as session:
        # Get material_ids of withdrawals that haven't been returned yet
        statement = select(Withdrawal.material_id).where(
            Withdrawal.return_date == None
        )
        result = await session.execute(statement)
        return set(result.scalars().all())
