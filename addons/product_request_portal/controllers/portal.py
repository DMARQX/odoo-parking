from odoo import http, _, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from datetime import datetime, timedelta
from collections import defaultdict
import json


class ProductRequestPortal(CustomerPortal):

    @http.route(['/my/product_requests/dashboard'], type='http', auth="user", website=True)
    def portal_product_requests_dashboard(self, **kw):
        """Display dashboard with statistics"""
        partner = request.env.user.partner_id
        
        # Check access
        if not partner.is_product_requester:
            return request.redirect('/my')
        
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'product_request_dashboard',
        })
        
        return request.render("product_request_portal.portal_product_requests_dashboard", values)

    @http.route(['/my/product_requests/dashboard/data'], type='json', auth="user")
    def portal_product_requests_dashboard_data(self, **kw):
        """Get dashboard statistics data"""
        partner = request.env.user.partner_id
        
        if not partner.is_product_requester:
            return {}
        
        # Get all user requests
        domain = [('partner_id', '=', partner.id)]
        requests = request.env['product.request'].sudo().search(domain)
        
        # Calculate statistics
        total_requests = len(requests)
        total_items = sum(len(req.request_line_ids) for req in requests)
        
        # Requests by status
        status_counts = {}
        for req in requests:
            state = dict(req._fields['state'].selection).get(req.state, req.state)
            status_counts[state] = status_counts.get(state, 0) + 1
        
        # Most requested products
        product_counts = defaultdict(lambda: {'count': 0, 'quantity': 0})
        for req in requests:
            for line in req.request_line_ids:
                product_counts[line.product_id.name]['count'] += 1
                product_counts[line.product_id.name]['quantity'] += line.quantity
        
        # Sort by count and get top 10
        top_products = sorted(
            [{'name': k, **v} for k, v in product_counts.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:10]
        
        # Monthly trend (last 6 months)
        today = datetime.now()
        monthly_data = []
        for i in range(5, -1, -1):
            month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_requests = requests.filtered(
                lambda r: r.request_date and 
                         month_start.date() <= fields.Date.from_string(r.request_date) <= month_end.date()
            )
            
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'count': len(month_requests)
            })
        
        return {
            'total_requests': total_requests,
            'total_items': total_items,
            'status_counts': status_counts,
            'top_products': top_products,
            'monthly_trend': monthly_data,
        }

    @http.route(['/my/product_requests', '/my/product_requests/page/<int:page>'], 
                type='http', auth="user", website=True)
    def portal_my_product_requests(self, page=1, **kw):
        """Display product requests for portal user"""
        partner = request.env.user.partner_id
        
        # Check if user can access requests
        if not partner.is_product_requester:
            return request.redirect('/my')
        
        # Get requests
        domain = [('partner_id', '=', partner.id)]
        product_requests = request.env['product.request'].sudo().search(domain)
        
        values = self._prepare_portal_layout_values()
        values.update({
            'requests': product_requests,
            'page_name': 'product_request',
            'default_url': '/my/product_requests',
        })
        
        return request.render("product_request_portal.portal_my_product_requests", values)

    @http.route(['/my/product_request/<int:request_id>'], type='http', auth="user", website=True)
    def portal_product_request_detail(self, request_id, **kw):
        """Display product request detail"""
        partner = request.env.user.partner_id
        
        try:
            product_request = request.env['product.request'].sudo().browse(request_id)
            if not product_request.exists() or product_request.partner_id != partner:
                return request.redirect('/my/product_requests')
        except:
            return request.redirect('/my/product_requests')
        
        values = self._prepare_portal_layout_values()
        values.update({
            'product_request': product_request,
            'page_name': 'product_request',
        })
        
        return request.render("product_request_portal.portal_product_request_detail", values)

    @http.route(['/my/product_requests/new'], type='http', auth="user", website=True, methods=['GET'])
    def portal_new_product_request(self, **kw):
        """Create new product request form"""
        partner = request.env.user.partner_id
        
        # Check access
        if not partner.is_product_requester:
            return request.redirect('/my')
        
        # Get locations
        source_locations = request.env['stock.location'].sudo().search([('usage', '=', 'internal')])
        dest_locations = request.env['stock.location'].sudo().search([('usage', '=', 'internal')])
        
        # Get products - filter by allowed products if configured
        products_domain = [('type', 'in', ['product', 'consu'])]
        if partner.allowed_product_ids:
            products_domain.append(('id', 'in', partner.allowed_product_ids.ids))
        products = request.env['product.product'].sudo().search(products_domain)
        
        # Get units of measure with categories
        uoms = request.env['uom.uom'].sudo().search([])
        uom_categories = request.env['uom.category'].sudo().search([])
        
        values = self._prepare_portal_layout_values()
        values.update({
            'source_locations': source_locations,
            'dest_locations': dest_locations,
            'products': products,
            'uoms': uoms,
            'uom_categories': uom_categories,
            'page_name': 'new_product_request',
            'error': kw.get('error', ''),
        })
        
        return request.render("product_request_portal.portal_new_product_request", values)

    @http.route(['/my/product_requests/create'], type='http', auth="user", website=True, methods=['POST'])
    def portal_create_product_request(self, **post):
        """Create new product request"""
        partner = request.env.user.partner_id
        
        # Check access
        if not partner.is_product_requester:
            return request.redirect('/my')
        
        try:
            # Create product request
            vals = {
                'partner_id': partner.id,
                'source_location_id': int(post.get('source_location_id')),
                'dest_location_id': int(post.get('dest_location_id')),
                'state': 'submitted',
            }
            
            product_request = request.env['product.request'].sudo().create(vals)
            
            # Create request lines
            line_keys = [key for key in post.keys() if key.startswith('product_id_')]
            lines_created = 0
            for key in line_keys:
                line_num = key.split('_')[-1]
                product_id = post.get(f'product_id_{line_num}')
                quantity = post.get(f'quantity_{line_num}')
                product_uom_id = post.get(f'uom_id_{line_num}')
                
                if product_id and quantity and product_uom_id:
                    request.env['product.request.line'].sudo().create({
                        'request_id': product_request.id,
                        'product_id': int(product_id),
                        'quantity': float(quantity),
                        'product_uom_id': int(product_uom_id),
                    })
                    lines_created += 1
            
            # Check if at least one line was created
            if lines_created == 0:
                product_request.sudo().unlink()
                return request.redirect('/my/product_requests/new?error=Please add at least one product / الرجاء إضافة منتج واحد على الأقل')
            
            # Redirect to success page
            return request.redirect('/my/product_requests/success/%s' % product_request.id)
            
        except Exception as e:
            return request.redirect('/my/product_requests/new?error=%s' % str(e))
    
    @http.route(['/my/product_requests/success/<int:request_id>'], type='http', auth="user", website=True)
    def portal_product_request_success(self, request_id, **kw):
        """Display success page after creating request"""
        partner = request.env.user.partner_id
        
        try:
            product_request = request.env['product.request'].sudo().browse(request_id)
            if not product_request.exists() or product_request.partner_id != partner:
                return request.redirect('/my/product_requests')
        except:
            return request.redirect('/my/product_requests')
        
        values = self._prepare_portal_layout_values()
        values.update({
            'product_request': product_request,
            'page_name': 'product_request_success',
        })
        
        return request.render("product_request_portal.portal_product_request_success", values)

    @http.route(['/my/product_requests/dashboard_data'], type='json', auth="user", website=True)
    def get_dashboard_data(self, **kw):
        """JSON endpoint to provide chart data"""
        partner = request.env.user.partner_id
        
        if not partner.is_product_requester:
            return {}
        
        # Status data
        status_data = []
        states = ['draft', 'submitted', 'approved', 'received', 'cancelled']
        for state in states:
            count = request.env['product.request'].sudo().search_count([
                ('partner_id', '=', partner.id),
                ('state', '=', state)
            ])
            status_data.append({'name': state, 'value': count})
        
        # Monthly data - simplified
        monthly_data = []
        for i in range(6, 0, -1):
            import datetime
            today = datetime.date.today()
            month_start = today.replace(day=1) - datetime.timedelta(days=30*i)
            month_end = today.replace(day=1) - datetime.timedelta(days=30*(i-1))
            
            count = request.env['product.request'].sudo().search_count([
                ('partner_id', '=', partner.id),
                ('request_date', '>=', month_start),
                ('request_date', '<', month_end)
            ])
            
            monthly_data.append({
                'month': month_start.strftime('%Y-%m'),
                'count': count
            })
        
        return {
            'status_data': status_data,
            'monthly_data': monthly_data,
        }