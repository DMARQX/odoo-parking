from odoo import models

class DashboardRealEstate(models.Model):
    _name = "dashboard.real.estate"
    _description = "Dashboard for Real Estate"

    def action_open_ownership_state(self):
        return self.env.ref('nthub_realestate.act_ownership_state').read()[0]

    def action_open_total_amount(self):
        return self.env.ref('nthub_realestate.act_total_amount').read()[0]

    def action_open_calender(self):
        return self.env.ref('nthub_realestate.act_calender').read()[0]

    def action_open_delay_state(self):
        return self.env.ref('nthub_realestate.act_delay_state').read()[0]

    def action_open_owner_calendar(self):
        return self.env.ref('nthub_realestate.act_owner_t_calender').read()[0]
