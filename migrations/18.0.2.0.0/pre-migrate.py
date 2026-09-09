def migrate(cr, version):
    """Merge parking.contract.history records into the unified parking.vehicle.movement
    log, then drop the legacy history table and clean up related system records."""

    # 1) Move history rows into the unified movement table.
    #    Legacy history columns -> unified movement columns:
    #      check_out  -> check_out_time
    #      check_in   -> check_in_time
    cr.execute("SELECT count(*) FROM parking_contract_history")
    count = cr.fetchone()[0]
    if count:
        cr.execute("""
            INSERT INTO parking_vehicle_movement (
                spot_id,
                contract_id,
                vehicle_id,
                check_out_time,
                check_in_time,
                operator_out_id,
                operator_in_id,
                notes,
                duration_hours,
                create_uid,
                create_date,
                write_uid,
                write_date
            )
            SELECT
                h.spot_id,
                h.contract_id,
                h.vehicle_id,
                h.check_out,
                h.check_in,
                h.operator_out_id,
                h.operator_in_id,
                h.notes,
                h.duration_hours,
                h.create_uid,
                h.create_date,
                h.write_uid,
                h.write_date
            FROM parking_contract_history h
        """)

    # 2) Clean up system records that referenced the removed model.
    cr.execute("""
        DELETE FROM ir_model_access
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'parking.contract.history'
        )
    """)

    cr.execute("""
        DELETE FROM ir_rule
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'parking.contract.history'
        )
    """)

    # Remove stale ir.model.data pointing to records that no longer exist,
    # keeping action_parking_contract_history (reused for the unified model).
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'parking_management'
        AND name IN (
            'model_parking_contract_history',
            'parking_contract_history_tree',
            'parking_contract_history_form',
            'access_parking_contract_history_user_read',
            'access_parking_contract_history_manage',
            'access_parking_contract_history_delete',
            'access_parking_contract_history_manager',
            'access_parking_contract_history_portal',
            'rule_parking_contract_history_portal'
        )
    """)

    # Delete stale views that referenced the removed model.
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE model = 'parking.contract.history'
    """)

    # 3) Drop the legacy table (views/models are handled by the ORM upgrade).
    cr.execute("DROP TABLE IF EXISTS parking_contract_history CASCADE")

    # 4) Clean up the replaced check-in wizard records.
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE model = 'parking.checkin.checkout.wizard'
    """)
    cr.execute("""
        DELETE FROM ir_model_access
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'parking.checkin.checkout.wizard'
        )
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'parking_management'
        AND name IN (
            'model_parking_checkin_checkout_wizard',
            'parking_checkin_checkout_wizard_form',
            'menu_parking_history',
            'menu_parking_checkin_dashboard'
        )
    """)

    cr.execute("""
        DELETE FROM ir_ui_menu
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'parking_management'
            AND name IN ('menu_parking_history', 'menu_parking_checkin_dashboard')
        )
    """)