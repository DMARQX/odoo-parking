from odoo import models, api, fields, models

class RsProject(models.Model):
    _inherit = 'rs.project'


    count_of_proprety = fields.Integer(compute="count_of_proprety_project")


    quantity = fields.Integer(
        string="Quantity",
        compute='get_propreties_number',
        store=True  # Add this
    )
    total_projects_sold = fields.Integer(
        compute="total_projects_sold_state",
        store=True  # Add this
    )



    # Make sure the @api.depends decorators are correct for stored fields
    @api.depends('subproperties_ids')  # This is the trigger
    def get_propreties_number(self):
        for rec in self:
            rec.quantity = len(rec.subproperties_ids)

    @api.depends("subproperties_ids", "subproperties_ids.state", "subproperties_ids.pricing")
    def total_projects_sold_state(self):
        for rec in self:
            # Filter for sold units and sum their pricing
            sold_units = rec.subproperties_ids.filtered(lambda x: x.state == "sold")
            rec.total_projects_sold = sum(sold_units.mapped("pricing"))

    @api.depends("subproperties_ids", "subproperties_ids.state")
    def count_of_proprety_project(self):
        for rec in self:
            rec.count_of_proprety = len(rec.subproperties_ids.filtered(lambda x: x.state == "sold"))

    @api.model
    def get_dashboard_data(self):
        total_sold = self.search_count([])
        delayed = self.env['ownership.contract.line'].search_count([
            ('delay_state', '=', 'draft'),
            ('invoice_state', '=', 'posted'),
        ])
        return {
            'total_sold': total_sold,
            'delayed': delayed,
        }





