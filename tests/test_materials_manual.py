import asyncio
import os
from datetime import date, datetime

from warehouse.database import init_db, get_session
from warehouse.controllers import create_user
from warehouse.controllers_material import create_material, get_materials
from warehouse.models import MaterialType, Batch, Withdrawal


async def main():
    print("Initializing DB...")
    await init_db()

    print("Creating mock Users...")
    u1 = await create_user(
        "Mario",
        "Rossi",
        title="Dr",
        workplace="Pronto Soccorso",
        mobile="3330000001",
        email="mario.rossi@example.com",
    )
    u2 = await create_user(
        "Giulia",
        "Bianchi",
        title="Infermiere",
        workplace="Reparto Chirurgia",
        mobile="3330000002",
        email="giulia.bianchi@example.com",
    )
    u3 = await create_user(
        "Stefano",
        "Verdi",
        title="Tecnico",
        workplace="Magazzino",
        mobile="3330000003",
        email="stefano.verdi@example.com",
    )

    print("Created Users:")
    for u in (u1, u2, u3):
        print(f" - {u.custom_id}: {u.first_name} {u.last_name} [{u.workplace or ''}]")

    print("\nCreating mock Consumables...")
    c_mask = await create_material(
        material_type=MaterialType.CONSUMABLE,
        denomination="Mascherina chirurgica",
        ndc="CNS-0001",
        part_number="MSK-CHIR-001",
        serial_number=None,
        code="MASK001",
    )
    c_gloves = await create_material(
        material_type=MaterialType.CONSUMABLE,
        denomination="Guanti in nitrile M",
        ndc="CNS-0002",
        part_number="GNT-NIT-M",
        serial_number=None,
        code="GLOVE_M",
    )
    c_syringes = await create_material(
        material_type=MaterialType.CONSUMABLE,
        denomination="Siringhe monouso 5ml",
        ndc="CNS-0003",
        part_number="SRG-5ML",
        serial_number=None,
        code="SYRINGE5",
    )

    print("Creating mock Items...")
    i_defib = await create_material(
        material_type=MaterialType.ITEM,
        denomination="Defibrillatore portatile",
        ndc="ITM-0001",
        part_number="DEF-PORT-01",
        serial_number="SN-DEF-0001",
        code="DEFIB01",
    )
    i_pump = await create_material(
        material_type=MaterialType.ITEM,
        denomination="Pompa infusione",
        ndc="ITM-0002",
        part_number="PMP-INF-01",
        serial_number="SN-PMP-0001",
        code="PUMP01",
    )
    i_monitor = await create_material(
        material_type=MaterialType.ITEM,
        denomination="Monitor multiparametrico",
        ndc="ITM-0003",
        part_number="MON-MULTI-01",
        serial_number="SN-MON-0001",
        code="MON01",
    )

    print("\nCreating mock Batches and Withdrawals...")
    async with get_session() as session:
        b1 = Batch(
            material_id=c_mask.id,
            expiration=date(2026, 1, 1),
            amount=500,
            location="Magazzino A - Scaffale 1",
        )
        b2 = Batch(
            material_id=c_gloves.id,
            expiration=date(2025, 6, 30),
            amount=1000,
            location="Magazzino A - Scaffale 2",
        )
        b3 = Batch(
            material_id=c_syringes.id,
            expiration=date(2027, 12, 31),
            amount=2000,
            location="Magazzino B - Scaffale 3",
        )
        session.add_all([b1, b2, b3])
        await session.commit()
        await session.refresh(b1)
        await session.refresh(b2)
        await session.refresh(b3)

        w1 = Withdrawal(
            user_id=u1.id,
            material_id=c_mask.id,
            amount=10,
            notes="Utilizzo reparto PS",
        )
        w2 = Withdrawal(
            user_id=u2.id,
            material_id=c_gloves.id,
            amount=50,
            notes="Uso sala operatoria",
        )
        w3 = Withdrawal(
            user_id=u3.id,
            material_id=i_defib.id,
            amount=1,
            withdrawal_date=datetime.now(),
            return_date=None,
            efficient_at_return=None,
            notes="Defibrillatore assegnato a carrello emergenza",
        )
        session.add_all([w1, w2, w3])
        await session.commit()

    print("\nListing Consumables:")
    consumables = await get_materials(MaterialType.CONSUMABLE)
    for m in consumables:
        print(f" - {m.denomination} ({m.part_number or ''}) [{m.code or ''}]")

    print("\nListing Items:")
    items = await get_materials(MaterialType.ITEM)
    for m in items:
        print(f" - {m.denomination} ({m.part_number or ''}) [{m.code or ''}]")


if __name__ == "__main__":
    if os.path.exists("warehouse.db"):
        os.remove("warehouse.db")
    asyncio.run(main())
