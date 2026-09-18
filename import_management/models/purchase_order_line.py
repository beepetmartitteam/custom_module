# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    import_shipment_id = fields.Many2one(
        'import.shipment',
        string='Import Shipment',
        ondelete='set null',
    )
    
    import_container_ids = fields.One2many(
        'import.container',
        'purchase_order_line_id',
        string='Import Containers',
    )
    
    shipped_qty = fields.Float(
        string='Shipped Quantity',
        compute='_compute_shipped_qty',
        store=True
    )
    
    @api.depends('import_container_ids.quantity')
    def _compute_shipped_qty(self):
        for line in self:
            line.shipped_qty = sum(line.import_container_ids.mapped('quantity'))
