# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'
    
    import_shipment_id = fields.Many2one(
        'import.shipment',
        string='Import Shipment',
        ondelete='set null',
    )
    
    import_container_ids = fields.One2many(
        'import.container',
        'landed_cost_id',
        string='Import Containers'
    )
    
    auto_allocate = fields.Boolean(
        string='Auto Allocate',
        default=True,
        help='Automatically allocate landed costs when validated'
    )
    
    allocation_method = fields.Selection([
        ('quantity', 'By Quantity'),
        ('value', 'By Value'),
        ('weight', 'By Weight'),
        ('volume', 'By Volume'),
    ],
        string='Allocation Method',
        default='quantity',
        required=True,
    )
    
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    @api.onchange('import_shipment_id')
    def _onchange_import_shipment_id(self):
        if self.import_shipment_id:
            self.picking_ids = self.import_shipment_id.container_ids.mapped('stock_picking_id').ids
            self.import_container_ids = self.import_shipment_id.container_ids.ids
    
    def compute_landed_cost(self):
        """Override to support custom allocation methods and currency conversion."""
        # Convert cost lines to company currency if needed
        for cost_line in self.cost_lines:
            if cost_line.currency_id and cost_line.currency_id != self.company_id.currency_id:
                cost_line.cost = cost_line.currency_id._convert(
                    cost_line.cost,
                    self.company_id.currency_id,
                    self.company_id,
                    self.date or fields.Date.today()
                )
        res = super().compute_landed_cost()
        return res
    
    def _get_valuation_lines(self):
        """Override to support import container-based allocation."""
        lines = super()._get_valuation_lines()
        
        # If allocation method is weight/volume, add those fields
        if self.allocation_method in ['weight', 'volume']:
            for line in lines:
                move = self.env['stock.move'].browse(line.get('move_id'))
                if move.import_container_id:
                    if self.allocation_method == 'weight':
                        line['weight'] = move.import_container_id.total_weight
                    elif self.allocation_method == 'volume':
                        line['volume'] = move.import_container_id.total_volume
        
        return lines
