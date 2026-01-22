import asyncio
from datetime import date, datetime, timedelta
from sqlmodel import select
from warehouse.database import get_session, init_db
from warehouse.models import User, Material, Batch, Withdrawal, MaterialType

async def seed():
    print("Inizializzazione database...")
    await init_db()
    
    async with get_session() as session:
        print("Pulizia dati esistenti (opzionale - commentata per sicurezza)...")
        # Uncomment to clear data before seeding
        # await session.execute(text("DELETE FROM withdrawal"))
        # await session.execute(text("DELETE FROM batch"))
        # await session.execute(text("DELETE FROM material"))
        # await session.execute(text("DELETE FROM user"))
        # await session.commit()

        print("Creazione Utenti...")
        users = [
            User(first_name="Mario", last_name="Rossi", custom_id="MR1", title="Dr.", workplace="Officina A", mobile="3331234567", email="mario.rossi@example.com", notes="Responsabile"),
            User(first_name="Luigi", last_name="Verdi", custom_id="LV1", workplace="Magazzino B"),
            User(first_name="Peach", last_name="Toadstool", custom_id="PT1", title="Principessa", workplace="Castello", notes="VIP"),
        ]
        
        # Check if users exist to avoid duplicates if run multiple times
        for u in users:
            existing = await session.execute(select(User).where(User.custom_id == u.custom_id))
            if not existing.first():
                session.add(u)
        await session.commit()
        
        # Reload users to get IDs
        mario = (await session.execute(select(User).where(User.custom_id == "MR1"))).scalar_one()
        luigi = (await session.execute(select(User).where(User.custom_id == "LV1"))).scalar_one()
        peach = (await session.execute(select(User).where(User.custom_id == "PT1"))).scalar_one()

        print("Creazione Materiali (Oggetti)...")
        items_data = [
            # Efficient Items
            {"denomination": "Trapano Avvitatore", "part_number": "TR-2000", "serial_number": "SN-001", "is_efficient": True},
            {"denomination": "Saldatrice", "part_number": "WELD-X", "serial_number": "SN-002", "is_efficient": True},
            {"denomination": "Multimetro", "part_number": "FLUKE-87", "serial_number": "SN-003", "is_efficient": True},
            {"denomination": "Oscilloscopio", "part_number": "TEK-100", "serial_number": "SN-004", "is_efficient": True},
            
            # Inefficient/Damaged Items
            {"denomination": "Martello Pneumatico", "part_number": "HAMMER-99", "serial_number": "SN-DAMAGED", "is_efficient": False},
            {"denomination": "Generatore di Funzioni", "part_number": "GEN-50", "serial_number": "SN-BROKEN", "is_efficient": False},
        ]
        
        items = []
        for i_data in items_data:
            # Check existence by serial number if present
            stmt = select(Material).where(Material.serial_number == i_data["serial_number"]).where(Material.material_type == MaterialType.ITEM)
            existing = await session.execute(stmt)
            obj = existing.scalar_one_or_none()
            if not obj:
                obj = Material(material_type=MaterialType.ITEM, **i_data)
                session.add(obj)
                await session.commit()
                await session.refresh(obj)
            items.append(obj)
        
        # Unpack for easier reference
        trapano, saldatrice, multimetro, oscilloscopio, martello, generatore = items

        print("Creazione Materiali (Consumabili)...")
        consumables_data = [
            {"denomination": "Viti M4x20", "part_number": "SCREW-M4", "is_efficient": True},
            {"denomination": "Nastro Isolante", "part_number": "TAPE-BLK", "is_efficient": True},
            {"denomination": "Guanti in Lattice", "part_number": "GLOVE-L", "is_efficient": True},
        ]
        
        consumables = []
        for c_data in consumables_data:
            stmt = select(Material).where(Material.denomination == c_data["denomination"]).where(Material.material_type == MaterialType.CONSUMABLE)
            existing = await session.execute(stmt)
            obj = existing.scalar_one_or_none()
            if not obj:
                obj = Material(material_type=MaterialType.CONSUMABLE, **c_data)
                session.add(obj)
                await session.commit()
                await session.refresh(obj)
            consumables.append(obj)
            
        viti, nastro, guanti = consumables

        print("Creazione Lotti...")
        today = date.today()
        batches = [
            # Viti: Expired, Expiring Soon, Valid
            Batch(material_id=viti.id, expiration=today - timedelta(days=40), amount=100, location="Scaffale A1"),
            Batch(material_id=viti.id, expiration=today + timedelta(days=5), amount=200, location="Scaffale A2"),
            Batch(material_id=viti.id, expiration=today + timedelta(days=365), amount=1000, location="Scaffale A3"),
            
            # Nastro: Valid
            Batch(material_id=nastro.id, expiration=today + timedelta(days=700), amount=50, location="Cassetto B1"),
            
            # Guanti: Expired
            Batch(material_id=guanti.id, expiration=today - timedelta(days=1), amount=500, location="Magazzino C"),
        ]
        
        for b in batches:
            # Simple check to avoid massive duplication, though batches are unique entities usually
            # We'll just add them. If you run this script multiple times, you get more batches.
            # To be safe, let's check if a batch with same material and expiration exists
            stmt = select(Batch).where(Batch.material_id == b.material_id).where(Batch.expiration == b.expiration)
            existing = await session.execute(stmt)
            if not existing.first():
                session.add(b)
        await session.commit()

        print("Creazione Prelievi...")
        # 1. Active Withdrawal: Mario -> Saldatrice (Item)
        # Check if already withdrawn
        if not await is_withdrawn(session, saldatrice.id):
            w1 = Withdrawal(
                user_id=mario.id,
                material_id=saldatrice.id,
                amount=1,
                withdrawal_date=datetime.now() - timedelta(days=2),
                notes="Lavoro urgente"
            )
            session.add(w1)

        # 2. Active Withdrawal: Luigi -> Multimetro (Item)
        if not await is_withdrawn(session, multimetro.id):
            w2 = Withdrawal(
                user_id=luigi.id,
                material_id=multimetro.id,
                amount=1,
                withdrawal_date=datetime.now() - timedelta(hours=4),
                notes="Misurazioni"
            )
            session.add(w2)

        # 3. Consumable Withdrawal: Mario -> Viti (50 units)
        # We don't check uniqueness strictly for consumables, but let's avoid spamming if run twice
        # by checking if Mario withdrew Viti recently
        stmt = select(Withdrawal).where(Withdrawal.user_id == mario.id).where(Withdrawal.material_id == viti.id)
        if not (await session.execute(stmt)).first():
            w3 = Withdrawal(
                user_id=mario.id,
                material_id=viti.id,
                amount=50,
                withdrawal_date=datetime.now() - timedelta(days=1),
                notes="Montaggio scaffali"
            )
            session.add(w3)
            # Reduce stock? The controller does it, but here we are seeding directly.
            # We should technically reduce stock from batches if we want consistency.
            # For simplicity in seeding, we might skip logic or implement a simple one.
            # Let's just leave batches as is for now or manually reduce if needed.
            # Since batches were just created, let's assume these withdrawals happened 'before' or just don't touch batches to keep numbers nice.

        # 4. Returned Item: Peach -> Oscilloscopio (Returned Efficient)
        if not await is_withdrawn(session, oscilloscopio.id):
            # Check if there is a past withdrawal record already
            stmt = select(Withdrawal).where(Withdrawal.material_id == oscilloscopio.id).where(Withdrawal.return_date != None)
            if not (await session.execute(stmt)).first():
                w4 = Withdrawal(
                    user_id=peach.id,
                    material_id=oscilloscopio.id,
                    amount=1,
                    withdrawal_date=datetime.now() - timedelta(days=10),
                    return_date=datetime.now() - timedelta(days=5),
                    efficient_at_return=True,
                    notes="Progetto X"
                )
                session.add(w4)

        # 5. Returned Item: Luigi -> Generatore (Returned Damaged)
        # Note: Generatore is already marked is_efficient=False in items creation above.
        if not await is_withdrawn(session, generatore.id):
            stmt = select(Withdrawal).where(Withdrawal.material_id == generatore.id).where(Withdrawal.return_date != None)
            if not (await session.execute(stmt)).first():
                w5 = Withdrawal(
                    user_id=luigi.id,
                    material_id=generatore.id,
                    amount=1,
                    withdrawal_date=datetime.now() - timedelta(days=20),
                    return_date=datetime.now() - timedelta(days=19),
                    efficient_at_return=False,
                    notes="Caduto accidentalmente"
                )
                session.add(w5)

        await session.commit()
        print("Seeding completato!")

async def is_withdrawn(session, material_id):
    # Helper to check if item is currently withdrawn
    stmt = select(Withdrawal).where(Withdrawal.material_id == material_id).where(Withdrawal.return_date == None)
    result = await session.execute(stmt)
    return result.first() is not None

if __name__ == "__main__":
    asyncio.run(seed())
