# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json

class RentalQuotationDashboard(models.TransientModel):
    _name = 'rental.quotation.dashboard'
    _description = 'Rental Quotation Dashboard'
    
    # Dashboard Data
    total_quotations = fields.Integer(string='Total Quotations', readonly=True)
    pending_approvals = fields.Integer(string='Pending Approvals', readonly=True)
    approved_quotations = fields.Integer(string='Approved Quotations', readonly=True)
    converted_quotations = fields.Integer(string='Converted to Contracts', readonly=True)
    rejected_quotations = fields.Integer(string='Rejected Quotations', readonly=True)
    expired_quotations = fields.Integer(string='Expired Quotations', readonly=True)
    
    # Monthly Statistics
    monthly_quotations = fields.Text(string='Monthly Quotations Data', readonly=True)
    approval_time_avg = fields.Float(string='Average Approval Time (Hours)', readonly=True)
    conversion_rate = fields.Float(string='Conversion Rate %', readonly=True)
    
    # Financial Statistics
    total_quotation_value = fields.Float(string='Total Quotation Value', readonly=True)
    approved_value = fields.Float(string='Approved Value', readonly=True)
    converted_value = fields.Float(string='Converted Value', readonly=True)
    average_quotation_value = fields.Float(string='Average Quotation Value', readonly=True)
    
    # Top Performers
    top_salesperson_data = fields.Text(string='Top Salesperson Data', readonly=True)
    approval_stats_data = fields.Text(string='Approval Statistics Data', readonly=True)
    
    # Filter Options
    date_from = fields.Date(string='Date From', default=lambda self: fields.Date.today() - relativedelta(months=3))
    date_to = fields.Date(string='Date To', default=fields.Date.today)
    salesperson_ids = fields.Many2many('res.users', string='Salespersons')
    state_filter = fields.Selection([
        ('all', 'All States'),
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('converted', 'Converted')
    ], string='State Filter', default='all')
    
    @api.model
    def get_dashboard_data(self, context=None):
        """Get dashboard data for frontend widgets"""
        domain = self._get_domain_filters(context)
        
        # Get basic counts
        dashboard_data = {
            'total_quotations': self._get_quotation_count(domain),
            'pending_approvals': self._get_quotation_count(domain + [('state', 'in', ['submitted', 'under_review'])]),
            'approved_quotations': self._get_quotation_count(domain + [('state', '=', 'approved')]),
            'converted_quotations': self._get_quotation_count(domain + [('state', '=', 'converted')]),
            'rejected_quotations': self._get_quotation_count(domain + [('state', '=', 'rejected')]),
            'expired_quotations': self._get_quotation_count(domain + [('state', '=', 'expired')]),
        }
        
        # Get financial data
        financial_data = self._get_financial_statistics(domain)
        dashboard_data.update(financial_data)
        
        # Get chart data
        dashboard_data.update({
            'monthly_chart_data': self._get_monthly_chart_data(domain),
            'status_pie_data': self._get_status_pie_data(domain),
            'approval_time_data': self._get_approval_time_data(domain),
            'top_salesperson_data': self._get_top_salesperson_data(domain),
            'approval_stats_data': self._get_approval_statistics_data(domain),
        })
        
        return dashboard_data
    
    def _get_domain_filters(self, context=None):
        """Build domain filters based on context"""
        domain = []
        
        if context:
            if context.get('date_from'):
                domain.append(('quotation_date', '>=', context['date_from']))
            if context.get('date_to'):
                domain.append(('quotation_date', '<=', context['date_to']))
            if context.get('salesperson_ids'):
                domain.append(('salesperson_id', 'in', context['salesperson_ids']))
            if context.get('state_filter') and context['state_filter'] != 'all':
                domain.append(('state', '=', context['state_filter']))
                
        return domain
    
    def _get_quotation_count(self, domain):
        """Get quotation count for given domain"""
        return self.env['rental.quotation'].search_count(domain)
    
    def _get_financial_statistics(self, domain):
        """Calculate financial statistics"""
        quotations = self.env['rental.quotation'].search(domain)
        
        if not quotations:
            return {
                'total_quotation_value': 0,
                'approved_value': 0,
                'converted_value': 0,
                'average_quotation_value': 0,
                'conversion_rate': 0,
            }
        
        total_value = sum(quotations.mapped('total_amount'))
        approved_quotations = quotations.filtered(lambda q: q.state in ['approved', 'sent', 'accepted', 'converted'])
        converted_quotations = quotations.filtered(lambda q: q.state == 'converted')
        
        approved_value = sum(approved_quotations.mapped('total_amount'))
        converted_value = sum(converted_quotations.mapped('total_amount'))
        
        conversion_rate = (len(converted_quotations) / len(quotations) * 100) if quotations else 0
        
        return {
            'total_quotation_value': total_value,
            'approved_value': approved_value,
            'converted_value': converted_value,
            'average_quotation_value': total_value / len(quotations) if quotations else 0,
            'conversion_rate': round(conversion_rate, 2),
        }
    
    def _get_monthly_chart_data(self, domain):
        """Get monthly quotation data for charts"""
        quotations = self.env['rental.quotation'].search(domain)
        
        # Group by month
        monthly_data = {}
        for quotation in quotations:
            month_key = quotation.quotation_date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'total': 0,
                    'approved': 0,
                    'converted': 0,
                    'value': 0
                }
            
            monthly_data[month_key]['total'] += 1
            monthly_data[month_key]['value'] += quotation.total_amount
            
            if quotation.state in ['approved', 'sent', 'accepted', 'converted']:
                monthly_data[month_key]['approved'] += 1
            if quotation.state == 'converted':
                monthly_data[month_key]['converted'] += 1
        
        # Convert to chart format
        months = sorted(monthly_data.keys())
        return {
            'labels': [datetime.strptime(m, '%Y-%m').strftime('%B %Y') for m in months],
            'datasets': [
                {
                    'label': _('Total Quotations'),
                    'data': [monthly_data[m]['total'] for m in months],
                    'backgroundColor': '#1f77b4'
                },
                {
                    'label': _('Approved'),
                    'data': [monthly_data[m]['approved'] for m in months],
                    'backgroundColor': '#2ca02c'
                },
                {
                    'label': _('Converted'),
                    'data': [monthly_data[m]['converted'] for m in months],
                    'backgroundColor': '#ff7f0e'
                }
            ]
        }
    
    def _get_status_pie_data(self, domain):
        """Get status distribution for pie chart"""
        quotations = self.env['rental.quotation'].search(domain)
        
        status_counts = {}
        for quotation in quotations:
            status = quotation.state
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'labels': [dict(self.env['rental.quotation']._fields['state'].selection)[status] 
                      for status in status_counts.keys()],
            'data': list(status_counts.values()),
            'backgroundColor': [
                '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                '#9467bd', '#8c564b', '#e377c2', '#7f7f7f'
            ]
        }
    
    def _get_approval_time_data(self, domain):
        """Get approval time statistics"""
        approved_quotations = self.env['rental.quotation'].search(
            domain + [('state', 'in', ['approved', 'sent', 'accepted', 'converted'])]
        )
        
        approval_times = []
        for quotation in approved_quotations:
            approvals = quotation.approval_history_ids.filtered(lambda a: a.status == 'approved')
            if approvals:
                latest_approval = max(approvals, key=lambda a: a.approval_date)
                time_diff = (latest_approval.approval_date - quotation.create_date).total_seconds() / 3600
                approval_times.append(time_diff)
        
        if approval_times:
            return {
                'average': round(sum(approval_times) / len(approval_times), 2),
                'min': round(min(approval_times), 2),
                'max': round(max(approval_times), 2),
                'data': approval_times
            }
        
        return {'average': 0, 'min': 0, 'max': 0, 'data': []}
    
    def _get_top_salesperson_data(self, domain):
        """Get top salesperson performance data"""
        quotations = self.env['rental.quotation'].search(domain)
        
        salesperson_stats = {}
        for quotation in quotations:
            sp_id = quotation.salesperson_id.id
            if sp_id not in salesperson_stats:
                salesperson_stats[sp_id] = {
                    'name': quotation.salesperson_id.name,
                    'total_quotations': 0,
                    'approved_quotations': 0,
                    'converted_quotations': 0,
                    'total_value': 0,
                    'converted_value': 0
                }
            
            stats = salesperson_stats[sp_id]
            stats['total_quotations'] += 1
            stats['total_value'] += quotation.total_amount
            
            if quotation.state in ['approved', 'sent', 'accepted', 'converted']:
                stats['approved_quotations'] += 1
            if quotation.state == 'converted':
                stats['converted_quotations'] += 1
                stats['converted_value'] += quotation.total_amount
        
        # Calculate conversion rates and sort by performance
        for stats in salesperson_stats.values():
            stats['approval_rate'] = (stats['approved_quotations'] / stats['total_quotations'] * 100) \
                if stats['total_quotations'] else 0
            stats['conversion_rate'] = (stats['converted_quotations'] / stats['total_quotations'] * 100) \
                if stats['total_quotations'] else 0
        
        # Sort by total value
        top_performers = sorted(salesperson_stats.values(), 
                               key=lambda x: x['total_value'], reverse=True)[:10]
        
        return top_performers
    
    def _get_approval_statistics_data(self, domain):
        """Get approval statistics and bottlenecks"""
        quotations = self.env['rental.quotation'].search(domain)
        
        approval_stats = {
            'total_approvals_required': 0,
            'auto_approved': 0,
            'manual_approved': 0,
            'rejected': 0,
            'avg_approval_levels': 0,
            'approval_bottlenecks': {}
        }
        
        total_levels = 0
        for quotation in quotations:
            if quotation.approval_required:
                approval_stats['total_approvals_required'] += 1
                total_levels += quotation.max_approval_level
                
                # Check approval history
                for approval in quotation.approval_history_ids:
                    if approval.status == 'approved':
                        if approval.auto_approved:
                            approval_stats['auto_approved'] += 1
                        else:
                            approval_stats['manual_approved'] += 1
                    elif approval.status == 'rejected':
                        approval_stats['rejected'] += 1
                    
                    # Track bottlenecks by approver
                    approver = approval.approver_id.name
                    if approver not in approval_stats['approval_bottlenecks']:
                        approval_stats['approval_bottlenecks'][approver] = {
                            'pending': 0,
                            'avg_time': 0,
                            'total_approvals': 0
                        }
        
        if approval_stats['total_approvals_required']:
            approval_stats['avg_approval_levels'] = total_levels / approval_stats['total_approvals_required']
        
        return approval_stats

