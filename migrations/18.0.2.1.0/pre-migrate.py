def migrate(cr, version):
    cr.execute("""
        ALTER TABLE parking_location
            ADD COLUMN IF NOT EXISTS company_id INTEGER
    """)
    cr.execute("""
        UPDATE parking_location
        SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
        WHERE company_id IS NULL
    """)
    cr.execute("""
        ALTER TABLE parking_location
            ALTER COLUMN company_id SET NOT NULL
    """)

    cr.execute("""
        DELETE FROM ir_model_data
        WHERE res_id IN (
            SELECT id FROM ir_model
            WHERE model IN ('parking.contract.history', 'parking.checkin.checkout.wizard')
        )
        AND model = 'ir.model'
    """)
    cr.execute("""
        DELETE FROM ir_model
        WHERE model IN ('parking.contract.history', 'parking.checkin.checkout.wizard')
    """)