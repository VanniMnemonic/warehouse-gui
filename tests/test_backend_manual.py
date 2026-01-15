import asyncio
import os
from warehouse.database import init_db, get_session
from warehouse.controllers import create_user, get_all_users, filter_users
from warehouse.models import User

async def main():
    print("Initializing DB...")
    await init_db()
    
    print("Creating Users...")
    u1 = await create_user("Mario", "Rossi", workplace="Office", title="Mr")
    print(f"Created: {u1.custom_id} - {u1.first_name} {u1.last_name}")
    
    u2 = await create_user("Mario", "Bianchi", workplace="Factory")
    print(f"Created: {u2.custom_id} - {u2.first_name} {u2.last_name}")
    
    u3 = await create_user("Stefano", "Verdi")
    print(f"Created: {u3.custom_id} - {u3.first_name} {u3.last_name}")
    
    print("\nListing all users:")
    users = await get_all_users()
    for u in users:
        print(f" - {u.custom_id}: {u.first_name} {u.last_name}")
        
    print("\nFuzzy Search 'Mario':")
    results = filter_users("Mario", users)
    for u in results:
        print(f" - Found: {u.first_name} {u.last_name}")

    print("\nFuzzy Search 'MR':")
    results = filter_users("MR", users)
    for u in results:
        print(f" - Found: {u.first_name} {u.last_name} ({u.custom_id})")

if __name__ == "__main__":
    # Clean up old db
    if os.path.exists("warehouse.db"):
        os.remove("warehouse.db")
        
    asyncio.run(main())
