# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ImportDocument(models.Model):
    _name = 'import.document'
    _description = 'Import Document'
    _order = 'document_date desc, id desc'

    shipment_id = fields.Many2one(
        'import.shipment',
        string='Shipment',
        required=True,
        ondelete='cascade',
    )

    document_type = fields.Selection([
        ('bl', 'Bill of Lading'),
        ('invoice', 'Commercial Invoice'),
        ('packing_list', 'Packing List'),
        ('coa', 'Certificate of Analysis'),
        ('certificate', 'Certificate'),
        ('insurance', 'Insurance'),
        ('customs', 'Customs Declaration'),
        ('other', 'Other'),
    ],
        string='Document Type',
        required=True,
    )

    document_number = fields.Char(
        string='Document Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    document_date = fields.Date(
        string='Document Date',
        required=True,
        default=fields.Date.context_today,
    )

    attachment = fields.Binary(
        string='File Attachment',
    )

    attachment_name = fields.Char(
        string='Attachment Name',
    )

    expiry_date = fields.Date(
        string='Expiry Date',
    )

    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ],
        string='Status',
        default='draft',
        required=True,
    )

    notes = fields.Text(
        string='Notes',
    )

    active = fields.Boolean(
        default=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('document_number', 'New') == 'New':
                vals['document_number'] = self.env['ir.sequence'].next_by_code('import.document') or 'New'
        return super().create(vals_list)

    @api.depends('expiry_date')
    def _check_expiry(self):
        for document in self:
            if document.expiry_date and document.expiry_date < fields.Date.today() and document.status not in ['rejected', 'expired']:
                document.status = 'expired'

    def action_submit(self):
        self.write({'status': 'submitted'})

    def action_approve(self):
        self.write({'status': 'approved'})

    def action_reject(self):
        self.write({'status': 'rejected'})

    def action_reset_draft(self):
        self.write({'status': 'draft'})