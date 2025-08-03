# Data Cleanup Utility

## Overview
The `data_cleanup.py` utility maintains database performance by cleaning historical data. It handles three main types of cleanup operations:
- Analytics data (heatmaps, usage, visitor logs)
- Events
- Retailer statuses

## Features
- Configurable cleanup thresholds
- Separate cleanup operations for different data types
- Detailed logging of cleanup operations
- Transaction-safe database operations

## Usage
```bash
python data_cleanup.py [--type {analytics,events,retailers,all}]
```

### Options
- `--type`: Specifies which type of data to clean
  - `analytics`: Cleans heatmap, usage, and visitor log data
  - `events`: Cleans old events
  - `retailers`: Clears old retailer statuses
  - `all`: Performs all cleanup operations (default)

## Cleanup Thresholds
- Analytics data: 30 days old
- Visitor logs: 90 days old
- Events: 24 hours old
- Retailer statuses: 30 days old

## Logging
- Logs are stored in `utils/logs/data_cleanup.log`
- Rotating file handler with 5MB max size and 5 backup files
- Detailed logging of each cleanup operation

## Functions

### clean_analytics()
Removes old analytics data including:
- PinInteraction records
- MapUsage records
- VisitorLog records

### clean_events()
Removes events older than 24 hours.

### clean_retailer_status()
Clears status fields for retailers older than 30 days.

## Error Handling
- All operations are wrapped in try-except blocks
- Database transactions are rolled back on error
- Errors are logged with full stack traces

## Dependencies
- SQLAlchemy
- Flask
- Python standard library 