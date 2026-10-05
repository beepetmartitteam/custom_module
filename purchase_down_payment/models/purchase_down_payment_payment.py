from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging


class PurchaseDownPaymentPaymentWizard(models.TransientModel):
    _name = 'purchase.down.payment.payment.wizard'
    _description = 'Register Purchase Down Payment Payment'
    _logger = logging.getLogger(__name__)

    def action_create_payment(self):
        self.ensure_one()

        dp = self.down_payment_id
        company = dp.company_id
        currency = dp.currency_id

        self._logger.info(
            "=== ACTION CREATE PAYMENT START === "
            "wizard_id=%s, dp_id=%s, dp_name=%s, "
            "amount=%s, payment_date=%s, journal_id=%s, "
            "company_id=%s, company_currency=%s, dp_currency=%s",
            self.id,
            dp.id if dp else False,
            dp.name if dp else False,
            self.amount,
            self.payment_date,
            self.journal_id.id if self.journal_id else False,
            company.id if company else False,
            company.currency_id.id if company and company.currency_id else False,
            currency.id if currency else False,
        )

        if not dp:
            raise UserError(
                _('Down Payment is required.')
            )

        if dp.state != 'approved':
            raise UserError(
                _('Only approved Down Payments can be paid.')
            )

        if dp.payment_move_id:
            raise UserError(
                _('This Down Payment already has a payment journal entry.')
            )

        if self.amount <= 0:
            raise ValidationError(
                _('Payment amount must be greater than zero.')
            )

        remaining_to_pay = dp.amount - dp.payment_amount

        if self.amount > remaining_to_pay:
            raise ValidationError(
                _(
                    'Payment amount cannot exceed '
                    'the remaining Down Payment amount.'
                )
            )

        if not self.journal_id:
            raise UserError(
                _('Payment Journal is required.')
            )

        if self.journal_id.company_id != company:
            raise UserError(
                _(
                    'Payment Journal must belong to the same company '
                    'as the Down Payment.'
                )
            )

        account = company.purchase_down_payment_account_id

        if not account:
            raise UserError(
                _(
                    'Purchase Down Payment Account is not configured '
                    'for company %s.'
                )
                % company.display_name
            )

        if account.company_ids and company not in account.company_ids:
            raise UserError(
                _(
                    'Purchase Down Payment Account does not belong '
                    'to company %s.'
                )
                % company.display_name
            )

        bank_account = self.journal_id.default_account_id

        if not bank_account:
            raise UserError(
                _(
                    'Payment Journal %s does not have a default '
                    'account configured.'
                )
                % self.journal_id.display_name
            )

        move = self._create_payment_move(
            dp=dp,
            account=account,
            bank_account=bank_account,
        )

        dp.write({
            'payment_amount': dp.payment_amount + self.amount,
            'payment_date': self.payment_date,
            'payment_move_id': move.id,
            'payment_journal_id': self.journal_id.id,
            'state': 'paid',
        })

        self._logger.info(
            "=== ACTION CREATE PAYMENT SUCCESS === "
            "dp_id=%s, move_id=%s, move_name=%s, "
            "payment_amount=%s, state=%s",
            dp.id,
            move.id,
            move.name,
            dp.payment_amount,
            dp.state,
        )

        return {
            'type': 'ir.actions.act_window_close',
        }

    def _create_payment_move(
        self,
        dp,
        account,
        bank_account,
    ):
        company = dp.company_id
        currency = dp.currency_id

        payment_amount = self.amount

        is_foreign_currency = currency != company.currency_id

        # Convert DP currency -> company currency
        company_amount = currency._convert(
            payment_amount,
            company.currency_id,
            company,
            self.payment_date,
        )

        self._logger.info(
            "=== CREATE PAYMENT MOVE === "
            "dp_id=%s, currency=%s, payment_amount=%s, "
            "company_currency=%s, company_amount=%s, "
            "foreign=%s, journal_id=%s, account_id=%s, "
            "bank_account_id=%s",
            dp.id,
            currency.name,
            payment_amount,
            company.currency_id.name,
            company_amount,
            is_foreign_currency,
            self.journal_id.id,
            account.id,
            bank_account.id,
        )

        move_vals = {
            'move_type': 'entry',
            'date': self.payment_date,
            'journal_id': self.journal_id.id,
            'company_id': company.id,

            # WAJIB diisi
            'currency_id': currency.id,

            'ref': _('Down Payment: %s') % dp.name,

            'line_ids': [
                (0, 0, {
                    'account_id': account.id,
                    'name': dp.name,

                    # Company currency
                    'debit': 0.0,
                    'credit': company_amount,

                    'partner_id': dp.partner_id.id,

                    # Transaction currency
                    'currency_id': currency.id,
                    'amount_currency': -payment_amount,
                }),

                (0, 0, {
                    'account_id': bank_account.id,
                    'name': dp.name,

                    # Company currency
                    'debit': company_amount,
                    'credit': 0.0,

                    'partner_id': dp.partner_id.id,

                    # Transaction currency
                    'currency_id': currency.id,
                    'amount_currency': payment_amount,
                }),
            ],
        }

        self._logger.info(
            "PAYMENT MOVE VALS: %s",
            move_vals,
        )

        move = self.env['account.move'].create(move_vals)

        self._logger.info(
            "PAYMENT MOVE CREATED: move_id=%s, name=%s, "
            "currency_id=%s, state=%s",
            move.id,
            move.name,
            move.currency_id.id,
            move.state,
        )

        move.action_post()

        self._logger.info(
            "PAYMENT MOVE POSTED: move_id=%s, name=%s, state=%s",
            move.id,
            move.name,
            move.state,
        )

        return move

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        down_payment_id = self.env.context.get('default_down_payment_id')

        if not down_payment_id:
            return res

        dp = self.env['purchase.down.payment'].browse(
            down_payment_id
        )

        if not dp.exists():
            return res

        res['amount'] = dp.amount - dp.payment_amount
        res['payment_date'] = fields.Date.context_today(self)

        journal = self.env['account.journal'].search(
            [
                ('company_id', '=', dp.company_id.id),
                ('type', 'in', ['bank', 'cash']),
            ],
            order='sequence, id',
            limit=1,
        )

        if journal:
            res['journal_id'] = journal.id

        return res

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            return {
                'domain': {
                    'journal_id': [
                        ('company_id', '=', self.company_id.id),
                        ('type', 'in', ['bank', 'cash']),
                    ],
                }
            }

    down_payment_id = fields.Many2one(
        'purchase.down.payment',
        string='Down Payment',
        required=True,
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        related='down_payment_id.partner_id',
        readonly=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='down_payment_id.company_id',
        readonly=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='down_payment_id.currency_id',
        readonly=True,
    )

    amount = fields.Monetary(
        string='Payment Amount',
        currency_field='currency_id',
        required=True,
    )

    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.context_today,
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        required=True,
        domain="[('company_id', '=', company_id), ('type', 'in', ['bank', 'cash'])]",
    )

    memo = fields.Char(
        string='Memo',
    )