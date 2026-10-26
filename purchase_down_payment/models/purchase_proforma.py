import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PurchaseProforma(models.Model):
    _name = 'purchase.proforma'
    _description = 'Purchase Supplier Proforma Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # =========================================================
    # BASIC INFORMATION
    # =========================================================

    name = fields.Char(
        string='Proforma Reference',
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
    # ACCOUNTING
    # =========================================================

    proforma_move_id = fields.Many2one(
        'account.move',
        string='Proforma Journal Entry',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    proforma_move_count = fields.Integer(
        string='Journal Entry Count',
        compute='_compute_proforma_move_count',
    )

    # =========================================================
    # SUPPLIER PROFORMA
    # =========================================================

    proforma_number = fields.Char(
        string='Supplier Proforma Number',
        required=True,
        tracking=True,
    )

    proforma_date = fields.Date(
        string='Proforma Date',
        required=True,
        default=fields.Date.context_today,
    )

    due_date = fields.Date(
        string='Payment Due Date',
    )

    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        currency_field='currency_id',
    )

    tax_amount = fields.Monetary(
        string='Tax Amount',
        currency_field='currency_id',
    )

    amount_total = fields.Monetary(
        string='Proforma Total',
        currency_field='currency_id',
        required=True,
    )

    # =========================================================
    # DOWN PAYMENT
    # =========================================================

    down_payment_percentage = fields.Float(
        string='Down Payment %',
        digits='Product Unit of Measure',
    )

    down_payment_amount = fields.Monetary(
        string='Down Payment Amount',
        currency_field='currency_id',
    )

    # =========================================================
    # NOTES / ATTACHMENTS
    # =========================================================

    notes = fields.Text(string='Notes')

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'purchase_proforma_attachment_rel',
        'proforma_id',
        'attachment_id',
        string='Attachments',
    )

    # =========================================================
    # WORKFLOW
    # =========================================================

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('verified', 'Verified'),
            ('dp_requested', 'DP Requested'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
    )

    # =========================================================
    # DOWN PAYMENT RELATION
    # =========================================================

    down_payment_ids = fields.One2many(
        'purchase.down.payment',
        'proforma_id',
        string='Down Payments',
    )

    down_payment_count = fields.Integer(
        string='Down Payment Count',
        compute='_compute_down_payment_count',
    )

    # =========================================================
    # COMPUTE
    # =========================================================

    @api.depends('down_payment_ids')
    def _compute_down_payment_count(self):
        for record in self:
            record.down_payment_count = len(record.down_payment_ids)

    @api.depends('proforma_move_id')
    def _compute_proforma_move_count(self):
        for record in self:
            record.proforma_move_count = (
                1 if record.proforma_move_id else 0
            )

    # =========================================================
    # CREATE
    # =========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(
                        'purchase.proforma'
                    )
                    or _('New')
                )

        return super().create(vals_list)



    # =========================================================
    # ACCOUNTING CONFIGURATION
    # =========================================================

    def _get_proforma_accounting_configuration(self):
        self.ensure_one()

        company = self.company_id

        _logger.info(
            "[PROFORMA ACCOUNTING CONFIG] START | "
            "Proforma ID=%s | Reference=%s | Company=%s (ID=%s) | User=%s",
            self.id,
            self.name,
            company.display_name,
            company.id,
            self.env.user.login,
        )

        journal = company.purchase_proforma_journal_id
        debit_account = company.purchase_proforma_advance_account_id
        credit_account = company.purchase_proforma_payable_account_id

        _logger.info(
            "[PROFORMA ACCOUNTING CONFIG] CONFIG VALUES | "
            "Proforma=%s | Journal=%s (ID=%s, Type=%s, Company ID=%s) | "
            "Debit Account=%s (ID=%s) | "
            "Credit Account=%s (ID=%s)",
            self.name,
            journal.display_name if journal else False,
            journal.id if journal else False,
            journal.type if journal else False,
            journal.company_id.id if journal else False,
            debit_account.display_name if debit_account else False,
            debit_account.id if debit_account else False,
            credit_account.display_name if credit_account else False,
            credit_account.id if credit_account else False,
        )
    
        if not journal:
            raise UserError(_(
                'Please configure the Proforma Journal '
                'in Purchase Down Payment settings for %s.'
            ) % company.display_name)

        if journal.company_id != company or journal.type != 'general':
            raise ValidationError(_(
                'The configured Proforma Journal must be a '
                'Miscellaneous journal belonging to %s.'
            ) % company.display_name)

        if not debit_account:
            raise UserError(_(
                'Please configure the Purchase Advance Account '
                'in Purchase Down Payment settings for %s.'
            ) % company.display_name)

        if not credit_account:
            raise UserError(_(
                'Please configure the Accounts Payable account '
                'in Purchase Down Payment settings for %s.'
            ) % company.display_name)

        if company not in debit_account.company_ids:
            raise ValidationError(_(
                'The Purchase Advance Account does not belong '
                'to the selected company.'
            ))

        if company not in credit_account.company_ids:
            raise ValidationError(_(
                'The Accounts Payable account does not belong '
                'to the selected company.'
            ))

        if credit_account.account_type != 'liability_payable':
            raise ValidationError(_(
                'The configured Accounts Payable account must '
                'have the account type Payable.'
            ))

        return journal, debit_account, credit_account

    # =========================================================
    # CREATE PROFORMA JOURNAL
    # =========================================================

    def _create_proforma_journal(self):
        self.ensure_one()

        # Prevent creating the same journal twice.
        if self.proforma_move_id:
            if self.proforma_move_id.state == 'posted':
                return self.proforma_move_id

            if self.proforma_move_id.state != 'cancel':
                raise UserError(_(
                    'A journal entry already exists for this Proforma. '
                    'Please review it before proceeding.'
                ))

        # Detect an existing entry linked by reference.
        journal_ref = 'Supplier Proforma: %s' % self.name

        existing_move = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('ref', '=', journal_ref),
            ('state', '=', 'posted'),
        ], limit=1)

        if existing_move:
            self.proforma_move_id = existing_move
            return existing_move

        journal, debit_account, credit_account = (
            self._get_proforma_accounting_configuration()
        )

        if self.amount_total <= 0:
            raise ValidationError(_(
                'Proforma total must be greater than zero.'
            ))

        company = self.company_id
        company_currency = company.currency_id
        proforma_currency = self.currency_id

        # Convert the total to company currency for debit/credit.
        company_amount = proforma_currency._convert(
            self.amount_total,
            company_currency,
            company,
            self.proforma_date,
        )

        company_amount = company_currency.round(company_amount)

        if company_amount <= 0:
            raise ValidationError(_(
                'The Proforma total must produce a positive '
                'amount in company currency.'
            ))

        debit_line_vals = {
            'name': journal_ref,
            'account_id': debit_account.id,
            'partner_id': self.partner_id.id,
            'debit': company_amount,
            'credit': 0.0,
        }

        credit_line_vals = {
            'name': journal_ref,
            'account_id': credit_account.id,
            'partner_id': self.partner_id.id,
            'debit': 0.0,
            'credit': company_amount,
        }

        # Preserve foreign-currency amounts when applicable.
        if proforma_currency != company_currency:
            debit_line_vals.update({
                'currency_id': proforma_currency.id,
                'amount_currency': self.amount_total,
            })
            credit_line_vals.update({
                'currency_id': proforma_currency.id,
                'amount_currency': -self.amount_total,
            })

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'company_id': company.id,
            'journal_id': journal.id,
            'date': self.proforma_date,
            'ref': journal_ref,
            'partner_id': self.partner_id.id,
            'line_ids': [
                (0, 0, debit_line_vals),
                (0, 0, credit_line_vals),
            ],
        })

        # Post the journal before marking the Proforma verified.
        move.action_post()

        self.proforma_move_id = move.id

        return move

    # =========================================================
    # SUBMIT
    # =========================================================

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_(
                    'Only draft Proforma invoices can be submitted.'
                ))

            if not record.purchase_order_id:
                raise ValidationError(_(
                    'Purchase Order is required.'
                ))

            if not record.proforma_number:
                raise ValidationError(_(
                    'Supplier Proforma Number is required.'
                ))

            if not record.proforma_date:
                raise ValidationError(_(
                    'Proforma Date is required.'
                ))

            if record.amount_total <= 0:
                raise ValidationError(_(
                    'Proforma total must be greater than zero.'
                ))

            if record.amount_untaxed < 0 or record.tax_amount < 0:
                raise ValidationError(_(
                    'Untaxed amount and tax amount cannot be negative.'
                ))

            record.state = 'submitted'

    # =========================================================
    # VERIFY + CREATE ACCOUNTING JOURNAL
    # =========================================================

    def action_verify(self):
        for record in self:
            _logger.info(
            "[PURCHASE PROFORMA VERIFY] START | "
            "Proforma ID=%s | Reference=%s | State=%s | "
            "PO=%s | Vendor=%s | Company=%s | User=%s",
            record.id,
            record.name,
            record.state,
            record.purchase_order_id.name,
            record.partner_id.display_name,
            record.company_id.display_name,
            self.env.user.login,
        )

            try:
                # -------------------------------------------------
                # 1. VALIDATE STATE
                # -------------------------------------------------
                _logger.info(
                    "[PURCHASE PROFORMA VERIFY] STEP 1: "
                    "Validate state | Proforma=%s | State=%s",
                    record.name,
                    record.state,
                )
    
                if record.state != 'submitted':
                    raise UserError(_(
                        'Only submitted Proforma invoices can be verified.'
                    ))
    
                # -------------------------------------------------
                # 2. VALIDATE AMOUNTS
                # -------------------------------------------------
                _logger.info(
                    "[PURCHASE PROFORMA VERIFY] STEP 2: "
                    "Validate amounts | Proforma=%s | "
                    "Currency=%s | Untaxed=%s | Tax=%s | Total=%s | "
                    "DP Percentage=%s | DP Amount=%s",
                    record.name,
                    record.currency_id.name,
                    record.amount_untaxed,
                    record.tax_amount,
                    record.amount_total,
                    record.down_payment_percentage,
                    record.down_payment_amount,
                )
    
                if record.amount_total <= 0:
                    raise ValidationError(_(
                        'Proforma total must be greater than zero.'
                    ))
    
                if record.down_payment_percentage < 0:
                    raise ValidationError(_(
                        'Down payment percentage cannot be negative.'
                    ))
    
                if record.down_payment_percentage > 100:
                    raise ValidationError(_(
                        'Down payment percentage cannot exceed 100%.'
                    ))
    
                if record.down_payment_amount <= 0:
                    raise ValidationError(_(
                        'Down payment amount must be greater than zero.'
                    ))
    
                if record.down_payment_amount > record.amount_total:
                    raise ValidationError(_(
                        'Down payment cannot be greater than Proforma total.'
                    ))
    
                # -------------------------------------------------
                # 3. VERIFY DP CALCULATION
                # -------------------------------------------------
                expected_dp = record.currency_id.round(
                    record.amount_total
                    * record.down_payment_percentage
                    / 100.0
                )
    
                _logger.info(
                    "[PURCHASE PROFORMA VERIFY] STEP 3: "
                    "Check DP calculation | Proforma=%s | "
                    "Percentage=%s | Expected DP=%s | Actual DP=%s",
                    record.name,
                    record.down_payment_percentage,
                    expected_dp,
                    record.down_payment_amount,
                )
    
                if (
                    record.down_payment_percentage
                    and record.currency_id.compare_amounts(
                        expected_dp,
                        record.down_payment_amount,
                    ) != 0
                ):
                    raise ValidationError(_(
                        'Down Payment Amount does not match '
                        'the configured Down Payment percentage.'
                    ))
    

                # -------------------------------------------------
                # 4. CHECK ACCOUNTING CONFIGURATION
                # -------------------------------------------------
                # _logger.info(
                #     "[PURCHASE PROFORMA VERIFY] STEP 4: "
                #     "Check accounting configuration | Proforma=%s",
                #     record.name,
                # )

                # journal, debit_account, credit_account = (
                #     record._get_proforma_accounting_configuration()
                # )

                # _logger.info(
                #     "[PURCHASE PROFORMA VERIFY] ACCOUNTING CONFIG | "
                #     "Proforma=%s | Journal=%s (ID=%s) | "
                #     "Debit Account=%s (ID=%s) | "
                #     "Credit Account=%s (ID=%s)",
                #     record.name,
                #     journal.display_name,
                #     journal.id,
                #     debit_account.display_name,
                #     debit_account.id,
                #     credit_account.display_name,
                #     credit_account.id,
                # )

                # -------------------------------------------------
                # 5. CREATE AND POST JOURNAL
                # -------------------------------------------------
                # _logger.info(
                #     "[PURCHASE PROFORMA VERIFY] STEP 5: "
                #     "Create/post journal | Proforma=%s | "
                #     "Existing Move ID=%s",
                #     record.name,
                #     record.proforma_move_id.id or False,
                # )

                # move = record._create_proforma_journal()

                # _logger.info(
                #     "[PURCHASE PROFORMA VERIFY] JOURNAL RESULT | "
                #     "Proforma=%s | Move ID=%s | Move Name=%s | "
                #     "Journal=%s | State=%s | Date=%s | Ref=%s",
                #     record.name,
                #     move.id,
                #     move.name,
                #     move.journal_id.display_name,
                #     move.state,
                #     move.date,
                #     move.ref,
                # )

                # -------------------------------------------------
                # 6. LOG JOURNAL LINES
                # -------------------------------------------------
                # for line in move.line_ids:
                #     _logger.info(
                #         "[PURCHASE PROFORMA VERIFY] JOURNAL LINE | "
                #         "Proforma=%s | Move=%s | Line ID=%s | "
                #         "Account=%s | Partner=%s | "
                #         "Debit=%s | Credit=%s | "
                #         "Currency=%s | Amount Currency=%s",
                #         record.name,
                #         move.name,
                #         line.id,
                #         line.account_id.display_name,
                #         line.partner_id.display_name,
                #         line.debit,
                #         line.credit,
                #         line.currency_id.name,
                #         line.amount_currency,
                #     )

                #if move.state != 'posted':
                #    raise UserError(_(
                #        'The Proforma journal entry was not posted successfully.'
                #    ))
    
                # -------------------------------------------------
                # 7. UPDATE STATUS
                # -------------------------------------------------
                _logger.info(
                    "[PURCHASE PROFORMA VERIFY] STEP 7: "
                    "Update state | Proforma=%s | Old State=%s | "
                    "New State=verified",
                    record.name,
                    record.state,
                )
    
                record.state = 'verified'
    
                _logger.info(
                    "[PURCHASE PROFORMA VERIFY] SUCCESS | "
                    "Proforma ID=%s | Reference=%s | "
                    "State=%s",
                    record.id,
                    record.name,
                #    move.id,
                #    move.name,
                    record.state,
                )
    
            except Exception:
                _logger.exception(
                    "[PURCHASE PROFORMA VERIFY] FAILED | "
                    "Proforma ID=%s | Reference=%s | State=%s",
                    record.id,
                    record.name,
                    record.state,
                )
                raise

        return True

    # =========================================================
    # REQUEST DOWN PAYMENT
    # =========================================================

    def action_request_down_payment(self):
        for record in self:
            if record.state != 'verified':
                raise UserError(_(
                    'Only verified Proforma invoices can request '
                    'Down Payment.'
                ))

            #if not record.proforma_move_id or (
            #    record.proforma_move_id.state != 'posted'
            #):
            #    raise UserError(_(
            #        'A posted Proforma journal is required '
            #        'before requesting Down Payment.'
            #    ))

            if record.down_payment_amount <= 0:
                raise ValidationError(_(
                    'Down Payment amount must be greater than zero.'
                ))

            if record.down_payment_amount > record.amount_total:
                raise ValidationError(_(
                    'Down Payment cannot be greater than Proforma total.'
                ))

            active_down_payments = record.down_payment_ids.filtered(
                lambda dp: dp.state != 'cancelled'
            )

            if active_down_payments:
                raise UserError(_(
                    'A Down Payment already exists for this '
                    'Supplier Proforma.'
                ))

            self.env['purchase.down.payment'].create({
                'purchase_order_id': record.purchase_order_id.id,
                'proforma_id': record.id,
                'amount': record.down_payment_amount,
            })

            record.state = 'dp_requested'

        return True

    # =========================================================
    # CANCEL
    # =========================================================

    def action_cancel(self):
        for record in self:
            if record.state == 'cancelled':
                continue

            if record.proforma_move_id and (
                record.proforma_move_id.state == 'posted'
            ):
                raise UserError(_(
                    'This Proforma cannot be cancelled because its '
                    'accounting journal is already posted. '
                    'Reverse the journal through the accounting '
                    'workflow before cancelling the Proforma.'
                ))

            active_down_payments = record.down_payment_ids.filtered(
                lambda dp: dp.state not in ('cancelled', 'draft')
            )

            if active_down_payments:
                raise UserError(_(
                    'This Proforma cannot be cancelled because '
                    'it already has an active Down Payment.'
                ))

            record.state = 'cancelled'

        return True

    # =========================================================
    # VIEW DOWN PAYMENTS
    # =========================================================

    def action_view_down_payments(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Down Payments'),
            'res_model': 'purchase.down.payment',
            'view_mode': 'list,form',
            'domain': [
                ('proforma_id', '=', self.id),
            ],
            'context': {
                'default_purchase_order_id': self.purchase_order_id.id,
                'default_proforma_id': self.id,
            },
        }

    # =========================================================
    # VIEW PROFORMA JOURNAL
    # =========================================================

    def action_view_proforma_journal(self):
        self.ensure_one()

        if not self.proforma_move_id:
            raise UserError(_(
                'No journal entry is linked to this Proforma.'
            ))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Proforma Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.proforma_move_id.id,
            'target': 'current',
        }
