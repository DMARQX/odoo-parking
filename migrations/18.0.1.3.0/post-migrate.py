def migrate(cr, version):
    """Migrate old Many2many service_ids to new One2many service_line_ids."""
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'parking_contract_service_rel'")
    if not cr.fetchone():
        return  # No old table, nothing to migrate

    # Check if there are any contracts with old services not yet migrated
    cr.execute("""
        INSERT INTO parking_contract_service_line (contract_id, service_id, quantity, price_unit, create_date, write_date)
        SELECT
            r.parking_contract_id,
            r.parking_service_id,
            1.0,
            ps.price,
            NOW(),
            NOW()
        FROM parking_contract_service_rel r
        JOIN parking_service ps ON ps.id = r.parking_service_id
        WHERE NOT EXISTS (
            SELECT 1 FROM parking_contract_service_line l
            WHERE l.contract_id = r.parking_contract_id
              AND l.service_id = r.parking_service_id
        )
    """)
