# Retailer Enabled Field Migration

## Overview

This document outlines the migration to add an `enabled` boolean field to the retailers table. This field allows retailers to be temporarily disabled without being deleted from the database.

## Changes Made

### 1. Model Update
**File:** `app/models.py`
- Added `enabled = db.Column(db.Boolean, default=True)` to the Retailer model
- Updated model docstring to include the new field

### 2. Database Migration
**File:** `utils/add_retailer_enabled_field.py`
- Created migration script to add the `enabled` column
- Sets default value to `True` for all existing retailers
- Includes verification and rollback capabilities

### 3. Query Updates
**File:** `app/utils.py`
- Updated `get_retailer_locations()` to filter by `enabled = 1`
- Added `enabled` field to SELECT statements
- Ensures only enabled retailers are returned by the API

### 4. Performance Index
**File:** `utils/create_performance_indexes.py`
- Added `idx_retailer_enabled` index for the new field
- Optimizes queries filtering by enabled status

## Migration Results

### Database Changes
- ✅ Added `enabled` column to `retailers` table
- ✅ Set `enabled = True` for all 4,473 existing retailers
- ✅ Created performance index for the field

### API Behavior
- ✅ Only enabled retailers are returned by `/api/retailers`
- ✅ Disabled retailers are filtered out automatically
- ✅ Field is included in API responses

## Usage Examples

### Check Enabled Status
```python
from app.models import Retailer

# Get all enabled retailers
enabled_retailers = Retailer.query.filter_by(enabled=True).all()

# Get all disabled retailers
disabled_retailers = Retailer.query.filter_by(enabled=False).all()

# Count enabled vs disabled
total = Retailer.query.count()
enabled = Retailer.query.filter_by(enabled=True).count()
disabled = Retailer.query.filter_by(enabled=False).count()
```

### Enable/Disable Retailers
```python
# Disable a retailer
retailer = Retailer.query.get(1)
retailer.enabled = False
db.session.commit()

# Enable a retailer
retailer.enabled = True
db.session.commit()
```

### API Impact
```python
# Before disabling: 4,473 retailers returned
# After disabling one: 4,472 retailers returned
# After re-enabling: 4,473 retailers returned
```

## Production Deployment

### Files to Deploy
```
app/models.py                                    # Updated model
app/utils.py                                     # Updated queries
utils/add_retailer_enabled_field.py             # Migration script
utils/create_performance_indexes.py             # Updated index script
```

### Deployment Steps
1. **Backup production database**
2. **Deploy updated files**
3. **Run migration script:**
   ```bash
   python utils/add_retailer_enabled_field.py
   ```
4. **Create new index:**
   ```bash
   python utils/create_performance_indexes.py
   ```
5. **Verify migration:**
   ```bash
   python utils/add_retailer_enabled_field.py --verify-only
   ```

## Benefits

### 1. Data Preservation
- Retailers can be disabled without losing data
- Historical information is preserved
- Easy to re-enable if needed

### 2. API Performance
- Disabled retailers are filtered out at the database level
- Reduces API response size
- Improves map rendering performance

### 3. Administrative Control
- Easy to temporarily hide problematic retailers
- Can disable retailers during maintenance
- Provides granular control over what's displayed

## Testing

### Migration Verification
- ✅ All existing retailers have `enabled = True`
- ✅ New retailers default to `enabled = True`
- ✅ API only returns enabled retailers
- ✅ Performance index is created

### Functionality Testing
- ✅ Disabling a retailer removes it from API responses
- ✅ Re-enabling a retailer restores it to API responses
- ✅ Database queries filter correctly
- ✅ No impact on existing functionality

## Future Considerations

### 1. Admin Interface
- Consider adding UI controls to enable/disable retailers
- Bulk operations for multiple retailers
- Audit trail for enable/disable actions

### 2. Additional Filtering
- Could extend to other entities (events, etc.)
- Consider soft delete patterns for other tables

### 3. Performance Monitoring
- Monitor query performance with the new index
- Consider composite indexes if needed
- Track enable/disable patterns

## Conclusion

The `enabled` field migration was successful and provides a clean way to temporarily disable retailers without data loss. The implementation includes proper filtering, performance optimization, and maintains backward compatibility. 