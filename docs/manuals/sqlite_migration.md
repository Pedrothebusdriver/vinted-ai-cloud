# SQLite Drafts/Photos Migration (FlipLens)

FlipLens Milestone 1 needs richer draft metadata and photo ordering stored on the Pi. Use this checklist to update the SQLite database safely.

## 1. Backup first

```bash
cd ~/vinted-ai-cloud
cp pi-app/data/vinted.db pi-app/data/vinted.db.bak.$(date +%Y%m%d-%H%M%S)
```

Store the backup somewhere safe (or SCP it off the Pi) before running the migration.

## 2. Dry run the helper

```bash
python scripts/sqlite_migrate.py --dry-run
```

This prints the SQL that would run (`CREATE TABLE`, `ALTER TABLE`, etc.) without modifying anything. If you see unexpected statements, stop and investigate before moving on.

## 3. Apply the migration

```bash
python scripts/sqlite_migrate.py --db pi-app/data/vinted.db
```

What the helper does:
- Ensures `drafts` includes all FlipLens columns:
  `id`, timestamps, `status`, `brand`, `size`, `colour`, `category_id`, `condition`,
  `title`, `description`, `price_low/mid/high`, `selected_price`.
- Renames the legacy table to `drafts__legacy`, creates the new schema, copies any existing `item_id/title/price_pence` data, then drops the legacy table.
- Ensures `photos` has `draft_id`, `file_path`, and `position` columns (keeps existing `original_path`, `optimised_path`, etc.) and backfills `draft_id` from `item_id`.
- VACUUMs the DB at the end for consistency.

You can point `--db` at another path if you need to prep a staging database before copying it onto the Pi.

## 4. Verify

```bash
sqlite3 pi-app/data/vinted.db '.schema drafts'
sqlite3 pi-app/data/vinted.db '.schema photos'
```

Confirm the tables include the FlipLens columns. Also spot-check a few rows:

```bash
sqlite3 pi-app/data/vinted.db 'select id, title, status, selected_price from drafts limit 5;'
sqlite3 pi-app/data/vinted.db 'select draft_id, file_path, position from photos limit 5;'
```

If you hit an error, restore the backup (`mv vinted.db.bak* vinted.db`) and try again.
