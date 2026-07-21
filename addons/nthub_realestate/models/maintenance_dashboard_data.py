# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, timedelta


class MaintenanceDashboardData(models.Model):
    _name = 'maintenance.dashboard.data'
    _description = 'Maintenance Dashboard Data Provider'

    @api.model
    def get_maintenance_dashboard_data(self):
        """
        Fetch all maintenance dashboard data in a single call.
        Returns KPIs, chart data for Maintenance Requests and Job Orders.
        """
        MaintenanceRequest = self.env['rental.maintenance.request']
        JobOrder = self.env['maintenance.job.order']
        
        # ==================== 1. MAINTENANCE REQUEST KPIs ====================
        total_requests = MaintenanceRequest.search_count([])
        draft_requests = MaintenanceRequest.search_count([('x_status', '=', 'draft')])
        submitted_requests = MaintenanceRequest.search_count([('x_status', '=', 'submitted')])
        under_review_requests = MaintenanceRequest.search_count([('x_status', '=', 'under_review')])
        in_progress_requests = MaintenanceRequest.search_count([('x_status', '=', 'in_progress')])
        pending_approval_requests = MaintenanceRequest.search_count([
            ('x_status', 'in', ['pending_supervisor_approval', 'pending_tenant_approval'])
        ])
        closed_requests = MaintenanceRequest.search_count([('x_status', '=', 'closed')])
        cancelled_requests = MaintenanceRequest.search_count([('x_status', '=', 'cancelled')])
        
        # ==================== 2. JOB ORDER KPIs ====================
        total_jobs = JobOrder.search_count([])
        draft_jobs = JobOrder.search_count([('state', '=', 'draft')])
        sent_to_contractor = JobOrder.search_count([('state', '=', 'sent_to_contractor')])
        in_progress_jobs = JobOrder.search_count([('state', '=', 'in_progress')])
        completed_by_contractor = JobOrder.search_count([('state', '=', 'completed_by_contractor')])
        pending_supervisor = JobOrder.search_count([('state', '=', 'pending_supervisor_approval')])
        pending_tenant = JobOrder.search_count([('state', '=', 'pending_tenant_approval')])
        closed_jobs = JobOrder.search_count([('state', '=', 'closed')])
        cancelled_jobs = JobOrder.search_count([('state', '=', 'cancelled')])
        
        # ==================== 3. CHART: Requests by Type ====================
        request_type_data = MaintenanceRequest.read_group(
            domain=[],
            fields=['x_request_type'],
            groupby=['x_request_type'],
        )
        type_selection = dict(MaintenanceRequest._fields['x_request_type'].selection)
        request_type_labels = [type_selection.get(d['x_request_type'], d['x_request_type'] or 'Unknown') for d in request_type_data]
        request_type_values = [d['x_request_type_count'] for d in request_type_data]
        
        # ==================== 4. CHART: Requests by Status ====================
        request_status_data = MaintenanceRequest.read_group(
            domain=[],
            fields=['x_status'],
            groupby=['x_status'],
        )
        status_selection = dict(MaintenanceRequest._fields['x_status'].selection)
        request_status_labels = [status_selection.get(d['x_status'], d['x_status'] or 'Unknown') for d in request_status_data]
        request_status_values = [d['x_status_count'] for d in request_status_data]
        
        # ==================== 5. CHART: Job Orders by Status ====================
        job_status_data = JobOrder.read_group(
            domain=[],
            fields=['state'],
            groupby=['state'],
        )
        job_state_selection = dict(JobOrder._fields['state'].selection)
        job_status_labels = [job_state_selection.get(d['state'], d['state'] or 'Unknown') for d in job_status_data]
        job_status_values = [d['state_count'] for d in job_status_data]
        
        # ==================== 6. CHART: Requests by Priority ====================
        priority_data = MaintenanceRequest.read_group(
            domain=[],
            fields=['priority'],
            groupby=['priority'],
        )
        priority_selection = dict(MaintenanceRequest._fields['priority'].selection)
        priority_labels = [priority_selection.get(d['priority'], d['priority'] or 'Unknown') for d in priority_data]
        priority_values = [d['priority_count'] for d in priority_data]
        
        # ==================== 7. CHART: Monthly Requests Trend ====================
        query = """
            SELECT
                TO_CHAR(request_date, 'YYYY-MM') as month,
                COUNT(*) as total_requests
            FROM
                rental_maintenance_request
            WHERE
                request_date IS NOT NULL
            GROUP BY
                TO_CHAR(request_date, 'YYYY-MM')
            ORDER BY
                month DESC
            LIMIT 12;
        """
        self.env.cr.execute(query)
        monthly_data = self.env.cr.dictfetchall()
        monthly_data.reverse()  # Oldest first
        monthly_labels = [m['month'] for m in monthly_data]
        monthly_values = [m['total_requests'] for m in monthly_data]
        
        # ==================== 8. CHART: Job Orders by Type ====================
        job_type_data = JobOrder.read_group(
            domain=[],
            fields=['job_type'],
            groupby=['job_type'],
        )
        job_type_selection = dict(JobOrder._fields['job_type'].selection)
        job_type_labels = [job_type_selection.get(d['job_type'], d['job_type'] or 'Unknown') for d in job_type_data]
        job_type_values = [d['job_type_count'] for d in job_type_data]
        
        # ==================== 9. RECENT ACTIVITY ====================
        recent_requests = MaintenanceRequest.search([], limit=5, order='create_date DESC')
        recent_requests_list = [{
            'id': r.id,
            'name': r.name,
            'type': type_selection.get(r.x_request_type, r.x_request_type),
            'status': status_selection.get(r.x_status, r.x_status),
            'priority': priority_selection.get(r.priority, r.priority),
            'date': r.request_date.strftime('%Y-%m-%d %H:%M') if r.request_date else '',
        } for r in recent_requests]
        
        recent_jobs = JobOrder.search([], limit=5, order='create_date DESC')
        recent_jobs_list = [{
            'id': j.id,
            'name': j.name,
            'state': job_state_selection.get(j.state, j.state),
            'contractor': j.assigned_contractor_id.name if j.assigned_contractor_id else 'Not Assigned',
            'date': j.date.strftime('%Y-%m-%d') if j.date else '',
        } for j in recent_jobs]
        
        # ==================== RETURN ALL DATA ====================
        return {
            # Maintenance Request KPIs
            'total_requests': total_requests,
            'draft_requests': draft_requests,
            'submitted_requests': submitted_requests,
            'under_review_requests': under_review_requests,
            'in_progress_requests': in_progress_requests,
            'pending_approval_requests': pending_approval_requests,
            'closed_requests': closed_requests,
            'cancelled_requests': cancelled_requests,
            
            # Job Order KPIs
            'total_jobs': total_jobs,
            'draft_jobs': draft_jobs,
            'sent_to_contractor': sent_to_contractor,
            'in_progress_jobs': in_progress_jobs,
            'completed_by_contractor': completed_by_contractor,
            'pending_supervisor': pending_supervisor,
            'pending_tenant': pending_tenant,
            'closed_jobs': closed_jobs,
            'cancelled_jobs': cancelled_jobs,
            
            # Charts
            'request_type_chart': {
                'labels': request_type_labels,
                'values': request_type_values,
            },
            'request_status_chart': {
                'labels': request_status_labels,
                'values': request_status_values,
            },
            'job_status_chart': {
                'labels': job_status_labels,
                'values': job_status_values,
            },
            'priority_chart': {
                'labels': priority_labels,
                'values': priority_values,
            },
            'monthly_trend_chart': {
                'labels': monthly_labels,
                'values': monthly_values,
            },
            'job_type_chart': {
                'labels': job_type_labels,
                'values': job_type_values,
            },
            
            # Recent Activity
            'recent_requests': recent_requests_list,
            'recent_jobs': recent_jobs_list,
        }
