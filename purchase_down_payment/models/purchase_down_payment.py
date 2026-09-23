from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseDownPayment(models.Model):
    _name = 'purchase.down.payment'
    _inherit = ['mail.thread']
    _description = 'Purchase Down Payment'
    _order = 'id desc'

    # =========================================================
    # BASIC INFORMATION
    # =========================================================

    name = fields.Char(
        string='Down Payment Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
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

    # =========================================================
    # AMOUNT
    # =========================================================

    amount = fields.Monetary(
        string='Down Payment Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )

    payment_amount = fields.Monetary(
        string='Paid Amount',
        currency_field='currency_id',
        readonly=True,
        copy=False,
        default=0.0,
    )

    applied_amount = fields.Monetary(
        string='Applied Amount',
        currency_field='currency_id',
        compute='_compute_applied_amount',
        store=True,
        readonly=True,
    )

    remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='currency_id',
        compute='_compute_remaining_amount',
        store=True,
        readonly=True,
    )

    # =========================================================
    # PAYMENT
    # =========================================================

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

    # =========================================================
    # APPLICATION
    # =========================================================

    application_ids = fields.One2many(
        'purchase.down.payment.application',
        'down_payment_id',
        string='Applications',
        readonly=True,
        copy=False,
    )

    application_count = fields.Integer(
        string='Application Count',
        compute='_compute_application_count',
    )

    # =========================================================
    # STATUS
    # =========================================================

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
            ('partially_applied', 'Partially Applied'),
            ('fully_applied', 'Fully Applied'),
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

    # =========================================================
    # COMPUTE
    # =========================================================

    @api.depends('application_ids.amount')
    def _compute_applied_amount(self):
        for record in self:
            record.applied_amount = sum(
                record.application_ids.mapped('amount')
            )

    @api.depends('amount', 'payment_amount', 'applied_amount')
    def _compute_remaining_amount(self):
        for record in self:
            # Remaining amount means the amount that can still
            # be applied to Vendor Bills.
            #
            # Before payment:
            #   remaining = 0
            #
            # After payment:
            #   remaining = paid - applied
            #
            # It is capped at the original DP amount.
            available_amount = (
                record.payment_amount - record.applied_amount
            )

            record.remaining_amount = max(
                min(available_amount, record.amount),
                0.0,
            )

    @api.depends('application_ids')
    def _compute_application_count(self):
        for record in self:
            record.application_count = len(record.application_ids)

    # =========================================================
    # CREATE
    # =========================================================

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

    # =========================================================
    # CONFIRM
    # =========================================================

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

            if record.proforma_id.state not in ('verified', 'dp_requested'):
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

    # =========================================================
    # APPROVE
    # =========================================================

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

    # =========================================================
    # CANCEL
    # =========================================================

    def action_cancel(self):
        for record in self:
            if record.state in (
                'paid',
                'partially_applied',
                'fully_applied',
            ):
                raise UserError(
                    _(
                        'This down payment has already been paid '
                        'or applied. Use a refund/reversal process instead.'
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

    # =========================================================
    # REGISTER PAYMENT
    # =========================================================

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

        if self.remaining_amount > 0:
            raise UserError(
                _(
                    'This down payment already has an available '
                    'amount for application.'
                )
            )

        if self.amount <= 0:
            raise UserError(
                _('There is no amount to pay.')
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
                'default_amount': self.amount - self.payment_amount,
                'default_payment_date': fields.Date.context_today(self),
                'default_company_id': self.company_id.id,
            },
        }

    # =========================================================
    # APPLY DP
    # =========================================================

    def action_apply_to_bill(self):
        self.ensure_one()

        if self.state not in (
            'paid',
            'partially_applied',
        ):
            raise UserError(
                _(
                    'Only paid down payments can be applied '
                    'to Vendor Bills.'
                )
            )

        if self.remaining_amount <= 0:
            raise UserError(
                _('There is no remaining amount available for application.')
            )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Apply Down Payment'),
            'res_model': 'purchase.down.payment.apply.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_down_payment_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_currency_id': self.currency_id.id,
                'default_company_id': self.company_id.id,
            },
        }

    # =========================================================
    # VIEW PAYMENT
    # =========================================================

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

    # =========================================================
    # VIEW APPLICATIONS
    # =========================================================

    def action_view_applications(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Down Payment Applications'),
            'res_model': 'purchase.down.payment.application',
            'view_mode': 'list,form',
            'domain': [
                ('down_payment_id', '=', self.id),
            ],
            'context': {
                'default_down_payment_id': self.id,
            },
        }

    # =========================================================
    # STATE UPDATE AFTER APPLICATION
    # =========================================================

    def _update_application_state(self):
        for record in self:
            if record.payment_amount <= 0:
                continue

            if record.applied_amount >= record.payment_amount:
                record.state = 'fully_applied'
            elif record.applied_amount > 0:
                record.state = 'partially_applied'
            else:
                record.state = 'paid'