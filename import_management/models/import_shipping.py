# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ImportShipping(models.Model):
    _name = 'import.shipping'
    _description = 'Import Shipping'
    _order = 'eta'

    shipment_id = fields.Many2one(
        'import.shipment',
        string='Shipment',
        required=True,
        ondelete='cascade',
    )

    shipping_line = fields.Char(
        string='Shipping Line',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    carrier_id = fields.Many2one(
        'res.partner',
        string='Carrier',
        domain="[('is_company', '=', True)]",
    )

    vessel_name = fields.Char(
        string='Vessel Name',
    )

    voyage_number = fields.Char(
        string='Voyage Number',
    )

    etd = fields.Date(
        string='Estimated Departure',
    )

    eta = fields.Date(
        string='Estimated Arrival',
    )

    actual_departure = fields.Date(
        string='Actual Departure',
    )

    actual_arrival = fields.Date(
        string='Actual Arrival',
    )

    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('departed', 'Departed'),
        ('delayed', 'Delayed'),
        ('arrived', 'Arrived'),
        ('cancelled', 'Cancelled'),
    ],
        string='Status',
        default='scheduled',
        required=True,
    )

    delay_reason = fields.Text(
        string='Delay Reason',
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
            if vals.get('shipping_line', 'New') == 'New':
                vals['shipping_line'] = self.env['ir.sequence'].next_by_code('import.shipping') or 'New'
        return super().create(vals_list)

    def action_depart(self):
        self.write({
            'status': 'departed',
            'actual_departure': fields.Date.today()
        })

    def action_arrive(self):
        self.write({
            'status': 'arrived',
            'actual_arrival': fields.Date.today()
        })

    def action_mark_delayed(self):
        self.write({'status': 'delayed'})

    def action_cancel(self):
        self.write({'status': 'cancelled'})