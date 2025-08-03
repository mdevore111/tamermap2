# Database Management Utility

## Overview
The `db_manage.py` utility provides comprehensive database management capabilities, including backup creation, schema inspection, and schema reset operations. It's designed to work with SQLite databases.

## Features
- Create timestamped database backups
- List and inspect database schema
- Reset schema for data import
- Automatic database file location
- Detailed operation logging

## Usage
```bash
python db_manage.py [backup|schema|reset]
```

### Commands
1. Create Backup:
```bash
python db_manage.py backup
```
Creates a timestamped backup of the database in the instance directory.

2. List Schema:
```bash
python db_manage.py schema
```
Displays all tables and their schema definitions.

3. Reset Schema:
```bash
python db_manage.py reset
```
Resets the database schema for data import.

## Database Structure

### Retailers Table
```sql
CREATE TABLE retailers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    retailer         VARCHAR(255) NOT NULL,
    retailer_type    VARCHAR(50)  NOT NULL,
    full_address     VARCHAR(255) NOT NULL,
    latitude         FLOAT,
    longitude        FLOAT,
    place_id         VARCHAR(100),
    first_seen       DATETIME,
    phone_number     VARCHAR(50),
    rating           FLOAT,
    website          VARCHAR(255),
    opening_hours    TEXT,
    last_api_update  DATETIME,
    machine_count    INTEGER DEFAULT 0,
    previous_count   INTEGER DEFAULT 0,
    status           TEXT
)
```

### Events Table
```sql
CREATE TABLE events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    event_title      TEXT    NOT NULL,
    first_seen       TEXT,
    full_address     TEXT    NOT NULL,
    start_date       DATETIME,
    start_time       TIME,
    latitude         REAL,
    longitude        REAL,
    end_date         DATETIME,
    end_time         TIME,
    registration_url TEXT,
    price            REAL,
    email            TEXT,
    phone            TEXT
)
```

## Functions

### backup_database()
- Creates timestamped backup
- Verifies source database existence
- Returns backup file path

### list_schema()
- Connects to database
- Retrieves all table definitions
- Displays formatted schema information

### reset_schema()
- Drops existing tables
- Creates new tables with defined schema
- Handles transaction management

## Database Location
The utility automatically searches for the database file in:
1. `../instance/tamermap_data.db`
2. `../../instance/tamermap_data.db`
3. `./instance/tamermap_data.db`

## Logging
- Standard Python logging configuration
- Timestamp and level information
- Detailed operation logging

## Error Handling
- Database connection management
- File existence verification
- Transaction safety
- Detailed error logging

## Dependencies
- SQLite3
- Python standard library 