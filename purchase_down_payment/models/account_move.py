from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    purchase_down_payment_application_ids = fields.One2many(
        'purchase.down.payment.application',
        'vendor_bill_id',
        string='Down Payment Applications',
        readonly=True,
    )

    purchase_down_payment_total = fields.Monetary(
        string='Applied Down Payment',
        currency_field='currency_id',
        compute='_compute_purchase_down_payment',
        store=True,
    )

    purchase_down_payment_remaining = fields.Monetary(
        string='Remaining After Down Payment',
        currency_field='currency_id',
        compute='_compute_purchase_down_payment',
        store=True,
    )

    @api.depends(
        'purchase_down_payment_application_ids.amount',
        'amount_total',
    )
    def _compute_purchase_down_payment(self):
        for move in self:
            if move.move_type != 'in_invoice':
                move.purchase_down_payment_total = 0.0
                move.purchase_down_payment_remaining = 0.0
                continue

            total = sum(
                move.purchase_down_payment_application_ids.mapped('amount')
            )

            move.purchase_down_payment_total = total
            move.purchase_down_payment_remaining = max(
                move.amount_total - total,
                0.0,
            )

    def action_apply_purchase_down_payment(self):
        self.ensure_one()

        if self.move_type != 'in_invoice':
            raise UserError(
                _('Down Payment can only be applied to Vendor Bills.')
            )

        if self.state != 'posted':
            raise UserError(
                _('The Vendor Bill must be posted before applying a Down Payment.')
            )

        if self.amount_residual <= 0:
            raise UserError(
                _('This Vendor Bill has no outstanding amount.')
            )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Apply Purchase Down Payment'),
            'res_model': 'purchase.down.payment.apply.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vendor_bill_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_company_id': self.company_id.id,
                'default_currency_id': self.currency_id.id,
            },
        }

    def action_view_purchase_down_payment_applications(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Down Payment Applications'),
            'res_model': 'purchase.down.payment.application',
            'view_mode': 'list,form',
            'domain': [
                ('vendor_bill_id', '=', self.id),
            ],
        }