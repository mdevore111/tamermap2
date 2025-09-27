-- Migration Script: Remove is_pro field from database
-- Run this on staging server first, then production
-- 
-- This script removes the redundant is_pro field from:
-- 1. user table
-- 2. legend_clicks table  
-- 3. route_events table
--
-- After this migration, Pro status will be determined solely by roles
-- using current_user.has_role('Pro')

-- Step 1: Remove is_pro column from user table
ALTER TABLE user DROP COLUMN is_pro;

-- Step 2: Remove is_pro column from legend_clicks table
ALTER TABLE legend_clicks DROP COLUMN is_pro;

-- Step 3: Remove is_pro column from route_events table  
ALTER TABLE route_events DROP COLUMN is_pro;

-- Verify the columns have been removed
-- You can run these queries to confirm:
-- PRAGMA table_info(user);
-- PRAGMA table_info(legend_clicks);
-- PRAGMA table_info(route_events);

-- Note: After running this migration:
-- 1. Pro status will be determined by roles only
-- 2. All Pro checking should use current_user.has_role('Pro')
-- 3. Historical pro_end_date and cancellation data is preserved
-- 4. No data loss - only redundant field removed
