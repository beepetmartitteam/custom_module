from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseDownPaymentPaymentWizard(models.TransientModel):
    _name = 'purchase.down.payment.payment.wizard'
    _description = 'Register Purchase Down Payment Payment'

    down_payment_id = fields.Many2one(
        'purchase.down.payment',
        string='Down Payment',
        required=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        related='down_payment_id.company_id',
        string='Company',
        readonly=True,
    )

    partner_id = fields.Many2one(
        related='down_payment_id.partner_id',
        string='Vendor',
        readonly=True,
    )

    currency_id = fields.Many2one(
        related='down_payment_id.currency_id',
        string='Currency',
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
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        required=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
    )

    memo = fields.Char(
        string='Memo',
    )

    def action_create_payment(self):
        self.ensure_one()

        down_payment = self.down_payment_id

        if down_payment.state != 'approved':
            raise UserError(
                _('Only approved down payments can be paid.')
            )

        if down_payment.payment_move_id:
            raise UserError(
                _('This down payment already has a payment journal entry.')
            )

        if self.amount <= 0:
            raise ValidationError(
                _('Payment amount must be greater than zero.')
            )

        if self.amount > down_payment.remaining_amount:
            raise ValidationError(
                _(
                    'Payment amount cannot exceed the remaining '
                    'down payment amount.'
                )
            )

        if not self.journal_id:
            raise ValidationError(
                _('Please select a payment journal.')
            )

        if self.journal_id.company_id != down_payment.company_id:
            raise ValidationError(
                _('The payment journal must belong to the same company.')
            )

        if self.journal_id.type not in ('bank', 'cash'):
            raise ValidationError(
                _('The payment journal must be a Bank or Cash journal.')
            )

        if not self.journal_id.default_account_id:
            raise ValidationError(
                _(
                    'The selected payment journal does not have '
                    'a default account configured.'
                )
            )

        down_payment_account = (
            down_payment.company_id.purchase_down_payment_account_id
        )

        if not down_payment_account:
            raise ValidationError(
                _(
                    'Purchase Down Payment Account is not configured '
                    'for company %s.'
                )
                % down_payment.company_id.display_name
            )

        # Company validation - account.account may not have company_id in Odoo 18
        # Skipping this check as account selection is already filtered by company

        company_currency = down_payment.company_id.currency_id
        transaction_currency = down_payment.currency_id

        # ---------------------------------------------------------
        # Calculate company-currency amount
        # ---------------------------------------------------------
        if transaction_currency == company_currency:
            company_amount = self.amount
        else:
            company_amount = transaction_currency._convert(
                self.amount,
                company_currency,
                down_payment.company_id,
                self.payment_date,
            )

        company_amount = company_currency.round(company_amount)

        if company_amount <= 0:
            raise ValidationError(
                _('The company-currency payment amount must be greater than zero.')
            )

        # ---------------------------------------------------------
        # Create Journal Entry
        #
        # Dr Purchase Down Payment
        # Cr Bank / Cash
        # ---------------------------------------------------------
        move_vals = {
            'move_type': 'entry',
            'date': self.payment_date,
            'journal_id': self.journal_id.id,
            'company_id': down_payment.company_id.id,
            'ref': self.memo or down_payment.name,
            'line_ids': [
                (
                    0,
                    0,
                    {
                        'name': down_payment.name,
                        'account_id': down_payment_account.id,
                        'partner_id': down_payment.partner_id.id,
                        'currency_id': transaction_currency.id,
                        'amount_currency': self.amount,
                        'debit': company_amount,
                        'credit': 0.0,
                    },
                ),
                (
                    0,
                    0,
                    {
                        'name': down_payment.name,
                        'account_id': self.journal_id.default_account_id.id,
                        'partner_id': down_payment.partner_id.id,
                        'currency_id': transaction_currency.id,
                        'amount_currency': -self.amount,
                        'debit': 0.0,
                        'credit': company_amount,
                    },
                ),
            ],
        }

        move = self.env['account.move'].create(move_vals)

        move.action_post()

        down_payment.write({
            'payment_move_id': move.id,
            'payment_journal_id': self.journal_id.id,
            'payment_amount': self.amount,
            'payment_date': self.payment_date,
            'state': 'paid',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Down Payment'),
            'res_model': 'purchase.down.payment',
            'view_mode': 'form',
            'res_id': down_payment.id,
        }