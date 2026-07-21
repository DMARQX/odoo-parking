# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class RentalQuotationCRMIntegration(models.Model):
    _inherit = 'rental.quotation'

    # CRM Integration fields
    opportunity_id = fields.Many2one('crm.lead', 'Related Opportunity')
    lead_source = fields.Selection([
        ('website', 'Website'),
        ('phone', 'Phone Call'),
        ('email', 'Email'),
        ('referral', 'Referral'),
        ('advertisement', 'Advertisement'),
        ('social_media', 'Social Media'),
        ('walk_in', 'Walk-in'),
        ('other', 'Other'),
    ], 'Lead Source')
    campaign_id = fields.Many2one('utm.campaign', 'Campaign')
    medium_id = fields.Many2one('utm.medium', 'Medium')
    source_id = fields.Many2one('utm.source', 'Source')

    @api.model
    def create_from_opportunity(self, opportunity_id, quotation_data):
        """Create quotation from CRM opportunity"""
        opportunity = self.env['crm.lead'].browse(opportunity_id)
        if not opportunity.exists():
            raise ValueError("Opportunity not found")
        
        # Prepare quotation data
        quotation_vals = {
            'partner_id': opportunity.partner_id.id,
            'opportunity_id': opportunity.id,
            'lead_source': quotation_data.get('lead_source', 'website'),
            'campaign_id': opportunity.campaign_id.id if opportunity.campaign_id else False,
            'medium_id': opportunity.medium_id.id if opportunity.medium_id else False,
            'source_id': opportunity.source_id.id if opportunity.source_id else False,
            'notes': quotation_data.get('notes', ''),
        }
        
        # Merge with provided data
        quotation_vals.update(quotation_data)
        
        # Create quotation
        quotation = self.create(quotation_vals)
        
        # Update opportunity stage if needed
        if quotation_data.get('update_opportunity_stage'):
            stage = self.env['crm.stage'].search([
                ('name', 'ilike', 'quotation'),
                ('team_id', '=', opportunity.team_id.id)
            ], limit=1)
            if stage:
                opportunity.stage_id = stage.id
        
        # Log activity in opportunity
        opportunity.message_post(
            body=f"Rental quotation {quotation.name} created",
            subject="Quotation Created"
        )
        
        return quotation

    def sync_to_crm(self):
        """Sync quotation data to CRM opportunity"""
        self.ensure_one()
        if not self.opportunity_id:
            return
        
        # Update opportunity expected revenue
        if self.total_amount:
            self.opportunity_id.expected_revenue = self.total_amount
        
        # Add quotation information to opportunity description
        description = f"""
Quotation Details:
- Number: {self.name}
- Date: {self.quotation_date}
- Total Amount: {self.total_amount}
- State: {dict(self._fields['state'].selection)[self.state]}

Units:
"""
        for line in self.quotation_line_ids:
            description += f"- {line.property_id.name if line.property_id else 'N/A'} - "
            description += f"{line.unit_id.name if line.unit_id else 'N/A'}: {line.rental_amount}\n"
        
        # Update opportunity
        self.opportunity_id.write({
            'description': description,
            'expected_revenue': self.total_amount,
        })
        
        # Log activity
        self.opportunity_id.message_post(
            body=f"Quotation {self.name} updated - Total: {self.total_amount}",
            subject="Quotation Updated"
        )

    def convert_to_opportunity(self):
        """Convert quotation to CRM opportunity if not linked"""
        self.ensure_one()
        if self.opportunity_id:
            return self.opportunity_id
        
        # Create new opportunity
        opportunity_vals = {
            'name': f"Rental Opportunity - {self.partner_id.name}",
            'partner_id': self.partner_id.id,
            'expected_revenue': self.total_amount,
            'description': f"Created from rental quotation {self.name}",
            'user_id': self.env.user.id,
            'team_id': self.env['crm.team'].search([], limit=1).id,
            'campaign_id': self.campaign_id.id if self.campaign_id else False,
            'medium_id': self.medium_id.id if self.medium_id else False,
            'source_id': self.source_id.id if self.source_id else False,
        }
        
        opportunity = self.env['crm.lead'].create(opportunity_vals)
        self.opportunity_id = opportunity.id
        
        return opportunity

    @api.model
    def get_crm_analytics(self):
        """Get CRM analytics for quotations"""
        domain = [('opportunity_id', '!=', False)]
        quotations = self.search(domain)
        
        # Group by lead source
        source_data = {}
        for quotation in quotations:
            source = quotation.lead_source or 'unknown'
            if source not in source_data:
                source_data[source] = {
                    'count': 0,
                    'total_amount': 0,
                    'approved_count': 0,
                    'approved_amount': 0
                }
            
            source_data[source]['count'] += 1
            source_data[source]['total_amount'] += quotation.total_amount or 0
            
            if quotation.state == 'approved':
                source_data[source]['approved_count'] += 1
                source_data[source]['approved_amount'] += quotation.total_amount or 0
        
        # Group by campaign
        campaign_data = {}
        for quotation in quotations.filtered('campaign_id'):
            campaign = quotation.campaign_id.name
            if campaign not in campaign_data:
                campaign_data[campaign] = {
                    'count': 0,
                    'total_amount': 0,
                    'conversion_rate': 0
                }
            
            campaign_data[campaign]['count'] += 1
            campaign_data[campaign]['total_amount'] += quotation.total_amount or 0
        
        # Calculate conversion rates
        for source in source_data:
            if source_data[source]['count'] > 0:
                source_data[source]['conversion_rate'] = (
                    source_data[source]['approved_count'] / source_data[source]['count']
                ) * 100
        
        return {
            'by_source': source_data,
            'by_campaign': campaign_data,
            'total_linked': len(quotations),
            'total_opportunities': self.env['crm.lead'].search_count([]),
        }

    def update_opportunity_stage(self, stage_name):
        """Update related opportunity stage"""
        self.ensure_one()
        if not self.opportunity_id:
            return False
        
        stage = self.env['crm.stage'].search([
            ('name', 'ilike', stage_name),
            ('team_id', '=', self.opportunity_id.team_id.id)
        ], limit=1)
        
        if stage:
            self.opportunity_id.stage_id = stage.id
            self.opportunity_id.message_post(
                body=f"Stage updated to {stage.name} from quotation {self.name}",
                subject="Stage Updated"
            )
            return True
        
        return False

    @api.model
    def auto_sync_opportunities(self):
        """Auto sync quotations with opportunities (for scheduled actions)"""
        quotations = self.search([
            ('opportunity_id', '!=', False),
            ('state', 'in', ['approved', 'rejected', 'converted'])
        ])
        
        for quotation in quotations:
            try:
                if quotation.state == 'approved':
                    quotation.update_opportunity_stage('won')
                elif quotation.state == 'rejected':
                    quotation.update_opportunity_stage('lost')
                elif quotation.state == 'converted':
                    quotation.update_opportunity_stage('won')
                    
                quotation.sync_to_crm()
                
            except Exception as e:
                _logger.error(f"Error syncing quotation {quotation.name} to CRM: {str(e)}")
        
        return True

class CRMLeadExtended(models.Model):
    _inherit = 'crm.lead'

    rental_quotation_ids = fields.One2many(
        'rental.quotation', 
        'opportunity_id', 
        'Rental Quotations'
    )
    rental_quotations_count = fields.Integer(
        'Quotations Count',
        compute='_compute_rental_quotations_count'
    )

    def _compute_rental_quotations_count(self):
        for record in self:
            record.rental_quotations_count = len(record.rental_quotation_ids)

    def action_create_rental_quotation(self):
        """Action to create rental quotation from opportunity"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Rental Quotation',
            'res_model': 'rental.quotation',
            'view_mode': 'form',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_opportunity_id': self.id,
                'default_campaign_id': self.campaign_id.id,
                'default_medium_id': self.medium_id.id,
                'default_source_id': self.source_id.id,
            },
            'target': 'current',
        }

    def action_view_rental_quotations(self):
        """Action to view all rental quotations for this opportunity"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rental Quotations',
            'res_model': 'rental.quotation',
            'view_mode': 'list,form',
            'domain': [('opportunity_id', '=', self.id)],
            'context': {'default_opportunity_id': self.id},
        }