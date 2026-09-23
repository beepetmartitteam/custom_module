from odoo import api, fields, models, _
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

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        down_payment_id = res.get('down_payment_id')

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

    def action_create_payment(self):
        self.ensure_one()

        dp = self.down_payment_id

        if not dp:
            raise UserError(
                _('Down Payment is required.')
            )

        if dp.state != 'approved':
            raise UserError(
                _(
                    'Only approved Down Payments '
                    'can be paid.'
                )
            )

        if dp.payment_move_id:
            raise UserError(
                _(
                    'This Down Payment already has '
                    'a payment journal entry.'
                )
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

        if self.journal_id.company_id != dp.company_id:
            raise UserError(
                _(
                    'Payment Journal must belong '
                    'to the same company as the Down Payment.'
                )
            )

        account = dp.company_id.purchase_down_payment_account_id

        if not account:
            raise UserError(
                _(
                    'Purchase Down Payment Account is not configured '
                    'for company %s.'
                )
                % dp.company_id.display_name
            )

        if account.company_ids and dp.company_id not in account.company_ids:
            raise UserError(
                _(
                    'Purchase Down Payment Account does not belong '
                    'to company %s.'
                )
                % dp.company_id.display_name
            )

        bank_account = (
            self.journal_id.default_account_id
        )

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

        return {
            'type': 'ir.actions.act_window',
            'name': _('Down Payment'),
            'res_model': 'purchase.down.payment',
            'view_mode': 'form',
            'res_id': dp.id,
        }

    def _create_payment_move(
        self,
        dp,
        account,
        bank_account,
    ):
        company = dp.company_id
        currency = dp.currency_id

        move_vals = {
            'move_type': 'entry',
            'date': self.payment_date,
            'journal_id': self.journal_id.id,
            'company_id': company.id,
            'ref': self.memo or _(
                'Down Payment %s'
            ) % dp.name,
        }

        move = self.env['account.move'].create(
            move_vals
        )

        company_currency = company.currency_id

        if currency == company_currency:
            company_amount = self.amount
        else:
            company_amount = currency._convert(
                self.amount,
                company_currency,
                company,
                self.payment_date,
            )

        line_vals = [
            {
                'move_id': move.id,
                'name': _(
                    'Purchase Down Payment %s'
                ) % dp.name,
                'partner_id': dp.partner_id.id,
                'account_id': account.id,
                'currency_id': currency.id,
                'amount_currency': self.amount,
                'debit': company_amount,
                'credit': 0.0,
            },
            {
                'move_id': move.id,
                'name': _(
                    'Purchase Down Payment %s'
                ) % dp.name,
                'partner_id': dp.partner_id.id,
                'account_id': bank_account.id,
                'currency_id': currency.id,
                'amount_currency': -self.amount,
                'debit': 0.0,
                'credit': company_amount,
            },
        ]

        self.env['account.move.line'].create(
            line_vals
        )

        move.action_post()

        return move