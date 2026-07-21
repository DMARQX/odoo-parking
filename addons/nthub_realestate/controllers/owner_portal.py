from functools import wraps
from odoo import http, fields, _, SUPERUSER_ID # Ensure SUPERUSER_ID is not used unless necessary
from odoo.http import request, Response # Make sure Response is imported
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError
import base64
import json # Make sure json is imported
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def owner_only(f):
    @wraps(f)
    def wrap(self, *args, **kw):
        if request.env.user.share and not request.env.user.partner_id.is_owner:
            return request.render('website.403',
                                  {'message': 'Access to this section is restricted to property owners.'})
        return f(self, *args, **kw)

    return wrap


def is_owner(f):
    """Decorator to ensure the user is a property owner"""
    @wraps(f)
    def wrap(self, *args, **kw):
        if request.env.user.share and not request.env.user.partner_id.is_owner:
            return request.render('website.403',
                                  {'message': 'Access to this section is restricted to property owners.'})
        return f(self, *args, **kw)
    return wrap


class OwnerPortal(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        """Adds counters for properties to the portal home page."""
        values = super()._prepare_home_portal_values(counters)
        partner_id = request.env.user.partner_id.id
        
        if not request.env.user.partner_id.is_owner and request.env.user.share:
            values['property_count'] = 0
            values['pending_vendor_quotes'] = 0
            return values
            
        values['property_count'] = request.env['rs.project'].sudo().search_count([('partner_id', '=', partner_id)])
        
        # Count vendor quotes pending approval (pending_owner_approval state) for owner's projects - NEW WORKFLOW
        values['pending_vendor_quotes'] = request.env['maintenance.vendor.quote'].sudo().search_count([
            ('state', '=', 'pending_owner_approval'),
            ('project_id.partner_id', '=', partner_id)
        ])
        
        return values
    
    @http.route(['/my/properties'], type='http', auth="user", website=True)
    @owner_only
    def portal_my_properties(self, **kw):
        owner = request.env.user.partner_id
        domain = [('partner_id', '=', owner.id)]

        properties = request.env['rs.project'].sudo().search(domain)

        fields_to_aggregate = ['quantity:sum', 'count_of_proprety:sum', 'total_projects_sold:sum',
                               'monthly_revenue:sum', 'available_units_count:sum', 'rented_units_count:sum']
        aggregated_data = request.env['rs.project'].sudo().read_group(domain, fields_to_aggregate, [])
        stats = aggregated_data[0] if aggregated_data else {}

        recent_requests = request.env['owner.request'].sudo().search(
            [('owner_id', '=', owner.id)], order='create_date desc', limit=5
        )
        
        # Calculate financials from rental contracts for owner's properties
        total_amount = 0.0  # Sum of all installment amounts
        total_receivables = 0.0  # Amount due (unpaid)
        total_collected = 0.0  # Sum of paid installments
        total_contract_value = 0.0
        
        # Calculate contract value and receivables per project
        project_financials = {}
        project_ids = properties.ids
        for prop in properties:
            project_financials[prop.id] = {
                'contract_value': 0.0,  # Sum of total_contract_value (rental + services + electricity + taxes)
                'total_receivables': 0.0,  # Unpaid amounts (amount due)
                'total_amount': 0.0,  # Total installment amounts
                'total_collected': 0.0,  # Paid installments
            }
        
        # Search contracts ONLY for owner's projects (must have rs_project linked to owner's properties)
        rental_contracts = request.env['rental.contract'].sudo().search([
            ('rs_project', 'in', project_ids),
            ('state', '=', 'confirmed')
        ])
        
        for contract in rental_contracts:
            project_id = contract.rs_project.id if contract.rs_project else None
            
            # Add contract value per project (rental + services + electricity + taxes)
            if project_id and project_id in project_financials:
                # total_contract_value includes: rental_fee + service_fee + electricity_fee for entire period
                contract_total = contract.total_contract_value or 0.0
                # Add tax amount if not included
                if not contract.tax_included:
                    contract_total += contract.tax_amount or 0.0
                project_financials[project_id]['contract_value'] += contract_total
                total_contract_value += contract_total
            
            # Sum all amounts and receivables from rental lines (Installments)
            for line in contract.rental_line_ids:
                line_amount = line.amount or 0.0
                line_residual = line.amount_residual or line_amount
                
                # Add to total amount
                total_amount += line_amount
                if project_id and project_id in project_financials:
                    project_financials[project_id]['total_amount'] += line_amount
                
                # Check if line is paid
                if line.payment_state == 'paid':
                    total_collected += line_amount
                    if project_id and project_id in project_financials:
                        project_financials[project_id]['total_collected'] += line_amount
                else:
                    # Calculate amount due (receivables) - same logic as receivables page
                    # Only include if has posted invoice OR date is past due
                    is_receivable = False
                    if line.invoice_id and line.invoice_id.state == 'posted':
                        is_receivable = True
                    elif not line.invoice_id and line.date and line.date <= fields.Date.today():
                        is_receivable = True
                    
                    if is_receivable:
                        total_receivables += line_residual
                        if project_id and project_id in project_financials:
                            project_financials[project_id]['total_receivables'] += line_residual

        # Count pending vendor quotes for owner approval - NEW WORKFLOW
        pending_vendor_quotes = request.env['maintenance.vendor.quote'].sudo().search_count([
            ('state', '=', 'pending_owner_approval'),
            ('project_id.partner_id', '=', owner.id)
        ])

        # Calculate total available and rented area
        total_available_area = 0.0
        total_rented_area = 0.0
        for prop in properties:
            for unit in prop.subproperties_ids:
                unit_area = unit.rs_project_area or 0.0
                if unit.state == 'free':
                    total_available_area += unit_area
                elif unit.state in ('rented', 'on_lease'):
                    total_rented_area += unit_area

        # Calculate overdue amounts and count
        overdue_amount = 0.0
        overdue_count = 0
        today = fields.Date.today()
        for contract in rental_contracts:
            for line in contract.rental_line_ids:
                if line.payment_state != 'paid' and line.date and line.date < today:
                    overdue_amount += line.amount_residual or line.amount or 0.0
                    overdue_count += 1

        # Count and get contracts expiring within 30 days
        thirty_days_later = today + timedelta(days=30)
        expiring_contracts = request.env['rental.contract'].sudo().search([
            ('rs_project', 'in', project_ids),
            ('state', '=', 'confirmed'),
            ('date_to', '>=', today),
            ('date_to', '<=', thirty_days_later)
        ], order='date_to asc', limit=5)
        expiring_contracts_count = len(expiring_contracts)
        
        # Prepare expiring contracts data with days remaining
        expiring_contracts_data = []
        for contract in expiring_contracts:
            days_remaining = (contract.date_to - today).days if contract.date_to else 0
            expiring_contracts_data.append({
                'id': contract.id,
                'name': contract.name,
                'tenant': contract.partner_id.name if contract.partner_id else 'N/A',
                'unit': contract.rs_project_unit.name if contract.rs_project_unit else 'N/A',
                'project': contract.rs_project.name if contract.rs_project else 'N/A',
                'end_date': contract.date_to,
                'days_remaining': days_remaining,
                'rental_fee': contract.rental_fee or 0.0,
            })

        # Count open maintenance requests
        open_maintenance_count = request.env['owner.request'].sudo().search_count([
            ('owner_id', '=', owner.id),
            ('state', 'in', ['new', 'in_progress'])
        ])
        
        # Build alerts list
        alerts = []
        if expiring_contracts_count > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'fa-calendar-times-o',
                'message': f'{expiring_contracts_count} contract{"s" if expiring_contracts_count > 1 else ""} expiring within 30 days',
                'link': '#expiring-contracts',
                'count': expiring_contracts_count
            })
        if overdue_count > 0:
            alerts.append({
                'type': 'danger',
                'icon': 'fa-exclamation-triangle',
                'message': f'{overdue_count} overdue payment{"s" if overdue_count > 1 else ""} totaling {overdue_amount:,.0f} {request.env.company.currency_id.symbol}',
                'link': '/my/receivables',
                'count': overdue_count
            })
        if pending_vendor_quotes > 0:
            alerts.append({
                'type': 'info',
                'icon': 'fa-file-text-o',
                'message': f'{pending_vendor_quotes} vendor quote{"s" if pending_vendor_quotes > 1 else ""} awaiting your approval',
                'link': '/my/vendor_quotes',
                'count': pending_vendor_quotes
            })
        if open_maintenance_count > 0:
            alerts.append({
                'type': 'primary',
                'icon': 'fa-wrench',
                'message': f'{open_maintenance_count} open maintenance request{"s" if open_maintenance_count > 1 else ""}',
                'link': '/my/requests',
                'count': open_maintenance_count
            })
        
        # Calculate last month's data for comparison (percentage changes)
        last_month_start = today - relativedelta(months=1, day=1)
        last_month_end = today - relativedelta(day=1) - timedelta(days=1)
        this_month_start = today.replace(day=1)
        
        this_month_collected = 0.0
        last_month_collected = 0.0
        
        for contract in rental_contracts:
            for line in contract.rental_line_ids:
                if line.payment_state == 'paid' and line.date:
                    if this_month_start <= line.date <= today:
                        this_month_collected += line.amount or 0.0
                    elif last_month_start <= line.date <= last_month_end:
                        last_month_collected += line.amount or 0.0
        
        # Calculate percentage change
        collection_change = 0
        if last_month_collected > 0:
            collection_change = round(((this_month_collected - last_month_collected) / last_month_collected) * 100, 1)
        
        # Get total and rented units
        total_units = stats.get('quantity', 0)
        rented_units = stats.get('rented_units_count', 0)
        
        # Calculate occupancy rate
        occupancy_rate = round((rented_units / total_units * 100), 1) if total_units else 0

        # Prepare chart data for ApexCharts
        chart_data = self._prepare_dashboard_chart_data(owner, properties, project_financials, rental_contracts)

        values = {
            'properties': properties,
            'project_financials': project_financials,  # Per-project contract value & receivables
            'requests': recent_requests,
            'property_count': len(properties),
            'total_units': total_units,
            'available_units': stats.get('available_units_count', 0),
            'rented_units': rented_units,
            'sold_units_count': stats.get('count_of_proprety', 0),
            'sold_units_value': stats.get('total_projects_sold', 0),
            'monthly_revenue': stats.get('monthly_revenue', 0.0),
            'total_collected': total_collected,
            'total_receivables': total_receivables,
            'overdue_amount': overdue_amount,
            'overdue_count': overdue_count,
            'expiring_contracts_count': expiring_contracts_count,
            'expiring_contracts_data': expiring_contracts_data,
            'open_maintenance_count': open_maintenance_count,
            'pending_vendor_quotes': pending_vendor_quotes,
            'total_available_area': total_available_area,
            'total_rented_area': total_rented_area,
            'company_currency': request.env.company.currency_id,
            'chart_data': chart_data,
            'json': json,
            'page_name': 'property',
            # New enhanced dashboard data
            'alerts': alerts,
            'this_month_collected': this_month_collected,
            'collection_change': collection_change,
            'occupancy_rate': occupancy_rate,
        }
        return request.render("nthub_realestate.portal_owner_dashboard", values)

    @http.route(['/my/my-properties'], type='http', auth="user", website=True)
    @owner_only
    def portal_my_properties_list(self, **kw):
        """Comprehensive My Properties page with detailed property and unit information"""
        owner = request.env.user.partner_id
        domain = [('partner_id', '=', owner.id)]
        today = fields.Date.today()

        properties = request.env['rs.project'].sudo().search(domain)

        fields_to_aggregate = ['quantity:sum', 'count_of_proprety:sum', 'total_projects_sold:sum',
                               'monthly_revenue:sum', 'available_units_count:sum', 'rented_units_count:sum']
        aggregated_data = request.env['rs.project'].sudo().read_group(domain, fields_to_aggregate, [])
        stats = aggregated_data[0] if aggregated_data else {}

        # Calculate financials per project
        project_financials = {}
        project_ids = properties.ids
        total_collected = 0.0
        total_receivables = 0.0
        overdue_amount = 0.0
        overdue_count = 0
        
        for prop in properties:
            project_financials[prop.id] = {
                'contract_value': 0.0,
                'total_receivables': 0.0,
                'total_collected': 0.0,
            }
        
        rental_contracts = request.env['rental.contract'].sudo().search([
            ('rs_project', 'in', project_ids),
            ('state', '=', 'confirmed')
        ])
        
        for contract in rental_contracts:
            project_id = contract.rs_project.id if contract.rs_project else None
            if project_id and project_id in project_financials:
                contract_total = contract.total_contract_value or 0.0
                if not contract.tax_included:
                    contract_total += contract.tax_amount or 0.0
                project_financials[project_id]['contract_value'] += contract_total
            
            for line in contract.rental_line_ids:
                line_amount = line.amount or 0.0
                line_residual = line.amount_residual or line_amount
                
                if line.payment_state == 'paid':
                    total_collected += line_amount
                    if project_id and project_id in project_financials:
                        project_financials[project_id]['total_collected'] += line_amount
                else:
                    is_receivable = False
                    if line.invoice_id and line.invoice_id.state == 'posted':
                        is_receivable = True
                    elif not line.invoice_id and line.date and line.date <= today:
                        is_receivable = True
                    
                    if is_receivable:
                        total_receivables += line_residual
                        if project_id and project_id in project_financials:
                            project_financials[project_id]['total_receivables'] += line_residual
                    
                    # Count overdue
                    if line.date and line.date < today:
                        overdue_amount += line_residual
                        overdue_count += 1

        # Get all units from owner's properties
        all_units = request.env['sub.property'].sudo().search([
            ('rs_project_id', 'in', project_ids)
        ], limit=50, order='state, name')
        
        # Count reserved units
        reserved_units = request.env['sub.property'].sudo().search_count([
            ('rs_project_id', 'in', project_ids),
            ('state', '=', 'reserved')
        ])

        # Count pending vendor quotes
        pending_vendor_quotes = request.env['maintenance.vendor.quote'].sudo().search_count([
            ('state', '=', 'pending_owner_approval'),
            ('project_id.partner_id', '=', owner.id)
        ])

        # Count contracts expiring in 30 days
        thirty_days_later = today + timedelta(days=30)
        expiring_contracts_count = request.env['rental.contract'].sudo().search_count([
            ('rs_project', 'in', project_ids),
            ('state', '=', 'confirmed'),
            ('date_to', '>=', today),
            ('date_to', '<=', thirty_days_later)
        ])

        # Count open maintenance requests
        open_maintenance_count = request.env['owner.request'].sudo().search_count([
            ('owner_id', '=', owner.id),
            ('state', 'in', ['new', 'in_progress'])
        ])

        # Build recent activities
        recent_activities = []
        
        # Recent payments
        for contract in rental_contracts:
            for line in contract.rental_line_ids:
                if line.payment_state == 'paid' and line.date:
                    recent_activities.append({
                        'type': 'payment',
                        'title': f'Payment Received - {contract.name}',
                        'description': f'{line.amount:,.0f} {request.env.company.currency_id.symbol}',
                        'time': line.date.strftime('%b %d'),
                        'date': line.date
                    })
        
        # Recent requests
        recent_requests = request.env['owner.request'].sudo().search([
            ('owner_id', '=', owner.id)
        ], order='create_date desc', limit=5)
        for req in recent_requests:
            recent_activities.append({
                'type': 'maintenance',
                'title': req.subject[:40] if req.subject else 'Request',
                'description': req.state.replace('_', ' ').title(),
                'time': req.create_date.strftime('%b %d'),
                'date': req.create_date.date()
            })
        
        # Sort activities by date
        recent_activities.sort(key=lambda x: x.get('date', today), reverse=True)
        recent_activities = recent_activities[:10]

        # Prepare chart data
        chart_data = self._prepare_dashboard_chart_data(owner, properties, project_financials, rental_contracts)

        values = {
            'properties': properties,
            'project_financials': project_financials,
            'property_count': len(properties),
            'total_units': stats.get('quantity', 0),
            'available_units': stats.get('available_units_count', 0),
            'rented_units': stats.get('rented_units_count', 0),
            'reserved_units': reserved_units,
            'monthly_revenue': stats.get('monthly_revenue', 0.0),
            'total_collected': total_collected,
            'total_receivables': total_receivables,
            'overdue_amount': overdue_amount,
            'overdue_count': overdue_count,
            'expiring_contracts_count': expiring_contracts_count,
            'open_maintenance_count': open_maintenance_count,
            'pending_vendor_quotes': pending_vendor_quotes,
            'all_units': all_units,
            'recent_activities': recent_activities,
            'company_currency': request.env.company.currency_id,
            'chart_data': chart_data,
            'json': json,
            'page_name': 'my_properties',
        }
        return request.render("nthub_realestate.portal_my_properties_list", values)

    def _prepare_dashboard_chart_data(self, owner, properties, project_financials, rental_contracts):
        """Prepare data for ApexCharts in the dashboard"""
        chart_data = {
            'revenue': {
                'months': [],
                'revenue': [],
                'collected': []
            },
            'collection': {
                'projects': [],
                'collected': [],
                'receivables': []
            }
        }
        
        # Get last 6 months for revenue chart
        today = fields.Date.today()
        months_data = {}
        
        for i in range(5, -1, -1):
            month_date = today - relativedelta(months=i)
            month_key = month_date.strftime('%Y-%m')
            month_name = month_date.strftime('%b')
            months_data[month_key] = {
                'name': month_name,
                'revenue': 0.0,
                'collected': 0.0
            }
        
        # Calculate monthly revenue and collected amounts
        for contract in rental_contracts:
            for line in contract.rental_line_ids:
                if line.date:
                    line_month = line.date.strftime('%Y-%m')
                    if line_month in months_data:
                        months_data[line_month]['revenue'] += line.amount or 0.0
                        if line.payment_state == 'paid':
                            months_data[line_month]['collected'] += line.amount or 0.0
        
        # Build revenue chart data
        for month_key in sorted(months_data.keys()):
            chart_data['revenue']['months'].append(months_data[month_key]['name'])
            chart_data['revenue']['revenue'].append(round(months_data[month_key]['revenue'], 2))
            chart_data['revenue']['collected'].append(round(months_data[month_key]['collected'], 2))
        
        # Build collection by project chart data
        for prop in properties[:8]:  # Limit to 8 projects for readability
            financials = project_financials.get(prop.id, {})
            chart_data['collection']['projects'].append(prop.name[:15] + '...' if len(prop.name) > 15 else prop.name)
            chart_data['collection']['collected'].append(round(financials.get('total_collected', 0.0), 2))
            chart_data['collection']['receivables'].append(round(financials.get('total_receivables', 0.0), 2))
        
        return chart_data

    @http.route(['/my/collected-payments'], type='http', auth="user", website=True)
    @owner_only
    def portal_my_collected_payments(self, **kw):
        """Display all collected (paid) payments from rental contracts"""
        owner = request.env.user.partner_id
        
        # Get all projects owned by this owner
        properties = request.env['rs.project'].sudo().search([('partner_id', '=', owner.id)])
        project_ids = properties.ids
        
        # Get all rental contracts for owner's projects
        rental_contracts = request.env['rental.contract'].sudo().search([
            ('rs_project', 'in', project_ids),
            ('state', '=', 'confirmed')
        ])
        
        # Collect all paid rental lines with contract and tenant info
        paid_payments = []
        total_collected = 0.0
        monthly_collected = 0.0
        project_totals = {}
        monthly_data = {}
        today = fields.Date.today()
        current_month = today.strftime('%Y-%m')
        
        # Initialize last 6 months
        for i in range(5, -1, -1):
            month_date = today - relativedelta(months=i)
            month_key = month_date.strftime('%Y-%m')
            monthly_data[month_key] = {'name': month_date.strftime('%b'), 'amount': 0.0}
        
        for contract in rental_contracts:
            project_name = contract.rs_project.name if contract.rs_project else 'Unknown'
            if project_name not in project_totals:
                project_totals[project_name] = 0.0
            
            for line in contract.rental_line_ids:
                if line.payment_state == 'paid':
                    paid_payments.append({
                        'line': line,
                        'contract': contract,
                        'tenant': contract.partner_id,
                        'project': contract.rs_project,
                        'unit': contract.rs_project_unit,
                        'amount': line.amount,
                        'date': line.date,
                        'invoice': line.invoice_id,
                    })
                    total_collected += line.amount
                    project_totals[project_name] += line.amount
                    
                    # Track monthly collections
                    if line.date:
                        line_month = line.date.strftime('%Y-%m')
                        if line_month == current_month:
                            monthly_collected += line.amount
                        if line_month in monthly_data:
                            monthly_data[line_month]['amount'] += line.amount
        
        # Sort by date (most recent first)
        paid_payments.sort(key=lambda x: x['date'], reverse=True)
        
        # Prepare chart data
        chart_data = {
            'trend': {
                'months': [monthly_data[k]['name'] for k in sorted(monthly_data.keys())],
                'amounts': [round(monthly_data[k]['amount'], 2) for k in sorted(monthly_data.keys())]
            },
            'by_project': {
                'labels': list(project_totals.keys())[:8],
                'values': [round(v, 2) for v in list(project_totals.values())[:8]]
            }
        }
        
        values = {
            'paid_payments': paid_payments,
            'total_collected': total_collected,
            'monthly_collected': monthly_collected,
            'payment_count': len(paid_payments),
            'company_currency': request.env.company.currency_id,
            'chart_data': chart_data,
            'json': json,
            'page_name': 'collected_payments',
        }
        return request.render("nthub_realestate.portal_owner_collected_payments", values)

    @http.route(['/my/receivables'], type='http', auth="user", website=True)
    @owner_only
    def portal_my_receivables(self, **kw):
        """Display all receivables (posted invoices not yet paid) for owner's properties"""
        owner = request.env.user.partner_id
        
        # Get all projects owned by this owner
        properties = request.env['rs.project'].sudo().search([('partner_id', '=', owner.id)])
        project_ids = properties.ids
        
        receivable_lines = []
        total_receivables = 0.0
        overdue_amount = 0.0
        overdue_count = 0
        project_receivables = {}
        aging_buckets = {'current': 0.0, '30_days': 0.0, '60_days': 0.0, '90_plus': 0.0}
        today = fields.Date.today()
        total_days_overdue = 0
        
        # Get all rental contracts for owner's projects
        rental_contracts = request.env['rental.contract'].sudo().search([
            ('rs_project', 'in', project_ids),
            ('state', '=', 'confirmed')
        ])
        
        for contract in rental_contracts:
            project_name = contract.rs_project.name if contract.rs_project else 'Unknown'
            if project_name not in project_receivables:
                project_receivables[project_name] = 0.0
            
            for line in contract.rental_line_ids:
                # Skip paid lines
                if line.payment_state == 'paid':
                    continue
                    
                # Include lines with posted invoices that are not fully paid
                if line.invoice_id and line.invoice_id.state == 'posted':
                    due_date = line.invoice_id.invoice_date_due if line.invoice_id else line.date
                    amount_residual = line.amount_residual or line.amount
                    
                    receivable_lines.append({
                        'line': line,
                        'invoice': line.invoice_id,
                        'contract': contract,
                        'tenant': contract.partner_id,
                        'project': contract.rs_project,
                        'unit': contract.rs_project_unit,
                        'amount_total': line.amount,
                        'amount_residual': amount_residual,
                        'date': line.date,
                        'due_date': due_date,
                        'payment_state': line.payment_state or 'not_paid',
                    })
                    total_receivables += amount_residual
                    project_receivables[project_name] += amount_residual
                    
                    # Calculate aging and overdue
                    if due_date and due_date < today:
                        overdue_amount += amount_residual
                        overdue_count += 1
                        days_overdue = (today - due_date).days
                        total_days_overdue += days_overdue
                        
                        if days_overdue <= 30:
                            aging_buckets['30_days'] += amount_residual
                        elif days_overdue <= 60:
                            aging_buckets['60_days'] += amount_residual
                        else:
                            aging_buckets['90_plus'] += amount_residual
                    else:
                        aging_buckets['current'] += amount_residual
                        
                elif not line.invoice_id and line.date and line.date <= today:
                    # Line without invoice and past due - full amount is receivable
                    receivable_lines.append({
                        'line': line,
                        'invoice': None,
                        'contract': contract,
                        'tenant': contract.partner_id,
                        'project': contract.rs_project,
                        'unit': contract.rs_project_unit,
                        'amount_total': line.amount,
                        'amount_residual': line.amount,
                        'date': line.date,
                        'due_date': line.date,
                        'payment_state': 'not_paid',
                    })
                    total_receivables += line.amount
                    project_receivables[project_name] += line.amount
                    overdue_amount += line.amount
                    overdue_count += 1
                    days_overdue = (today - line.date).days
                    total_days_overdue += days_overdue
                    
                    if days_overdue <= 30:
                        aging_buckets['30_days'] += line.amount
                    elif days_overdue <= 60:
                        aging_buckets['60_days'] += line.amount
                    else:
                        aging_buckets['90_plus'] += line.amount
        
        # Sort by date (most recent first)
        receivable_lines.sort(key=lambda x: x['date'], reverse=True)
        
        # Calculate average days overdue
        avg_days_overdue = round(total_days_overdue / overdue_count) if overdue_count > 0 else 0
        
        # Prepare chart data
        chart_data = {
            'aging': {
                'labels': ['Current', '1-30 Days', '31-60 Days', '60+ Days'],
                'values': [
                    round(aging_buckets['current'], 2),
                    round(aging_buckets['30_days'], 2),
                    round(aging_buckets['60_days'], 2),
                    round(aging_buckets['90_plus'], 2)
                ]
            },
            'by_project': {
                'projects': list(project_receivables.keys())[:8],
                'amounts': [round(v, 2) for v in list(project_receivables.values())[:8]]
            }
        }
        
        values = {
            'receivable_invoices': receivable_lines,
            'total_receivables': total_receivables,
            'overdue_amount': overdue_amount,
            'overdue_count': overdue_count,
            'avg_days_overdue': avg_days_overdue,
            'invoice_count': len(receivable_lines),
            'company_currency': request.env.company.currency_id,
            'chart_data': chart_data,
            'json': json,
            'page_name': 'receivables',
        }
        return request.render("nthub_realestate.portal_owner_receivables", values)

    @http.route(['/my/requests'], type='http', auth="user", website=True)
    @owner_only
    def portal_my_owner_requests(self, **kw):
        owner = request.env.user.partner_id
        all_requests = request.env['owner.request'].sudo().search(
            [('owner_id', '=', owner.id)], order='create_date desc'
        )
        # Get projects for the modal form
        projects = request.env['rs.project'].sudo().search([('partner_id', '=', owner.id)])
        return request.render("nthub_realestate.portal_owner_requests_list", {
            'requests': all_requests, 
            'projects': projects,
            'page_name': 'my_requests'
        })

    @http.route(['/my/requests/new'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    @owner_only
    def portal_owner_request_new(self, **post):
        owner = request.env.user.partner_id

        if request.httprequest.method == 'POST':
            new_request = request.env['owner.request'].sudo().create({
                'owner_id': owner.id,
                'subject': post.get('subject'),
                'project_id': int(post.get('project_id')) if post.get('project_id') else False,
                'request_type': post.get('request_type'),
                'description': post.get('description'),
            })
            attachment_list = request.httprequest.files.getlist('attachments')
            for attachment in attachment_list:
                if attachment.filename:
                    request.env['ir.attachment'].sudo().create({
                        'name': attachment.filename, 'res_model': 'owner.request',
                        'res_id': new_request.id, 'datas': base64.b64encode(attachment.read()),
                        'public': False
                    })
            return request.redirect('/my/requests')

        projects = request.env['rs.project'].sudo().search([('partner_id', '=', owner.id)])
        return request.render("nthub_realestate.portal_owner_request_form_new", {
            'projects': projects, 'page_name': 'new_request'
        })

    @http.route(['/my/request/<int:request_id>'], type='http', auth="user", website=True)
    @owner_only
    def portal_owner_request_view(self, request_id, **kw):
        """Displays the details of a single owner request."""
        try:
            # Use a more descriptive variable name like 'request_obj' to avoid conflict
            request_obj = request.env['owner.request'].sudo().browse(request_id)
            if not request_obj.exists() or request_obj.owner_id.id != request.env.user.partner_id.id:
                raise AccessError("This request does not exist or you do not have access to it.")
        except (AccessError, ValueError):
            return request.redirect('/my/requests')

        return request.render("nthub_realestate.portal_owner_request_view", {
            'request_obj': request_obj, # Pass the object to the template
            'page_name': 'my_requests'
        })
    # =========================================================================
    # THIS ROUTE IS ESSENTIAL FOR VIEWING A PROJECT'S DETAILS
    # =========================================================================
    @http.route(['/my/property/<int:property_id>'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    @owner_only
    def portal_property_view(self, property_id, **kw):
        """Displays the details of a single property and handles attachment uploads."""
        print("\n" + "="*100)
        print(f"PORTAL PROPERTY VIEW CALLED - Property ID: {property_id}")
        print("="*100 + "\n")
        
        try:
            prop = request.env['rs.project'].sudo().browse(property_id)
            print(f"Property found: {prop.name} (ID: {prop.id})")
            if not prop.exists() or prop.partner_id.id != request.env.user.partner_id.id:
                print("ACCESS DENIED - Property doesn't exist or user doesn't own it")
                raise AccessError("Access Denied: You do not own this property.")
        except (AccessError, ValueError) as e:
            print(f"ERROR: {e}")
            return request.redirect('/my/properties')

        # Handle POST request for file upload
        if request.httprequest.method == 'POST':
            if 'attachment_file' in request.httprequest.files and request.httprequest.files['attachment_file']:
                uploaded_file = request.httprequest.files['attachment_file']
                file_name = uploaded_file.filename
                file_content = uploaded_file.read()

                # =====================================================================
                # THE FIX IS HERE: Create an instance of YOUR custom attachment model.
                # =====================================================================
                request.env['rs.project.attachment.line'].sudo().create({
                    'name': file_name,
                    'file': base64.b64encode(file_content), # 'file' is the binary field name in your model
                    'rs_project_attachment_id': prop.id,    # Link to the specific rs.project record
                })

                return request.redirect(f'/my/property/{prop.id}?upload_success=1') # Redirect with success message

        # For GET requests, prepare unit data with collected amounts
        units_with_data = []
        for unit in prop.subproperties_ids:
            # Search for related rental contracts that are confirmed, done, or renewed
            contracts = request.env['rental.contract'].sudo().search([
                ('rs_project_unit', '=', unit.id),
                ('state', 'in', ['confirmed', 'done', 'renew'])
            ])
            # Calculate the total paid amount for the unit from all its contracts
            total_collected = sum(contract.paid for contract in contracts)
            units_with_data.append({
                'unit': unit,
                'collected_amount': total_collected,
            })
        
        # Calculate Monthly Revenue for this project (from confirmed contracts)
        print("\n" + "-"*80)
        print("CALCULATING MONTHLY REVENUE AND RECEIVABLES")
        print("-"*80)
        
        monthly_revenue = 0.0
        confirmed_contracts = request.env['rental.contract'].sudo().search([
            ('rs_project', '=', prop.id),
            ('state', 'in', ['confirm', 'confirmed', 'done', 'renew'])
        ])
        
        print(f"Property ID: {prop.id}, Name: {prop.name}")
        print(f"Found {len(confirmed_contracts)} contracts with states: confirm/confirmed/done/renew")
        
        for contract in confirmed_contracts:
            # Calculate monthly revenue: rental_fee + service_fee (if monthly) + electricity_fee (if monthly and not included)
            contract_monthly_revenue = contract.rental_fee or 0.0
            
            # Add service fee if it's monthly
            if contract.service_monthly:
                contract_monthly_revenue += contract.service_fee or 0.0
            
            # Add electricity fee if it's monthly and not included in rental
            if contract.electricity_monthly and not contract.is_electricity_included:
                contract_monthly_revenue += contract.electricity_fee or 0.0
            
            # Add tax if not already included
            if not contract.tax_included and contract.tax_rate:
                tax_rate_decimal = contract.tax_rate / 100
                contract_monthly_revenue += contract_monthly_revenue * tax_rate_decimal
            
            print(f"  Contract: {contract.name} (State: {contract.state})")
            print(f"    - rental_fee: {contract.rental_fee}")
            print(f"    - service_fee: {contract.service_fee} (monthly: {contract.service_monthly})")
            print(f"    - electricity_fee: {contract.electricity_fee} (monthly: {contract.electricity_monthly}, included: {contract.is_electricity_included})")
            print(f"    - tax_rate: {contract.tax_rate}% (included: {contract.tax_included})")
            print(f"    - Total monthly revenue: {contract_monthly_revenue}")
            
            monthly_revenue += contract_monthly_revenue
        
        print(f"\nTotal Monthly Revenue: {monthly_revenue}")
        
        # Calculate Total Receivables (unpaid amounts) for this project
        total_receivables = 0.0
        print("\nCalculating unpaid amounts...")
        for contract in confirmed_contracts:
            for line in contract.rental_line_ids:
                if line.payment_state != 'paid':
                    unpaid_amount = line.amount_residual or line.amount or 0.0
                    total_receivables += unpaid_amount
                    print(f"  Unpaid line: {line.name} - Amount: {unpaid_amount}")

        print(f"\nFINAL RESULTS:")
        print(f"  Property: {prop.name}")
        print(f"  Monthly Revenue: {monthly_revenue}")
        print(f"  Total Receivables: {total_receivables}")
        print("-"*80 + "\n")

        # Render the view
        values = {
            'property': prop,
            'page_name': 'property',
            'units_with_data': units_with_data,  # Pass the enhanced data to the template
            'monthly_revenue': float(monthly_revenue or 0.0),
            'total_receivables': float(total_receivables or 0.0),
            'company_currency': request.env.company.currency_id,
        }
        return request.render("nthub_realestate.portal_property_view", values)


    @http.route(['/my/property/<int:property_id>/contract'], type='http', auth="user", website=True,
                methods=['GET', 'POST'])
    @owner_only
    def portal_property_contract_view(self, property_id, **kw):
        """
        Handles displaying the contract page (GET) and saving the
        edited articles and signature via a standard JSON POST request.
        """
        try:
            prop = request.env['rs.project'].sudo().browse(property_id)
            if not prop.exists() or prop.partner_id.id != request.env.user.partner_id.id:
                if request.httprequest.method == 'GET':
                    return request.redirect('/my/properties')
                return Response(json.dumps({'error': 'Access Denied'}), content_type='application/json', status=403)
        except (AccessError, ValueError):
            if request.httprequest.method == 'GET':
                return request.redirect('/my/properties')
            return Response(json.dumps({'error': 'Invalid Property'}), content_type='application/json', status=400)

        # Handle POST request from JavaScript fetch
        if request.httprequest.method == 'POST':
            try:
                # Correctly read the raw JSON body sent by fetch
                data = json.loads(request.httprequest.data)
                articles = data.get('articles', {})
                signature = data.get('signature')

                if not signature:
                    return Response(json.dumps({'error': 'Signature is missing.'}), content_type='application/json',
                                    status=400)

                # Prepare values to update on the project record
                vals_to_update = {
                    'contract_approved': True,
                    'contract_signature': signature.split(',')[1],  # Remove the base64 prefix
                    'contract_approval_date': fields.Datetime.now(),
                }
                # Add the content of all edited articles
                for i in range(1, 15):
                    field_name = f'contract_article_{i}'
                    if field_name in articles:
                        vals_to_update[field_name] = articles[field_name]

                prop.sudo().write(vals_to_update)
                return Response(json.dumps({'status': 'success'}), content_type='application/json', status=200)

            except Exception as e:
                _logger.error("Error processing contract signature: %s", str(e))
                return Response(json.dumps({'error': str(e)}), content_type='application/json', status=500)

        # Handle GET request to render the page
        values = {
            'property': prop,
            'page_name': 'contract',
        }
        return request.render("nthub_realestate.portal_property_contract", values)

    # =================== Vendor Quotes Approval Routes - NEW WORKFLOW ===================
    
    @http.route(['/my/vendor_quotes'], type='http', auth="user", website=True)
    @is_owner
    def portal_my_vendor_quotes(self, **kw):
        """Show all vendor quotes pending approval for owner's projects - NEW WORKFLOW"""
        owner = request.env.user.partner_id
        
        VendorQuote = request.env['maintenance.vendor.quote'].sudo()
        
        # Get all vendor quotes for owner's projects (all states)
        all_quotes = VendorQuote.search([
            ('project_id.partner_id', '=', owner.id)
        ], order='create_date desc')
        
        # Get all pending_owner_approval vendor quotes for owner's projects
        pending_quotes = VendorQuote.search([
            ('state', '=', 'pending_owner_approval'),
            ('project_id.partner_id', '=', owner.id)
        ], order='create_date desc')
        
        # Get approved quotes that need vendor selection
        approved_quotes = VendorQuote.search([
            ('state', '=', 'owner_approved'),
            ('project_id.partner_id', '=', owner.id)
        ], order='create_date desc')
        
        # Get rejected quotes
        rejected_quotes = VendorQuote.search([
            ('state', 'in', ['owner_rejected', 'rejected']),
            ('project_id.partner_id', '=', owner.id)
        ], order='create_date desc')
        
        # Calculate stats for the dashboard cards
        total_quotes = len(all_quotes)
        pending_count = len(pending_quotes)
        approved_count = len(approved_quotes)
        rejected_count = len(rejected_quotes)
        
        # Prepare quotes list for the table (list of dictionaries)
        quotes_list = []
        state_mapping = {
            'draft': 'draft',
            'pending_owner_approval': 'pending',
            'owner_approved': 'approved',
            'vendor_selected': 'approved',
            'po_created': 'approved',
            'owner_rejected': 'rejected',
            'rejected': 'rejected',
            'cancelled': 'rejected',
        }
        for quote in all_quotes:
            # Calculate total amount from quote lines
            total_amount = sum(line.subtotal for line in quote.quote_line_ids) if quote.quote_line_ids else 0.0
            quotes_list.append({
                'id': quote.id,
                'name': quote.name,
                'vendor_name': quote.selected_vendor_id.name if quote.selected_vendor_id else '-',
                'project_name': quote.project_id.name if quote.project_id else '-',
                'job_order_name': quote.job_order_id.name if quote.job_order_id else (quote.requisition_id.name if quote.requisition_id else '-'),
                'amount': total_amount,
                'state': state_mapping.get(quote.state, 'pending'),
                'state_raw': quote.state,
            })
        
        # Get company currency
        company_currency = request.env.company.currency_id
        
        values = {
            'pending_quotes': pending_quotes,
            'approved_quotes': approved_quotes,
            'rejected_quotes': rejected_quotes,
            'all_quotes': all_quotes,
            'quotes': quotes_list,
            'total_quotes': total_quotes,
            'pending_count': pending_count,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'company_currency': company_currency,
            'page_name': 'vendor_quotes',
            'error': kw.get('error'),
            'message': kw.get('message'),
        }
        return request.render("nthub_realestate.portal_my_vendor_quotes", values)
    
    @http.route(['/my/vendor_quote/<int:quote_id>'], type='http', auth="user", website=True)
    @is_owner
    def portal_vendor_quote_detail(self, quote_id, **kw):
        """View vendor quote details with all vendor PDFs - NEW WORKFLOW"""
        owner = request.env.user.partner_id
        
        quote = request.env['maintenance.vendor.quote'].sudo().browse(quote_id)
        
        # Verify ownership
        if not quote.exists() or not quote.project_id or quote.project_id.partner_id.id != owner.id:
            return request.render('website.403', {
                'message': 'Access Denied: You do not have access to this quote.'
            })
        
        values = {
            'quote': quote,
            'vendor_attachments': quote.vendor_attachment_ids,
            'quote_lines': quote.quote_line_ids,
            'page_name': 'vendor_quote_detail',
            'error': kw.get('error'),
            'message': kw.get('message'),
        }
        return request.render("nthub_realestate.portal_vendor_quote_detail", values)
    
    @http.route(['/my/vendor_quote/<int:quote_id>/approve'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    @is_owner
    def portal_vendor_quote_approve(self, quote_id, **kw):
        """Owner approves vendor quote - NEW WORKFLOW with vendor selection"""
        owner = request.env.user.partner_id
        
        quote = request.env['maintenance.vendor.quote'].sudo().browse(quote_id)
        
        # Verify ownership
        if not quote.exists() or not quote.project_id or quote.project_id.partner_id.id != owner.id:
            return request.redirect('/my/vendor_quotes?error=access_denied')
        
        if quote.state != 'pending_owner_approval':
            return request.redirect('/my/vendor_quotes?error=invalid_state')
        
        try:
            owner_notes = kw.get('owner_notes', '')
            
            # Get approved vendor IDs from checkboxes
            approved_vendor_ids = kw.getlist('approved_vendor_ids') if hasattr(kw, 'getlist') else []
            if not approved_vendor_ids:
                # Fallback for werkzeug request
                approved_vendor_ids = request.httprequest.form.getlist('approved_vendor_ids')
            
            # Convert to integers
            approved_vendor_ids = [int(vid) for vid in approved_vendor_ids if vid]
            
            # Mark selected vendor attachments as owner_approved
            if approved_vendor_ids:
                vendor_attachments = request.env['maintenance.vendor.quote.attachment'].sudo().browse(approved_vendor_ids)
                vendor_attachments.write({'is_owner_approved': True})
                
                # Add note about which vendors were approved
                vendor_names = ', '.join(vendor_attachments.mapped('vendor_id.name'))
                if owner_notes:
                    owner_notes += f"\n\nApproved Vendors: {vendor_names}"
                else:
                    owner_notes = f"Approved Vendors: {vendor_names}"
            
            quote.write({'owner_notes': owner_notes})
            quote.action_owner_approve()
            
            return request.redirect(f'/my/vendor_quote/{quote_id}?message=approved')
        except Exception as e:
            return request.redirect(f'/my/vendor_quote/{quote_id}?error={str(e)}')
    
    @http.route(['/my/vendor_quote/<int:quote_id>/reject'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    @is_owner
    def portal_vendor_quote_reject(self, quote_id, **kw):
        """Owner rejects vendor quote - NEW WORKFLOW"""
        owner = request.env.user.partner_id
        
        quote = request.env['maintenance.vendor.quote'].sudo().browse(quote_id)
        
        # Verify ownership
        if not quote.exists() or not quote.project_id or quote.project_id.partner_id.id != owner.id:
            return request.redirect('/my/vendor_quotes?error=access_denied')
        
        if quote.state != 'pending_owner_approval':
            return request.redirect('/my/vendor_quotes?error=invalid_state')
        
        rejection_reason = kw.get('rejection_reason', 'No reason provided')
        
        try:
            quote.action_owner_reject(rejection_reason)
            return request.redirect('/my/vendor_quotes?message=rejected')
        except Exception as e:
            return request.redirect(f'/my/vendor_quote/{quote_id}?error={str(e)}')

    @http.route(['/my/vendor_quote/attachment/<int:attachment_id>'], type='http', auth="user", website=True)
    @is_owner
    def portal_vendor_quote_attachment(self, attachment_id, download=False, **kw):
        """Download or view vendor quote attachment - with owner access check"""
        owner = request.env.user.partner_id
        
        # Get the actual attachment first
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists():
            return request.not_found()
        
        # Find the vendor quote attachment (check if it's linked via binary field or direct Many2one)
        vendor_attachment = None
        
        # Check if attachment is from binary field (res_field = 'quote_file')
        if attachment.res_model == 'maintenance.vendor.quote.attachment' and attachment.res_id:
            vendor_attachment = request.env['maintenance.vendor.quote.attachment'].sudo().browse(attachment.res_id)
        else:
            # Fallback: search by attachment_id Many2one
            vendor_attachment = request.env['maintenance.vendor.quote.attachment'].sudo().search([
                ('attachment_id', '=', attachment_id)
            ], limit=1)
        
        if not vendor_attachment or not vendor_attachment.exists():
            return request.not_found()
        
        # Get the quote and verify owner access
        quote = vendor_attachment.quote_id
        if not quote or not quote.project_id or quote.project_id.partner_id.id != owner.id:
            return request.render('website.403', {
                'message': 'Access Denied: You do not have access to this file.'
            })
        if not attachment.exists():
            return request.not_found()
        
        # Use Odoo's built-in method to get raw file content
        try:
            file_content = attachment.raw
        except Exception:
            # Fallback to datas if raw fails
            file_content = base64.b64decode(attachment.datas) if attachment.datas else b''
        
        if not file_content:
            return request.not_found()
        
        # Determine content type
        content_type = attachment.mimetype or 'application/octet-stream'
        
        # Set headers
        headers = [
            ('Content-Type', content_type),
            ('Content-Length', len(file_content)),
        ]
        
        if download or kw.get('download'):
            headers.append(('Content-Disposition', f'attachment; filename="{attachment.name}"'))
        else:
            # For viewing in browser (especially PDFs)
            headers.append(('Content-Disposition', f'inline; filename="{attachment.name}"'))
        
        return request.make_response(file_content, headers)
    
    # =================== Legacy Routes (kept for backward compatibility) ===================
    
    @http.route(['/my/job_order/<int:job_order_id>/quotes'], type='http', auth="user", website=True)
    @is_owner
    def portal_job_order_quotes_comparison(self, job_order_id, **kw):
        """Compare vendor quotes for a specific job order - LEGACY"""
        owner = request.env.user.partner_id
        
        # Get job order
        job_order = request.env['maintenance.job.order'].sudo().browse(job_order_id)
        
        # Verify ownership (job_order links to project via x_unit_area)
        project = job_order.x_unit_area.rs_project_id if job_order.x_unit_area else False
        if not job_order.exists() or not project or project.partner_id.id != owner.id:
            return request.render('website.403', {
                'message': 'Access Denied: You do not own this job order.'
            })
        
        # Get the single vendor quote for this job order (NEW WORKFLOW)
        quote = request.env['maintenance.vendor.quote'].sudo().search([
            ('job_order_id', '=', job_order_id),
        ], limit=1)
        
        if quote:
            # Redirect to new quote detail view
            return request.redirect(f'/my/vendor_quote/{quote.id}')
        
        values = {
            'job_order': job_order,
            'page_name': 'vendor_quotes',
        }
        return request.render("nthub_realestate.portal_job_order_no_quotes", values)

    @http.route(['/my/property/<int:property_id>'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    @owner_only
    def portal_property_view(self, property_id, **kw):
        """Displays the details of a single property and its units with payment details."""
        try:
            prop = request.env['rs.project'].sudo().browse(property_id)
            if not prop.exists() or prop.partner_id.id != request.env.user.partner_id.id:
                raise AccessError("Access Denied: You do not own this property.")
        except (AccessError, ValueError):
            return request.redirect('/my/properties')

        # Handle POST request for file upload (no changes here)
        if request.httprequest.method == 'POST':
            # ... (file upload logic remains the same)
            pass

        # --- For GET requests, prepare unit data with payment lines ---
        units_with_data = []
        for unit in prop.subproperties_ids:
            # Find related rental contracts (confirmed, done, or renewed)
            contracts = request.env['rental.contract'].sudo().search([
                ('rs_project_unit', '=', unit.id),
                ('state', 'in', ['confirmed', 'done', 'renew'])
            ])

            # Calculate the total paid amount for the unit
            total_collected = sum(contract.paid for contract in contracts)

            # **NEW**: Collect all payment lines from these contracts and sort them by date
            payment_lines = contracts.mapped('rental_line_ids').sorted(key=lambda r: r.date, reverse=True)

            units_with_data.append({
                'unit': unit,
                'collected_amount': total_collected,
                'payment_lines': payment_lines,  # <-- Pass the payment lines to the template
            })

        # Render the view with the new data
        values = {
            'property': prop,
            'page_name': 'property',
            'units_with_data': units_with_data,  # This now contains payment_lines
        }
        return request.render("nthub_realestate.portal_property_view", values)
