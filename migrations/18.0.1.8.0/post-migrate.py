def migrate(cr, version):
    """Migrate spot_type from selection to Many2one parking.spot.type"""
    # Create default spot types if they don't exist
    cr.execute("SELECT id FROM parking_spot_type WHERE code = 'standard'")
    if not cr.fetchone():
        cr.execute("""
            INSERT INTO parking_spot_type (name, code, sequence, active, create_date, write_date)
            VALUES
            ('Standard', 'standard', 10, true, NOW(), NOW()),
            ('Large / SUV', 'large', 20, true, NOW(), NOW()),
            ('Motorcycle', 'motorcycle', 30, true, NOW(), NOW()),
            ('VIP', 'vip', 40, true, NOW(), NOW())
        """)

    # Update parking_spot records that have spot_type set but no spot_type_id
    cr.execute("""
        UPDATE parking_spot ps
        SET spot_type_id = pst.id
        FROM parking_spot_type pst
        WHERE ps.spot_type = pst.code
        AND ps.spot_type_id IS NULL
    """)