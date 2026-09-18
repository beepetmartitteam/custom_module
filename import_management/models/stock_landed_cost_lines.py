# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockLandedCostLines(models.Model):
    _inherit = 'stock.landed.cost.lines'
    
    import_container_id = fields.Many2one(
        'import.container',
        string='Import Container',
        ondelete='set null',
    )
    
    product_qty = fields.Float(
        string='Quantity',
        help='Quantity for allocation calculation'
    )
    
    product_weight = fields.Float(
        string='Weight (KG)',
        help='Weight for allocation calculation'
    )
    
    product_volume = fields.Float(
        string='Volume (CBM)',
        help='Volume for allocation calculation'
    )
    
    currency_id = fields.Many2one(
        related='cost_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    @api.onchange('import_container_id')
    def _onchange_import_container_id(self):
        if self.import_container_id:
            self.product_qty = self.import_container_id.quantity
            self.product_weight = self.import_container_id.total_weight
            self.product_volume = self.import_container_id.total_volume
