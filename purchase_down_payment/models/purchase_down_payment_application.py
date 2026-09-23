from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseDownPaymentApplication(models.Model):
    _name = 'purchase.down.payment.application'
    _description = 'Purchase Down Payment Application'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )

    down_payment_id = fields.Many2one(
        'purchase.down.payment',
        string='Down Payment',
        required=True,
        ondelete='restrict',
        index=True,
    )

    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        required=True,
        ondelete='restrict',
        index=True,
    )

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        related='down_payment_id.purchase_order_id',
        store=True,
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        related='down_payment_id.partner_id',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='down_payment_id.company_id',
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='down_payment_id.currency_id',
        store=True,
        readonly=True,
    )

    amount = fields.Monetary(
        string='Applied Amount',
        currency_field='currency_id',
        required=True,
    )

    date = fields.Date(
        string='Application Date',
        required=True,
        default=fields.Date.context_today,
    )

    application_move_id = fields.Many2one(
        'account.move',
        string='Application Journal Entry',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    state = fields.Selection(
        [
            ('posted', 'Posted'),
            ('reversed', 'Reversed'),
        ],
        string='Status',
        default='posted',
        required=True,
        readonly=True,
    )

    notes = fields.Text(
        string='Notes',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'purchase.down.payment.application'
                ) or _('New')

        return super().create(vals_list)

    @api.constrains(
        'amount',
        'down_payment_id',
        'vendor_bill_id',
    )
    def _check_application(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(
                    _('Applied amount must be greater than zero.')
                )

            dp = record.down_payment_id
            bill = record.vendor_bill_id

            if not dp or not bill:
                continue

            if bill.move_type != 'in_invoice':
                raise ValidationError(
                    _('Down Payment can only be applied to Vendor Bills.')
                )

            if bill.state != 'posted':
                raise ValidationError(
                    _('The Vendor Bill must be posted before applying a Down Payment.')
                )

            if bill.company_id != dp.company_id:
                raise ValidationError(
                    _(
                        'Vendor Bill and Down Payment must belong '
                        'to the same company.'
                    )
                )

            if bill.partner_id != dp.partner_id:
                raise ValidationError(
                    _(
                        'Vendor Bill and Down Payment must belong '
                        'to the same vendor.'
                    )
                )

            if bill.currency_id != dp.currency_id:
                raise ValidationError(
                    _(
                        'Vendor Bill and Down Payment must use '
                        'the same currency.'
                    )
                )

    def action_view_journal_entry(self):
        self.ensure_one()

        if not self.application_move_id:
            raise UserError(
                _('No application journal entry exists.')
            )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Application Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.application_move_id.id,
        }

    def action_view_vendor_bill(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.vendor_bill_id.id,
        }