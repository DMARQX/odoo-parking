def migrate(cr, version):
    """Classify existing movements before movement_type replaces the old operation field.

    The old "operation" column was always "check_out", even for returns, so it is
    ignored: a movement with a return time but no delivery time was a first arrival,
    everything else is a trip. Inconsistent rows are flagged later by needs_review.
    """
    cr.execute("ALTER TABLE parking_vehicle_movement ADD COLUMN IF NOT EXISTS movement_type varchar")
    cr.execute("""
        UPDATE parking_vehicle_movement
           SET movement_type = CASE
               WHEN check_out_time IS NULL AND check_in_time IS NOT NULL THEN 'arrival'
               ELSE 'trip' END
         WHERE movement_type IS NULL
    """)
