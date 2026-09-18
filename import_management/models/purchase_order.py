# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    import_shipment_ids = fields.One2many(
        'import.shipment',
        'purchase_order_id',
        string='Import Shipments',
    )
    
    import_shipment_count = fields.Integer(
        string='Import Shipment Count',
        compute='_compute_import_shipment_count',
    )
    
    @api.depends('import_shipment_ids')
    def _compute_import_shipment_count(self):
        for order in self:
            order.import_shipment_count = len(order.import_shipment_ids)
    
    def action_view_import_shipments(self):
        self.ensure_one()
        return {
            'name': 'Import Shipments',
            'type': 'ir.actions.act_window',
            'res_model': 'import.shipment',
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id},
        }
    
    def action_create_import_shipment(self):
        self.ensure_one()
        # Create shipment with PO line information
        shipment_vals = {
            'purchase_order_id': self.id,
            'supplier_id': self.partner_id.id,
            'shipment_date': fields.Date.today(),
        }
        shipment = self.env['import.shipment'].create(shipment_vals)
        
        # Create containers for each PO line
        for line in self.order_line:
            if line.product_id:
                container_vals = {
                    'shipment_id': shipment.id,
                    'name': f"{line.product_id.default_code or 'CONT'}-{line.id}",
                    'container_type': '20ft',
                    'purchase_order_line_id': line.id,
                }
                self.env['import.container'].create(container_vals)
        
        return {
            'name': 'Import Shipment',
            'type': 'ir.actions.act_window',
            'res_model': 'import.shipment',
            'res_id': shipment.id,
            'view_mode': 'form',
        }
