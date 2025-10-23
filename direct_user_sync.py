"""
Direct PostgreSQL database sync: GCGC → TMS-server

This script directly copies user data from GCGC database to TMS-server database.
Much faster and more reliable than going through APIs.

GCGC Database: postgresql://postgres:ZAKIaIlaORvpkTWPzoCQWLnhlACfVMpq@nozomi.proxy.rlwy.net:59385/railway
TMS Database:  postgresql://postgres:dMlNKvaGqxIiiBFljALbCbMdxFdRduGj@maglev.proxy.rlwy.net:34372/railway

Usage:
    python direct_user_sync.py
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Database connections
GCGC_DB = {
    "host": "nozomi.proxy.rlwy.net",
    "port": 59385,
    "user": "postgres",
    "password": "ZAKIaIlaORvpkTWPzoCQWLnhlACfVMpq",
    "database": "railway"
}

TMS_DB = {
    "host": "maglev.proxy.rlwy.net",
    "port": 34372,
    "user": "postgres",
    "password": "dMlNKvaGqxIiiBFljALbCbMdxFdRduGj",
    "database": "railway"
}


def sync_users():
    """Sync all active users from GCGC to TMS-server."""
    print("=" * 80)
    print("🔄 Starting Direct Database Sync: GCGC → TMS-server")
    print("=" * 80)

    gcgc_conn = None
    tms_conn = None

    try:
        # Connect to GCGC database
        print("\n📡 Connecting to GCGC database...")
        gcgc_conn = psycopg2.connect(**GCGC_DB)
        gcgc_cursor = gcgc_conn.cursor(cursor_factory=RealDictCursor)

        # Connect to TMS-server database
        print("📡 Connecting to TMS-server database...")
        tms_conn = psycopg2.connect(**TMS_DB)
        tms_cursor = tms_conn.cursor()

        # Fetch all active users from GCGC
        print("\n📥 Fetching users from GCGC...")
        gcgc_cursor.execute("""
            SELECT
                id,
                email,
                username,
                name,
                "firstName",
                "lastName",
                "middleName",
                image,
                "contactNumber",
                role,
                "positionTitle",
                division,
                department,
                section,
                "customTeam",
                "hierarchyLevel",
                "reportsToId",
                "isActive",
                "isLeader"
            FROM users
            WHERE "isActive" = true
            ORDER BY email
        """)

        gcgc_users = gcgc_cursor.fetchall()
        print(f"✅ Found {len(gcgc_users)} active users in GCGC")

        # Sync each user to TMS-server
        synced = 0
        failed = 0

        for user in gcgc_users:
            try:
                # Handle name splitting
                full_name = user['name'] or ""
                first_name = user['firstName'] or (full_name.split(" ", 1)[0] if full_name else None)
                last_name = user['lastName'] or (full_name.split(" ", 1)[1] if " " in full_name else None)

                print(f"\n👤 Syncing: {user['email']}")
                print(f"   GCGC username: '{user['username']}'")
                print(f"   Name: {first_name} {last_name}")
                print(f"   Position: {user['positionTitle']}")
                print(f"   Division: {user['division']}")

                # UPSERT into TMS-server
                tms_cursor.execute("""
                    INSERT INTO users (
                        tms_user_id,
                        email,
                        username,
                        first_name,
                        last_name,
                        middle_name,
                        image,
                        contact_number,
                        role,
                        position_title,
                        division,
                        department,
                        section,
                        custom_team,
                        hierarchy_level,
                        reports_to_id,
                        is_active,
                        is_leader,
                        last_synced_at,
                        created_at,
                        updated_at,
                        settings_json
                    ) VALUES (
                        %(tms_user_id)s,
                        %(email)s,
                        %(username)s,
                        %(first_name)s,
                        %(last_name)s,
                        %(middle_name)s,
                        %(image)s,
                        %(contact_number)s,
                        %(role)s,
                        %(position_title)s,
                        %(division)s,
                        %(department)s,
                        %(section)s,
                        %(custom_team)s,
                        %(hierarchy_level)s,
                        %(reports_to_id)s,
                        %(is_active)s,
                        %(is_leader)s,
                        %(last_synced_at)s,
                        NOW(),
                        NOW(),
                        '{}'::json
                    )
                    ON CONFLICT (tms_user_id)
                    DO UPDATE SET
                        email = EXCLUDED.email,
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        middle_name = EXCLUDED.middle_name,
                        image = EXCLUDED.image,
                        contact_number = EXCLUDED.contact_number,
                        role = EXCLUDED.role,
                        position_title = EXCLUDED.position_title,
                        division = EXCLUDED.division,
                        department = EXCLUDED.department,
                        section = EXCLUDED.section,
                        custom_team = EXCLUDED.custom_team,
                        hierarchy_level = EXCLUDED.hierarchy_level,
                        reports_to_id = EXCLUDED.reports_to_id,
                        is_active = EXCLUDED.is_active,
                        is_leader = EXCLUDED.is_leader,
                        last_synced_at = EXCLUDED.last_synced_at,
                        updated_at = NOW()
                """, {
                    "tms_user_id": user['id'],
                    "email": user['email'],
                    "username": user['username'],
                    "first_name": first_name,
                    "last_name": last_name,
                    "middle_name": user['middleName'],
                    "image": user['image'],
                    "contact_number": user['contactNumber'],
                    "role": user['role'],
                    "position_title": user['positionTitle'],
                    "division": user['division'],
                    "department": user['department'],
                    "section": user['section'],
                    "custom_team": user['customTeam'],
                    "hierarchy_level": user['hierarchyLevel'],
                    "reports_to_id": user['reportsToId'],
                    "is_active": user['isActive'],
                    "is_leader": user['isLeader'],
                    "last_synced_at": datetime.utcnow()
                })

                synced += 1
                print(f"   ✅ Synced successfully")

            except Exception as e:
                failed += 1
                print(f"   ❌ Failed: {e}")
                continue

        # Commit all changes
        tms_conn.commit()

        print("\n" + "=" * 80)
        print("✅ Sync Complete!")
        print(f"   Total users: {len(gcgc_users)}")
        print(f"   Synced: {synced}")
        print(f"   Failed: {failed}")
        print("=" * 80)

        # Verify sync
        print("\n🔍 Verifying sync...")
        tms_cursor.execute("""
            SELECT email, username, first_name, last_name, position_title, division, contact_number
            FROM users
            WHERE email IN ('kim@gmail.com', 'zms@gmail.com')
            ORDER BY email
        """)

        verification = tms_cursor.fetchall()
        print("\n📊 Sample verification (TMS-server database):")
        for row in verification:
            print(f"   Email: {row[0]}")
            print(f"   Username: {row[1]}")
            print(f"   Name: {row[2]} {row[3]}")
            print(f"   Position: {row[4]}")
            print(f"   Division: {row[5]}")
            print(f"   Contact: {row[6]}")
            print()

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        if tms_conn:
            tms_conn.rollback()
        raise

    finally:
        # Close connections
        if gcgc_conn:
            gcgc_conn.close()
            print("📡 Closed GCGC connection")
        if tms_conn:
            tms_conn.close()
            print("📡 Closed TMS-server connection")


if __name__ == "__main__":
    sync_users()
