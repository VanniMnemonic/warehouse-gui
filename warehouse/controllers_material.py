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
    image_path: str | None = None
):
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
        return material


async def update_material(material_id: int, **kwargs) -> Material:
    async with get_session() as session:
        material = await session.get(Material, material_id)
        if material is None:
            raise ValueError("Material not found")
        for key, value in kwargs.items():
            if hasattr(material, key):
                setattr(material, key, value)
        await session.commit()
        await session.refresh(material)
        return material
