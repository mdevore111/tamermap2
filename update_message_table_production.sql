-- Production Message Table Update Script
-- This script safely adds all missing columns to the message table
-- Run this script on your production database to ensure all 24 fields are present

-- First, let's see the current table structure
PRAGMA table_info(message);

-- Add missing columns (these will fail silently if columns already exist)
-- SQLite will return an error for duplicate columns, but the script will continue

-- Add is_admin_report column
ALTER TABLE message ADD COLUMN is_admin_report BOOLEAN DEFAULT 0;

-- Add form_type column
ALTER TABLE message ADD COLUMN form_type VARCHAR(50);

-- Add win_type column
ALTER TABLE message ADD COLUMN win_type VARCHAR(50);

-- Add location_used column
ALTER TABLE message ADD COLUMN location_used VARCHAR(255);

-- Add cards_found column
ALTER TABLE message ADD COLUMN cards_found VARCHAR(255);

-- Add time_saved column
ALTER TABLE message ADD COLUMN time_saved VARCHAR(100);

-- Add money_saved column
ALTER TABLE message ADD COLUMN money_saved VARCHAR(100);

-- Add allow_feature column
ALTER TABLE message ADD COLUMN allow_feature BOOLEAN DEFAULT 0;

-- Verify the final table structure (should show 24 columns)
PRAGMA table_info(message);

-- Expected final structure:
-- 0|id|INTEGER|1||1
-- 1|sender_id|INTEGER|0||0
-- 2|recipient_id|INTEGER|0||0
-- 3|communication_type|VARCHAR(50)|1||0
-- 4|subject|VARCHAR(255)|1||0
-- 5|body|TEXT|1||0
-- 6|reported_address|VARCHAR(255)|0||0
-- 7|reported_phone|VARCHAR(100)|0||0
-- 8|reported_website|VARCHAR(255)|0||0
-- 9|reported_hours|VARCHAR(255)|0||0
-- 10|out_of_business|BOOLEAN|0|0|0
-- 11|is_new_location|BOOLEAN|0|0|0
-- 12|is_admin_report|BOOLEAN|0|0|0
-- 13|form_type|VARCHAR(50)|0||0
-- 14|timestamp|DATETIME|0||0
-- 15|read|BOOLEAN|0||0
-- 16|name|VARCHAR(255)|0||0
-- 17|address|VARCHAR(255)|0||0
-- 18|email|VARCHAR(255)|0||0
-- 19|win_type|VARCHAR(50)|0||0
-- 20|location_used|VARCHAR(255)|0||0
-- 21|cards_found|VARCHAR(255)|0||0
-- 22|time_saved|VARCHAR(100)|0||0
-- 23|money_saved|VARCHAR(100)|0||0
-- 24|allow_feature|BOOLEAN|0|0|0
