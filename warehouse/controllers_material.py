from sqlmodel import select, col
from warehouse.database import get_session
from warehouse.models import Material, MaterialType, Batch, Withdrawal, User

async def get_materials(material_type: MaterialType):
    async with get_session() as session:
        statement = select(Material).where(Material.material_type == material_type)
        result = await session.execute(statement)
        return list(result.scalars().all())

async def get_material_batches(material_id: int):
    async with get_session() as session:
        statement = select(Batch).where(Batch.material_id == material_id).order_by(Batch.expiration)
        result = await session.execute(statement)
        return list(result.scalars().all())

async def get_material_withdrawals(material_id: int):
    async with get_session() as session:
        # Join with User to get names
        statement = select(Withdrawal, User).join(User).where(Withdrawal.material_id == material_id).order_by(col(Withdrawal.withdrawal_date).desc())
        result = await session.execute(statement)
        return result.all()

async def create_material(
    material_type: MaterialType,
    denomination: str,
    ndc: str | None = None,
    part_number: str | None = None,
    serial_number: str | None = None,
    code: str | None = None,
    image_path: str | None = None,
    location: str | None = None
):
    from datetime import date
    async with get_session() as session:
        material = Material(
            material_type=material_type,
            denomination=denomination,
            ndc=ndc,
            part_number=part_number,
            serial_number=serial_number,
            code=code,
            image_path=image_path
        )
        session.add(material)
        await session.commit()
        await session.refresh(material)
        
        # If ITEM, create initial batch with location
        if material_type == MaterialType.ITEM:
             batch = Batch(
                material_id=material.id,
                expiration=date(9999, 12, 31),
                amount=1,
                location=location
            )
             session.add(batch)
             await session.commit()
        
        return material


async def get_expiring_batches(limit: int = 50):
    """
    Returns active batches (amount > 0) sorted by expiration date (ascending).
    Joins with Material to provide context.
    """
    async with get_session() as session:
        statement = (
            select(Batch, Material)
            .join(Material)
            .where(Batch.amount > 0)
            .order_by(Batch.expiration)
            .limit(limit)
        )
        result = await session.execute(statement)
        return result.all()


async def get_inefficient_materials():
    """
    Returns materials of type ITEM that are marked as inefficient.
    """
    async with get_session() as session:
        statement = select(Material).where(
            Material.material_type == MaterialType.ITEM,
            Material.is_efficient == False
        )
        result = await session.execute(statement)
        return result.scalars().all()


async def create_batch(
    material_id: int,
    expiration: "date",
    amount: int,
    location: str | None = None
) -> Batch:
    async with get_session() as session:
        batch = Batch(
            material_id=material_id,
            expiration=expiration,
            amount=amount,
            location=location
        )
        session.add(batch)
        await session.commit()
        await session.refresh(batch)
        return batch


async def update_material(material_id: int, **kwargs) -> Material:
    async with get_session() as session:
        material = await session.get(Material, material_id)
        if material is None:
            raise ValueError("Material not found")
            
        location_update = None
        if "location" in kwargs:
            location_update = kwargs.pop("location")
            
        for key, value in kwargs.items():
            if hasattr(material, key):
                setattr(material, key, value)
        
        session.add(material)
        
        if location_update is not None and material.material_type == MaterialType.ITEM:
            # Update the single batch location
            statement = select(Batch).where(Batch.material_id == material_id).limit(1)
            result = await session.execute(statement)
            batch = result.scalars().first()
            if batch:
                batch.location = location_update
                session.add(batch)
        
        await session.commit()
        await session.refresh(material)
        return material
