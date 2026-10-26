import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

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
    # ACCOUNTING
    # =========================================================

    accounting_move_id = fields.Many2one(
        'account.move',
        string='Down Payment Journal Entry',
        readonly=True,
        copy=False,
        ondelete='restrict',
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
    # DEFAULT / ONCHANGE
    # =========================================================

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        purchase_order_id = (
            res.get('purchase_order_id')
            or self.env.context.get('default_purchase_order_id')
        )
        if (
            not purchase_order_id
            and self.env.context.get('active_model') == 'purchase.order'
        ):
            purchase_order_id = self.env.context.get('active_id')
        if purchase_order_id and 'purchase_order_id' in fields_list:
            res['purchase_order_id'] = purchase_order_id
        return res

    @api.onchange('proforma_id')
    def _onchange_proforma_id(self):
        if not self.proforma_id:
            return
        self.purchase_order_id = self.proforma_id.purchase_order_id
        if not self.amount:
            self.amount = self.proforma_id.down_payment_amount

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        if (
            self.proforma_id
            and self.purchase_order_id
            and self.proforma_id.purchase_order_id != self.purchase_order_id
        ):
            self.proforma_id = False

    def _vals_with_purchase_order_from_proforma(self, vals):
        """Keep the Purchase Order aligned with the selected proforma.

        Nested Odoo 18 URLs often omit default_purchase_order_id and may
        inject the parent PO on save, which can disagree with the proforma.
        """
        vals = dict(vals)
        if vals.get('proforma_id'):
            proforma = self.env['purchase.proforma'].browse(vals['proforma_id'])
            if proforma.purchase_order_id:
                vals['purchase_order_id'] = proforma.purchase_order_id.id
        elif not vals.get('purchase_order_id'):
            context_po = self.env.context.get('default_purchase_order_id')
            if (
                not context_po
                and self.env.context.get('active_model') == 'purchase.order'
            ):
                context_po = self.env.context.get('active_id')
            if context_po:
                vals['purchase_order_id'] = context_po
        return vals

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
            vals.update(self._vals_with_purchase_order_from_proforma(vals))

        return super().create(vals_list)

    @api.constrains('proforma_id', 'purchase_order_id')
    def _check_proforma_purchase_order(self):
        for record in self:
            if (
                record.proforma_id
                and record.purchase_order_id
                and record.proforma_id.purchase_order_id
                != record.purchase_order_id
            ):
                raise ValidationError(
                    _(
                        'The Supplier Proforma must belong to '
                        'the selected Purchase Order.'
                    )
                )

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

            # Create the accounting entry once, when the DP is confirmed.
            # Dr Purchase Advances / Cr Accounts Payable.
            record._create_down_payment_journal()
            record.state = 'confirmed'

    # =========================================================
    # ACCOUNTING JOURNAL
    # =========================================================

    def _create_down_payment_journal(self):
        """Create and post the accounting entry for this down payment.

        Debit: Purchase Down Payment Account (Uang Muka Pembelian)
        Credit: Proforma Accounts Payable (Utang Usaha)
        """
        self.ensure_one()

        if self.accounting_move_id:
            if self.accounting_move_id.state == 'posted':
                return self.accounting_move_id
            raise UserError(_(
                'A journal entry already exists for this down payment. '
                'Please review it before confirming again.'
            ))

        company = self.company_id
        currency = self.currency_id
        company_currency = company.currency_id
        date = fields.Date.context_today(self)

        # Use the configured Proforma Journal unless a dedicated DP journal
        # configuration is introduced in the company settings.
        journal = company.purchase_proforma_journal_id
        debit_account = company.purchase_down_payment_account_id
        credit_account = company.purchase_proforma_payable_account_id

        if not journal:
            raise UserError(_(
                'Please configure the Proforma Journal in Purchase Down Payment '
                'settings for %s.'
            ) % company.display_name)

        if journal.company_id != company or journal.type != 'general':
            raise ValidationError(_(
                'The configured journal must be a Miscellaneous journal '
                'belonging to %s.'
            ) % company.display_name)

        if not debit_account:
            raise UserError(_(
                'Please configure the Purchase Down Payment Account '
                'in settings for %s.'
            ) % company.display_name)

        if not credit_account:
            raise UserError(_(
                'Please configure the Proforma Accounts Payable account '
                'in settings for %s.'
            ) % company.display_name)

        if company not in debit_account.company_ids:
            raise ValidationError(_(
                'The Purchase Down Payment Account does not belong '
                'to the selected company.'
            ))

        if company not in credit_account.company_ids:
            raise ValidationError(_(
                'The Accounts Payable account does not belong '
                'to the selected company.'
            ))

        if credit_account.account_type != 'liability_payable':
            raise ValidationError(_(
                'The configured Accounts Payable account must have '
                'the account type Payable.'
            ))

        if self.amount <= 0:
            raise ValidationError(_('Down payment amount must be greater than zero.'))

        ref = 'Down Payment: %s' % self.name
        existing_move = self.env['account.move'].search([
            ('company_id', '=', company.id),
            ('ref', '=', ref),
            ('state', '=', 'posted'),
        ], limit=1)
        if existing_move:
            self.accounting_move_id = existing_move
            return existing_move

        company_amount = currency._convert(
            self.amount, company_currency, company, date
        )
        company_amount = company_currency.round(company_amount)
        if company_amount <= 0:
            raise ValidationError(_(
                'The down payment must produce a positive amount in company currency.'
            ))

        line_currency_id = currency.id
        debit_amount_currency = self.amount
        credit_amount_currency = -self.amount

        move = self.env['account.move'].with_company(company).create({
            'move_type': 'entry',
            'date': date,
            'journal_id': journal.id,
            'company_id': company.id,
            'ref': ref,
            'partner_id': self.partner_id.id,
            'line_ids': [
                (0, 0, {
                    'name': _('Down Payment - %s') % self.name,
                    'account_id': debit_account.id,
                    'partner_id': self.partner_id.id,
                    'currency_id': line_currency_id,
                    'debit': company_amount,
                    'credit': 0.0,
                    'amount_currency': debit_amount_currency,
                }),
                (0, 0, {
                    'name': _('Down Payment - %s') % self.name,
                    'account_id': credit_account.id,
                    'partner_id': self.partner_id.id,
                    'currency_id': line_currency_id,
                    'debit': 0.0,
                    'credit': company_amount,
                    'amount_currency': credit_amount_currency,
                }),
            ],
        })
        move.action_post()
        self.accounting_move_id = move

        _logger.info(
            '[PURCHASE DOWN PAYMENT] JOURNAL POSTED | DP=%s | Move=%s | '
            'Journal=%s | Debit=%s | Credit=%s | Amount=%s | Company Amount=%s',
            self.name, move.name, journal.display_name,
            debit_account.display_name, credit_account.display_name,
            self.amount, company_amount,
        )
        return move

    def action_view_accounting_move(self):
        self.ensure_one()
        if not self.accounting_move_id:
            raise UserError(_('No accounting journal entry exists for this down payment.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Down Payment Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.accounting_move_id.id,
        }

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

            if record.accounting_move_id and record.accounting_move_id.state == 'posted':
                raise UserError(
                    _(
                        'This down payment already has a posted accounting journal entry. '
                        'Reverse the journal entry before cancelling the down payment.'
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

        if self.amount <= 0:
            raise UserError(
                _('There is no amount to pay.')
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