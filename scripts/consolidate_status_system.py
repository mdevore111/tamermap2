#!/usr/bin/env python3
"""
Separate retailer status concerns by adding a dedicated 'active' field.
This script will:
1. Add a new 'active' field (BOOLEAN: 1 = active, 0 = inactive)
2. Set active=1 for all retailers by default
3. Set active=0 for retailers that should be inactive (enabled=0 or specific statuses)
4. Keep the existing 'status' field for business logic (new, updated, etc.)
5. Remove the redundant 'enabled' field
6. Create clear separation of concerns
"""

import sqlite3
import os
import sys

def separate_status_concerns(db_path):
    """Separate status concerns by adding a dedicated 'active' field."""
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting status concern separation...")
        
        # First, let's see what we're working with
        cursor.execute("SELECT status, enabled, COUNT(*) FROM retailers GROUP BY status, enabled ORDER BY status, enabled;")
        current_statuses = cursor.fetchall()
        
        print("\nCurrent status distribution:")
        for status, enabled, count in current_statuses:
            status_display = status if status else "NULL"
            enabled_display = "True" if enabled else "False"
            print(f"  Status: {status_display}, Enabled: {enabled_display}, Count: {count}")
        
        # Step 1: Add new 'active' field
        cursor.execute("ALTER TABLE retailers ADD COLUMN active BOOLEAN DEFAULT 1;")
        print("Added new 'active' field with default value 1 (active)")
        
        # Step 2: Set active=0 for retailers that should be inactive
        # Any retailer with enabled=0 or specific statuses should be inactive
        inactive_conditions = [
            "enabled = 0",
            "status = 'disabled'",
            "status = 'inactive'", 
            "status = 'closed'",
            "status = 'suspended'",
            "status = 'pending'",
            "status = 'deleted'",
            "status = 'archived'"
        ]
        
        inactive_where = " OR ".join(inactive_conditions)
        cursor.execute(f"UPDATE retailers SET active = 0 WHERE {inactive_where};")
        inactive_count = cursor.rowcount
        print(f"Set {inactive_count} retailers to inactive (active = 0)")
        
        # Step 3: Verify the final state
        cursor.execute("SELECT active, COUNT(*) FROM retailers GROUP BY active ORDER BY active;")
        final_active_statuses = cursor.fetchall()
        
        print("\nFinal active field distribution:")
        for active, count in final_active_statuses:
            active_display = "Active (1)" if active == 1 else "Inactive (0)"
            print(f"  Active: {active_display}, Count: {count}")
        
        # Step 4: Show what status values remain for business logic
        cursor.execute("SELECT status, COUNT(*) FROM retailers WHERE status IS NOT NULL AND status != '' GROUP BY status ORDER BY status;")
        business_statuses = cursor.fetchall()
        
        print("\nBusiness logic status values (preserved):")
        for status, count in business_statuses:
            print(f"  Status: {status}, Count: {count}")
        
        # Step 5: Remove the redundant enabled field
        cursor.execute("ALTER TABLE retailers DROP COLUMN enabled;")
        print("Removed redundant 'enabled' field")
        
        # Commit all changes
        conn.commit()
        print("\n✅ Status concerns separated successfully!")
        print("New 'active' field: 1 = active, 0 = inactive")
        print("Existing 'status' field: preserved for business logic")
        print("Redundant 'enabled' field: removed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during consolidation: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    """Main function to run the consolidation."""
    
    # Default database path
    db_path = "instance/tamermap_data.db"
    
    # Allow command line override
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Separating status concerns in database: {db_path}")
    print("This will add a new 'active' field for active/inactive state.")
    print("The existing 'status' field will be preserved for business logic.")
    print("The redundant 'enabled' field will be removed.")
    
    # Ask for confirmation
    response = input("\nProceed with separation? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("Separation cancelled.")
        return
    
    success = separate_status_concerns(db_path)
    
    if success:
        print("\n🎉 Status concerns have been separated!")
        print("New 'active' field: 1 = active, 0 = inactive")
        print("Existing 'status' field: preserved for business logic")
        print("Redundant 'enabled' field: removed")
    else:
        print("\n💥 Separation failed. Please check the error messages above.")

if __name__ == "__main__":
    main()
