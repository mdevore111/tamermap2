# Place ID Migration TODO (SQLite-first)

This document tracks the steps implemented and remaining actions to complete a place_id‑centric system without dropping geolocation.

## Completed (this branch)
- Frontend
  - Route Planner builds Google Maps links using `place_id` (with lat,lng fallback).
  - Markers expose `place_id`; planner consumes it; duplicates merged by `place_id`.
  - Map de-duplication: `MarkerManager` prevents duplicate pins by `place_id` and merges `retailer_type` into "store + kiosk".
  - Planner adds "Merge Nearby" toggle and shows a "Merged N entries" disclosure in summary.
  - Popularity posts include `place_id` alongside lat/lng.
- Backend
  - `/track/pin` upserts into `pin_popularity` by `place_id` while retaining audit rows in `pin_interactions`.
  - `/api/pin-heatmap-data` serves from `pin_popularity` aggregated by `place_id` (fallback to recent clicks).
  - `/api/pin-stats` returns totals by `place_id`.
- DB migration
  - Script: `scripts/sqlite_migrate_place_id.py`
    - Adds `pin_interactions.place_id` (nullable)
    - Creates `pin_popularity` table
    - Indexes: tries UNIQUE `retailers(place_id)`, falls back to non-unique if duplicates exist, and logs samples
    - Creates UNIQUE `pin_popularity(place_id)`

## Remaining (server/data)
- Resolve duplicate retailers with the same `place_id`
  - Run the admin endpoint `/admin/duplicates/place-id` to list duplicates.
  - Use `/admin/duplicates/place-id/merge` to merge kiosk+store variants (safe merge rules below).
  - After cleanup, create the unique index:
    ```sql
    CREATE UNIQUE INDEX idx_retailers_place_id ON retailers(place_id);
    ```
- Switch any popularity/heatmap aggregation that still uses coordinates to `place_id` (most are updated).
- Backfill normalization (recommended for scrapers)
  - Store `normalized_name`, `normalized_street`, `postal_code` to prevent re-scrape dupes.

## Merge rules (auto-merge endpoint)
When two or more retailers share the same `place_id`:
- Keep the row with the most complete data (opening_hours present; non-null lat/lng; non-empty phone/website; latest `last_api_update`).
- Merge `retailer_type` as a combined value (e.g., `"store + kiosk"`).
- Preserve `machine_count` = max(current), `first_seen` = earliest. Keep `enabled` if any is true.
- Repoint related popularity: `pin_popularity(place_id)` is already consolidated by key; no change needed.
- Delete the extra duplicates after merge.

## Operations
- Dev/Prod migration
  - `python scripts/sqlite_migrate_place_id.py`
- Listing duplicates
  - `GET /admin/duplicates/place-id` → JSON list of duplicate `place_id` groups.
- Merging duplicates
  - `POST /admin/duplicates/place-id/merge` with payload `{ place_id: "..." }` → merges duplicates for that `place_id`.

## SQLite performance settings
- Enable WAL: `PRAGMA journal_mode=WAL;`
- `PRAGMA synchronous=NORMAL;`

## Postgres (future)
- Use same schema with `place_id` constraints and consider PostGIS for server-side geospatial if needed.


