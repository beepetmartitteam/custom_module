from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseDownPayment(models.Model):
    _name = 'purchase.down.payment'
    _inherit = ['mail.thread']
    _description = 'Purchase Down Payment'
    _order = 'id desc'

    name = fields.Char(
        string='Down Payment Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    proforma_id = fields.Many2one(
        'purchase.proforma',
        string='Supplier Proforma',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    partner_id = fields.Many2one(
        related='purchase_order_id.partner_id',
        string='Vendor',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        related='purchase_order_id.company_id',
        string='Company',
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        related='purchase_order_id.currency_id',
        string='Currency',
        store=True,
        readonly=True,
    )

    amount = fields.Monetary(
        string='Down Payment Amount',
        currency_field='currency_id',
        required=True,
    )

    payment_amount = fields.Monetary(
        string='Paid Amount',
        currency_field='currency_id',
        readonly=True,
        copy=False,
        default=0.0,
    )

    remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='currency_id',
        compute='_compute_remaining_amount',
        store=True,
    )

    payment_date = fields.Date(
        string='Payment Date',
        readonly=True,
        copy=False,
    )

    payment_move_id = fields.Many2one(
        'account.move',
        string='Payment Journal Entry',
        readonly=True,
        copy=False,
    )

    payment_journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        readonly=True,
        copy=False,
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    notes = fields.Text(
        string='Notes',
    )

    @api.depends('amount', 'payment_amount')
    def _compute_remaining_amount(self):
        for record in self:
            record.remaining_amount = max(
                record.amount - record.payment_amount,
                0.0,
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'purchase.down.payment'
                ) or _('New')

        records = super().create(vals_list)

        for record in records:
            if (
                record.proforma_id.purchase_order_id
                != record.purchase_order_id
            ):
                raise ValidationError(
                    _(
                        'The Supplier Proforma must belong to '
                        'the selected Purchase Order.'
                    )
                )

        return records

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(
                    _('Only draft down payments can be confirmed.')
                )

            if record.amount <= 0:
                raise ValidationError(
                    _('Down payment amount must be greater than zero.')
                )

            if not record.proforma_id:
                raise ValidationError(
                    _('Supplier Proforma is required.')
                )

            if record.proforma_id.state != 'verified':
                raise ValidationError(
                    _(
                        'The Supplier Proforma must be verified '
                        'before the down payment can be confirmed.'
                    )
                )

            if record.amount > record.proforma_id.down_payment_amount:
                raise ValidationError(
                    _(
                        'Down payment cannot exceed the amount '
                        'requested in the Supplier Proforma.'
                    )
                )

            record.state = 'confirmed'

    def action_approve(self):
        for record in self:
            if record.state != 'confirmed':
                raise UserError(
                    _('Only confirmed down payments can be approved.')
                )

            if record.amount <= 0:
                raise ValidationError(
                    _('Down payment amount must be greater than zero.')
                )

            record.state = 'approved'

    def action_cancel(self):
        for record in self:
            if record.state == 'paid':
                raise UserError(
                    _(
                        'A paid down payment cannot be cancelled. '
                        'Use a refund process instead.'
                    )
                )

            if record.payment_move_id:
                raise UserError(
                    _(
                        'This down payment already has a payment journal entry '
                        'and cannot be cancelled.'
                    )
                )

            if record.state == 'cancelled':
                continue

            record.state = 'cancelled'

    def action_register_payment(self):
        self.ensure_one()

        if self.state != 'approved':
            raise UserError(
                _('Only approved down payments can be paid.')
            )

        if self.payment_move_id:
            raise UserError(
                _('This down payment already has a payment journal entry.')
            )

        if self.remaining_amount <= 0:
            raise UserError(
                _('There is no remaining amount to pay.')
            )

        if not self.company_id.purchase_down_payment_account_id:
            raise UserError(
                _(
                    'Purchase Down Payment Account is not configured '
                    'for company %s.'
                )
                % self.company_id.display_name
            )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Down Payment'),
            'res_model': 'purchase.down.payment.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_down_payment_id': self.id,
                'default_amount': self.remaining_amount,
                'default_payment_date': fields.Date.context_today(self),
                'default_company_id': self.company_id.id,
            },
        }

    def action_view_payment_move(self):
        self.ensure_one()

        if not self.payment_move_id:
            raise UserError(
                _('No payment journal entry exists for this down payment.')
            )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.payment_move_id.id,
        }