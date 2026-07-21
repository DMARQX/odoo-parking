# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class RentalQuotationDashboardData(models.Model):
    _name = 'rental.quotation.dashboard.data'
    _description = 'Rental Quotation Dashboard Data Provider'

    @api.model
    def get_rental_quotation_dashboard_data(self):
        """
        هذه الطريقة تجلب جميع بيانات dashboard للكوتيشن
        مُحسّنة لجلب البيانات بكفاءة من rental.quotation model
        """
        Quotation = self.env['rental.quotation']
        QuotationLine = self.env['rental.quotation.line']

        # 1. --- إحصائيات KPIs (مؤشرات الأداء الرئيسية) ---
        total_quotations = Quotation.search_count([])
        draft_quotations = Quotation.search_count([('state', '=', 'draft')])
        submitted_quotations = Quotation.search_count([('state', '=', 'submitted')])
        approved_quotations = Quotation.search_count([('state', '=', 'approved')])
        rejected_quotations = Quotation.search_count([('state', '=', 'rejected')])
        
        # إجمالي قيمة الكوتيشن
        total_quotation_value = sum(Quotation.search([('state', '!=', 'rejected')]).mapped('total_amount'))
        
        # متوسط قيمة الكوتيشن
        avg_quotation_value = total_quotation_value / total_quotations if total_quotations > 0 else 0

        # 2. --- Chart: Quotations by Status ---
        quotation_status_data = Quotation.read_group(
            domain=[],
            fields=['state'],
            groupby=['state'],
        )
        
        # ترجمة حالات الكوتيشن للإنجليزية
        state_labels_english = {
            'draft': 'Draft',
            'submitted': 'Submitted',
            'under_review': 'Under Review', 
            'approved': 'Approved',
            'rejected': 'Rejected',
            'expired': 'Expired'
        }
        
        status_labels = [state_labels_english.get(d['state'], d['state']) for d in quotation_status_data]
        status_values = [d['state_count'] for d in quotation_status_data]

        # 3. --- Chart: Monthly Quotations Created ---
        # آخر 12 شهر
        end_date = datetime.now()
        start_date = end_date - relativedelta(months=12)
        
        quotations_by_month = Quotation.read_group(
            domain=[('create_date', '>=', start_date.strftime('%Y-%m-%d'))],
            fields=['create_date'],
            groupby=['create_date:month']
        )
        
        monthly_labels = []
        monthly_values = []
        
        for month_data in quotations_by_month:
            month_name = month_data['create_date:month']
            monthly_labels.append(month_name)
            monthly_values.append(month_data['create_date_count'])

        # 4. --- Chart: Quotation Value by Month ---
        # استعلام SQL مُحسّن لجمع القيم الشهرية
        query = """
            SELECT
                TO_CHAR(rq.create_date, 'YYYY-MM') as month,
                SUM(rq.total_amount) as total_value,
                COUNT(rq.id) as quotation_count
            FROM
                rental_quotation rq
            WHERE
                rq.create_date >= %s
                AND rq.state != 'rejected'
            GROUP BY
                TO_CHAR(rq.create_date, 'YYYY-MM')
            ORDER BY
                month;
        """
        self.env.cr.execute(query, (start_date.strftime('%Y-%m-%d'),))
        monthly_value_data = self.env.cr.dictfetchall()
        
        value_labels = [m['month'] for m in monthly_value_data]
        value_amounts = [float(m['total_value']) if m['total_value'] else 0 for m in monthly_value_data]

        # 5. --- الكوتيشن الأحدث ---
        recent_quotations = Quotation.search([
            ('state', '!=', 'rejected')
        ], order='create_date desc', limit=5)
        
        recent_data = []
        for quotation in recent_quotations:
            recent_data.append({
                'id': quotation.id,
                'quotation_number': quotation.name or f'Q-{quotation.id}',
                'partner_name': quotation.partner_id.name if quotation.partner_id else 'Not Specified',
                'total_amount': quotation.total_amount or 0,
                'state': state_labels_english.get(quotation.state, quotation.state),
                'create_date': quotation.create_date.strftime('%Y-%m-%d') if quotation.create_date else ''
            })

        # 6. --- إرجاع جميع البيانات في dictionary واحد ---
        return {
            # الإحصائيات الأساسية
            'total_quotations': total_quotations,
            'draft_quotations': draft_quotations,
            'submitted_quotations': submitted_quotations,
            'approved_quotations': approved_quotations,
            'rejected_quotations': rejected_quotations,
            'total_quotation_value': total_quotation_value,
            'avg_quotation_value': avg_quotation_value,
            
            # بيانات الرسوم البيانية
            'quotation_status_chart': {
                'labels': status_labels,
                'values': status_values,
            },
            'monthly_quotations_chart': {
                'labels': monthly_labels,
                'values': monthly_values,
            },
            'monthly_value_chart': {
                'labels': value_labels,
                'values': value_amounts,
            },
            
            # البيانات الإضافية
            'recent_quotations': recent_data,
        }