class RentalQuotationKPI(models.Model):
    _name = 'rental.quotation.kpi'
    _description = 'Rental Quotation KPI Tracking'
    _order = 'date desc'
    
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    period_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'), 
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')
    ], string='Period Type', default='daily')
    
    # Quotation Metrics
    total_quotations = fields.Integer(string='Total Quotations')
    approved_quotations = fields.Integer(string='Approved Quotations')
    rejected_quotations = fields.Integer(string='Rejected Quotations')
    converted_quotations = fields.Integer(string='Converted Quotations')
    expired_quotations = fields.Integer(string='Expired Quotations')
    
    # Financial Metrics
    total_value = fields.Float(string='Total Quotation Value')
    approved_value = fields.Float(string='Approved Value')
    converted_value = fields.Float(string='Converted Value')
    average_quotation_value = fields.Float(string='Average Quotation Value')
    
    # Performance Metrics
    approval_rate = fields.Float(string='Approval Rate %')
    conversion_rate = fields.Float(string='Conversion Rate %')
    avg_approval_time = fields.Float(string='Average Approval Time (Hours)')
    
    # Team Metrics
    active_salespersons = fields.Integer(string='Active Salespersons')
    top_performer_id = fields.Many2one('res.users', string='Top Performer')
    
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company)
    
    @api.model
    def calculate_daily_kpis(self):
        """Calculate and store daily KPIs - can be run via cron"""
        today = fields.Date.today()
        
        # Get quotations for today
        domain = [('quotation_date', '=', today)]
        quotations = self.env['rental.quotation'].search(domain)
        
        if not quotations:
            return
        
        # Calculate metrics
        kpi_data = {
            'date': today,
            'period_type': 'daily',
            'total_quotations': len(quotations),
            'approved_quotations': len(quotations.filtered(lambda q: q.state in ['approved', 'sent', 'accepted'])),
            'rejected_quotations': len(quotations.filtered(lambda q: q.state == 'rejected')),
            'converted_quotations': len(quotations.filtered(lambda q: q.state == 'converted')),
            'expired_quotations': len(quotations.filtered(lambda q: q.state == 'expired')),
            'total_value': sum(quotations.mapped('total_amount')),
            'approved_value': sum(quotations.filtered(lambda q: q.state in ['approved', 'sent', 'accepted']).mapped('total_amount')),
            'converted_value': sum(quotations.filtered(lambda q: q.state == 'converted').mapped('total_amount')),
        }
        
        # Calculate rates
        if kpi_data['total_quotations']:
            kpi_data['approval_rate'] = (kpi_data['approved_quotations'] / kpi_data['total_quotations']) * 100
            kpi_data['conversion_rate'] = (kpi_data['converted_quotations'] / kpi_data['total_quotations']) * 100
            kpi_data['average_quotation_value'] = kpi_data['total_value'] / kpi_data['total_quotations']
        
        # Check if record exists for today
        existing_kpi = self.search([('date', '=', today), ('period_type', '=', 'daily')])
        if existing_kpi:
            existing_kpi.write(kpi_data)
        else:
            self.create(kpi_data)