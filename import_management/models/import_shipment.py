from odoo import models, fields, api


class ImportShipment(models.Model):
    _name = "import.shipment"
    _description = "Import Shipment"
    _order = "shipment_date desc, id desc"

    name = fields.Char(
        string="Shipment Number",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )

    shipment_date = fields.Date(
        string="Shipment Date",
        default=fields.Date.context_today,
        required=True,
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain="[('is_company', '=', True)]",
    )

    origin_country = fields.Char(
        string="Origin Country",
    )

    destination = fields.Char(
        string="Destination",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_transit", "In Transit"),
            ("arrived", "Arrived"),
            ("received", "Received"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    notes = fields.Text(
        string="Notes",
    )

    active = fields.Boolean(
        default=True,
    )
    
    # New relationships and computed fields
    container_ids = fields.One2many(
        'import.container',
        'shipment_id',
        string='Containers'
    )
    
    shipping_ids = fields.One2many(
        'import.shipping',
        'shipment_id',
        string='Shipping Lines'
    )
    
    document_ids = fields.One2many(
        'import.document',
        'shipment_id',
        string='Documents'
    )
    
    total_containers = fields.Integer(
        string='Total Containers',
        compute='_compute_total_containers',
        store=True
    )
    
    total_weight = fields.Float(
        string='Total Weight (KG)',
        compute='_compute_total_weight',
        store=True
    )
    
    estimated_arrival = fields.Date(
        string='Estimated Arrival',
        compute='_compute_estimated_arrival',
        store=True
    )
    
    # Landed Cost Integration
    landed_cost_ids = fields.One2many(
        'stock.landed.cost',
        'import_shipment_id',
        string='Landed Costs'
    )
    
    landed_cost_count = fields.Integer(
        string='Landed Cost Count',
        compute='_compute_landed_cost_count'
    )
    
    total_landed_cost = fields.Monetary(
        string='Total Landed Cost',
        currency_field='currency_id',
        compute='_compute_total_landed_cost',
        store=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        ondelete='set null',
    )
    
    purchase_order_line_ids = fields.One2many(
        'purchase.order.line',
        'import_shipment_id',
        string='Purchase Order Lines',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "import.shipment"
                ) or "New"

        return super().create(vals_list)

    def action_confirm(self):
        self.write({
            "state": "confirmed"
        })

    def action_in_transit(self):
        self.write({
            "state": "in_transit"
        })

    def action_arrived(self):
        self.write({
            "state": "arrived"
        })

    def action_received(self):
        self.write({
            "state": "received"
        })

    def action_done(self):
        self.write({
            "state": "done"
        })

    def action_cancel(self):
        self.write({
            "state": "cancelled"
        })

    def action_reset_draft(self):
        self.write({
            "state": "draft"
        })
    
    @api.depends('container_ids')
    def _compute_total_containers(self):
        for record in self:
            record.total_containers = len(record.container_ids)
    
    @api.depends('container_ids.weight')
    def _compute_total_weight(self):
        for record in self:
            record.total_weight = sum(record.container_ids.mapped('weight'))
    
    @api.depends('shipping_ids.eta')
    def _compute_estimated_arrival(self):
        for record in self:
            if record.shipping_ids:
                # Get the earliest ETA from shipping lines
                arrivals = record.shipping_ids.filtered('eta').mapped('eta')
                if arrivals:
                    record.estimated_arrival = min(arrivals)
                else:
                    record.estimated_arrival = False
            else:
                record.estimated_arrival = False
    
    @api.depends('landed_cost_ids')
    def _compute_landed_cost_count(self):
        for record in self:
            record.landed_cost_count = len(record.landed_cost_ids)
    
    @api.depends('landed_cost_ids')
    def _compute_total_landed_cost(self):
        for record in self:
            record.total_landed_cost = sum(record.landed_cost_ids.mapped('amount_total'))
    
    def action_view_landed_costs(self):
        self.ensure_one()
        return {
            'name': 'Landed Costs',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.landed.cost',
            'view_mode': 'list,form',
            'domain': [('import_shipment_id', '=', self.id)],
            'context': {'default_import_shipment_id': self.id},
        }
    
    def action_create_landed_cost(self):
        self.ensure_one()
        return {
            'name': 'Create Landed Cost',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.landed.cost',
            'view_mode': 'form',
            'context': {
                'default_import_shipment_id': self.id,
                'default_picking_ids': self.container_ids.mapped('stock_picking_id').ids,
            },
        }