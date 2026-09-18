# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ImportContainer(models.Model):
    _name = 'import.container'
    _description = 'Import Container'
    _order = 'name'

    name = fields.Char(
        string='Container Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    container_type = fields.Selection([
        ('20ft', '20ft'),
        ('40ft', '40ft'),
        ('40ft_hc', '40ft High Cube'),
        ('45ft', '45ft'),
        ('reefer', 'Reefer'),
    ],
        string='Container Type',
        required=True,
    )

    shipment_id = fields.Many2one(
        'import.shipment',
        string='Shipment',
        required=True,
        ondelete='cascade',
    )

    seal_number = fields.Char(
        string='Seal Number',
    )

    weight = fields.Float(
        string='Weight (KG)',
    )

    volume = fields.Float(
        string='Volume (CBM)',
    )

    status = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived'),
        ('unloaded', 'Unloaded'),
        ('empty', 'Empty'),
    ],
        string='Status',
        default='draft',
        required=True,
    )

    loading_date = fields.Date(
        string='Loading Date',
    )

    unloading_date = fields.Date(
        string='Unloading Date',
    )

    notes = fields.Text(
        string='Notes',
    )

    active = fields.Boolean(
        default=True,
    )
    
    # Stock Integration
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking',
        ondelete='set null',
    )
    
    stock_move_ids = fields.One2many(
        'stock.move',
        'import_container_id',
        string='Stock Moves'
    )
    
    purchase_order_line_id = fields.Many2one(
        'purchase.order.line',
        string='Purchase Order Line',
        ondelete='set null',
    )
    
    product_id = fields.Many2one(
        'product.product',
        related='purchase_order_line_id.product_id',
        string='Product',
        store=True,
        readonly=True,
    )
    
    quantity = fields.Float(
        related='purchase_order_line_id.product_qty',
        string='Quantity',
        store=True,
        readonly=True,
    )
    
    total_weight = fields.Float(
        string='Total Weight (KG)',
        compute='_compute_total_weight',
        store=True
    )
    
    total_volume = fields.Float(
        string='Total Volume (CBM)',
        compute='_compute_total_volume',
        store=True
    )
    
    total_value = fields.Float(
        string='Total Value',
        compute='_compute_total_value',
        store=True
    )
    
    landed_cost_id = fields.Many2one(
        'stock.landed.cost',
        string='Landed Cost',
        ondelete='set null',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('import.container') or 'New'
        return super().create(vals_list)

    def action_load(self):
        self.write({'status': 'loaded', 'loading_date': fields.Date.today()})

    def action_unload(self):
        self.write({'status': 'unloaded', 'unloading_date': fields.Date.today()})
    
    @api.depends('weight')
    def _compute_total_weight(self):
        for record in self:
            record.total_weight = record.weight
    
    @api.depends('volume')
    def _compute_total_volume(self):
        for record in self:
            record.total_volume = record.volume
    
    @api.depends('purchase_order_line_id.price_subtotal')
    def _compute_total_value(self):
        for record in self:
            record.total_value = record.purchase_order_line_id.price_subtotal if record.purchase_order_line_id else 0