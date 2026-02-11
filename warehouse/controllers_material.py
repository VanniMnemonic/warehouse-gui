from sqlmodel import select, col, func
from datetime import date, timedelta
from warehouse.database import get_session
from warehouse.models import Material, MaterialType, Batch, Withdrawal, User, EventType
from warehouse.controllers_log import create_log_entry

async def get_materials(material_type: MaterialType):
    async with get_session() as session:
        statement = select(Material).where(Material.material_type == material_type)
        result = await session.execute(statement)
        return list(result.scalars().all())

async def get_material_stocks() -> dict[int, int]:
    """Returns a dictionary of material_id -> total_stock for ALL materials (Consumables and Items)."""
    async with get_session() as session:
        statement = (
            select(Batch.material_id, func.sum(Batch.amount))
            .join(Material)
            # Removed filter: .where(Material.material_type == MaterialType.CONSUMABLE)
            .group_by(Batch.material_id)
        )
        result = await session.execute(statement)
        # Result rows are (material_id, total_amount)
        # Note: func.sum might return None if no batches, but inner join ensures matches.
        # However, if a material has NO batches, it won't be in the result.
        return {row[0]: (row[1] or 0) for row in result.all()}


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
    location: str | None = None,
    min_stock: int = 0
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
            image_path=image_path,
            min_stock=min_stock
        )
        session.add(material)
        await session.commit()
        await session.refresh(material)
        
        # Log event
        type_str = "Attrezzatura" if material_type == MaterialType.ITEM else "Consumabile"
        await create_log_entry(
            event_type=EventType.MATERIAL_CREATED,
            description=f"Creato {type_str}: {denomination}"
        )
        
        # If ITEM, create initial batch with location ONLY IF batch data not provided manually in form
        # (The form now exposes batch fields for ITEM too, so if the user filled them, `create_batch` logic in form handler is used)
        # Wait, create_material is called by the form handler.
        # The form handler (MaterialForm.accept_data) calls create_material AND THEN calls create_batch if batch fields are filled.
        # So we should REMOVE the automatic 1-item batch creation here to avoid duplicates if the user adds a batch manually.
        # AND if the user DOESN'T add a batch manually, we might want to default to 1?
        # But if we support Batches properly, we should let the user decide.
        # If I remove this block, and the user leaves batch empty, Stock will be 0.
        # This is consistent with Consumables.
        
        # if material_type == MaterialType.ITEM:
        #      batch = Batch(
        #         material_id=material.id,
        #         expiration=date(9999, 12, 31),
        #         amount=1,
        #         location=location
        #     )
        #      session.add(batch)
        #      await session.commit()
        
        return material


async def get_expiring_batches(limit: int = 50, days_threshold: int = 30):
    """
    Returns active batches (amount > 0) of CONSUMABLES sorted by expiration date (ascending).
    Only includes batches expiring within 'days_threshold' days (or already expired).
    Joins with Material to provide context.
    """
    today = date.today()
    limit_date = today + timedelta(days=days_threshold)
    
    async with get_session() as session:
        statement = (
            select(Batch, Material)
            .join(Material)
            .where(Batch.amount > 0)
            .where(Material.material_type == MaterialType.CONSUMABLE)
            .where(Batch.expiration <= limit_date)
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


async def get_low_stock_materials():
    """
    Returns a list of (Material, current_stock) for ALL materials where current_stock <= min_stock.
    Only considers materials with min_stock > 0.
    """
    async with get_session() as session:
        # Subquery for stock sums
        stock_subquery = (
            select(Batch.material_id, func.sum(Batch.amount).label("total_stock"))
            .group_by(Batch.material_id)
            .subquery()
        )
        
        # Join Material with stock
        # Left join because if no batches, stock is None (0)
        stmt = (
            select(Material, func.coalesce(stock_subquery.c.total_stock, 0).label("stock"))
            .outerjoin(stock_subquery, Material.id == stock_subquery.c.material_id)
            .where(
                # Removed filter: Material.material_type == MaterialType.CONSUMABLE,
                Material.min_stock > 0,
                func.coalesce(stock_subquery.c.total_stock, 0) <= Material.min_stock
            )
        )
        
        results = await session.execute(stmt)
        return results.all()


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
        
        # Log event
        material = await session.get(Material, material_id)
        mat_name = material.denomination if material else "???"
        await create_log_entry(
            event_type=EventType.BATCH_CREATED,
            description=f"Nuovo lotto per {mat_name}: Qtà {amount}, Scad {expiration}"
        )
        
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
        
        # Log event
        await create_log_entry(
            event_type=EventType.MATERIAL_UPDATED,
            description=f"Aggiornato materiale: {material.denomination}"
        )
        
        return material


async def get_material_dependencies(material_id: int) -> tuple[int, int]:
    """Returns a tuple (batch_count, withdrawal_count) associated with the material."""
    async with get_session() as session:
        # Count batches
        batch_stmt = select(Batch).where(Batch.material_id == material_id)
        batch_res = await session.execute(batch_stmt)
        batch_count = len(batch_res.scalars().all())
        
        # Count withdrawals
        withdrawal_stmt = select(Withdrawal).where(Withdrawal.material_id == material_id)
        withdrawal_res = await session.execute(withdrawal_stmt)
        withdrawal_count = len(withdrawal_res.scalars().all())
        
        return batch_count, withdrawal_count


async def delete_material(material_id: int):
    """Deletes a material and its associated batches and withdrawals."""
    async with get_session() as session:
        material = await session.get(Material, material_id)
        if not material:
            raise ValueError("Material not found")
        
        # Delete withdrawals
        w_stmt = select(Withdrawal).where(Withdrawal.material_id == material_id)
        w_res = await session.execute(w_stmt)
        for w in w_res.scalars().all():
            await session.delete(w)
            
        # Delete batches
        b_stmt = select(Batch).where(Batch.material_id == material_id)
        b_res = await session.execute(b_stmt)
        for b in b_res.scalars().all():
            await session.delete(b)
            
        # Log event (must be done before delete or capture name before)
        mat_name = material.denomination
        
        await session.delete(material)
        await session.commit()
        
        await create_log_entry(
            event_type=EventType.MATERIAL_DELETED,
            description=f"Eliminato materiale: {mat_name}"
        )

