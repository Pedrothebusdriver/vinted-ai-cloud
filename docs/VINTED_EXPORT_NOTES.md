Notes on Pete's Vinted export (2025-12-02):
- Parsed file: `listings/index.html` inside `data/raw/vinted_export_20251202.zip`.
- Fields used: title, description, brand, size, condition/status, colour, price/order_value, created_at, parcel_size, views/likes, image paths (for IDs), currency suffix.
- Weirdness: export is HTML (no CSV); no explicit category or public URL; listing_id inferred from first photo path (`photos/<listing_id>/...`); prices carry currency text (GBP here); some fields occasionally missing (e.g., colour). 
