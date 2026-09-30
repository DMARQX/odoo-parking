from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Switch every company to the "Parking" document layout.

    Colours already chosen for a company are kept; companies without colours take the
    main company's (or navy and gold). Writing the layout also recompiles the report styles.
    Everything stays editable in Settings > Companies > Configure Document Layout.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    layout = env.ref("parking_management.external_layout_parking")
    paperformat = env.ref("parking_management.paperformat_parking_a4")
    companies = env["res.company"].search([])
    main = env.ref("base.main_company", raise_if_not_found=False) or companies[:1]
    primary = main.primary_color or "#c9a04e"
    secondary = main.secondary_color or "#0f172a"
    for company in companies:
        vals = {"external_report_layout_id": layout.id, "paperformat_id": paperformat.id}
        if not company.primary_color:
            vals["primary_color"] = primary
        if not company.secondary_color:
            vals["secondary_color"] = secondary
        company.write(vals)
