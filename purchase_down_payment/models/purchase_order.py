from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    proforma_ids = fields.One2many(
        'purchase.proforma',
        'purchase_order_id',
        string='Supplier Proforma Invoices',
    )

    down_payment_ids = fields.One2many(
        'purchase.down.payment',
        'purchase_order_id',
        string='Down Payments',
    )

    proforma_count = fields.Integer(
        string='Proforma Count',
        compute='_compute_purchase_down_payment_counts',
    )

    down_payment_count = fields.Integer(
        string='Down Payment Count',
        compute='_compute_purchase_down_payment_counts',
    )

    @api.depends('proforma_ids', 'down_payment_ids')
    def _compute_purchase_down_payment_counts(self):
        for order in self:
            order.proforma_count = len(order.proforma_ids)
            order.down_payment_count = len(order.down_payment_ids)

    def action_view_proformas(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Supplier Proforma Invoices',
            'res_model': 'purchase.proforma',
            'view_mode': 'list,form',
            'domain': [
                ('purchase_order_id', '=', self.id),
            ],
            'context': {
                'default_purchase_order_id': self.id,
            },
        }

    def action_view_down_payments(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Down Payments',
            'res_model': 'purchase.down.payment',
            'view_mode': 'list,form',
            'domain': [
                ('purchase_order_id', '=', self.id),
            ],
            'context': {
                'default_purchase_order_id': self.id,
            },
        }

    def action_create_proforma(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Supplier Proforma Invoice',
            'res_model': 'purchase.proforma',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_purchase_order_id': self.id,
            },
        }