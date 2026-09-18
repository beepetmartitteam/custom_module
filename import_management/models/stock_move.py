# -*- coding: utf-8 -*-
from odoo import models, fields


class StockMove(models.Model):
    _inherit = 'stock.move'
    
    import_container_id = fields.Many2one(
        'import.container',
        string='Import Container',
        ondelete='set null',
    )
