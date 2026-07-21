# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.tools.misc import get_lang

class RealEstateDashboardData(models.Model):
    _name = 'real.estate.dashboard.data'
    _description = 'Real Estate Dashboard Data Provider'

    @api.model
    def get_real_estate_dashboard_data(self):
        """
        This method is called by the JavaScript controller to fetch all dashboard data.
        It is optimized to gather data efficiently from your real estate models.
        """
        Project = self.env['rs.project']
        Unit = self.env['sub.property']
        RentalContract = self.env['rental.contract']

        # 1. --- Statistics KPIs (Key Performance Indicators) ---
        total_projects = Project.search_count([])
        total_units = Unit.search_count([])
        available_units = Unit.search_count([('state', '=', 'free')])
        rented_units = Unit.search_count([('state', '=', 'on_lease')])
        sold_units = Unit.search_count([('state', '=', 'sold')])
        total_owners = self.env['res.partner'].search_count([('is_owner', '=', True)])

        # 2. --- Chart: Units by Status ---
        unit_status_data = Unit.read_group(
            domain=[],
            fields=['state'],
            groupby=['state'],
        )
        state_selection = dict(Unit._fields['state'].selection)
        status_labels = [state_selection.get(d['state'], d['state']) for d in unit_status_data]
        status_values = [d['state_count'] for d in unit_status_data]

        # 3. --- Chart: Projects by Status ---
        project_status_data = Project.read_group(
            domain=[],
            fields=['project_status_type'],
            groupby=['project_status_type']
        )
        project_status_selection = dict(Project._fields['project_status_type'].selection)
        project_labels = [project_status_selection.get(d['project_status_type'], d['project_status_type']) for d in project_status_data]
        project_values = [d['project_status_type_count'] for d in project_status_data]

        # 4. --- Chart: Monthly Rental Revenue ---
        # Using a raw SQL query for efficient date grouping and aggregation.
        query = """
            SELECT
                TO_CHAR(rc.date_from, 'YYYY-MM') as month,
                SUM(rc.rental_fee) as total_revenue
            FROM
                rental_contract rc
            WHERE
                rc.state = 'confirmed'
            GROUP BY
                TO_CHAR(rc.date_from, 'YYYY-MM')
            ORDER BY
                month;
        """
        self.env.cr.execute(query)
        monthly_revenue_data = self.env.cr.dictfetchall()
        monthly_revenue_labels = [m['month'] for m in monthly_revenue_data]
        monthly_revenue_values = [m['total_revenue'] for m in monthly_revenue_data]

        # 5. --- Return all data in a single dictionary ---
        return {
            'total_projects': total_projects,
            'total_units': total_units,
            'available_units': available_units,
            'rented_units': rented_units,
            'sold_units': sold_units,
            'total_owners': total_owners,
            'unit_status_chart': {
                'labels': status_labels,
                'values': status_values,
            },
            'project_status_chart': {
                'labels': project_labels,
                'values': project_values,
            },
            'monthly_revenue_chart': {
                'labels': monthly_revenue_labels,
                'values': monthly_revenue_values,
            }
        }