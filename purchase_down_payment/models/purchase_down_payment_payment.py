from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseDownPaymentPaymentWizard(models.TransientModel):
    _name = 'purchase.down.payment.payment.wizard'
    _description = 'Register Purchase Down Payment Payment'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """Override to provide the view if not defined in XML"""
        res = super().fields_view_get(view_id, view_type, context, toolbar, submenu)
        
        if view_type == 'form':
            # Check if the view is properly defined
            if not res.get('arch') or 'down_payment_id' not in str(res.get('arch', '')):
                # Provide a default view structure
                view_arch = '''
                    <form string="Register Down Payment">
                        <group>
                            <group>
                                <field name="down_payment_id"/>
                                <field name="partner_id"/>
                                <field name="company_id"/>
                            </group>
                            <group>
                                <field name="currency_id"/>
                                <field name="amount"/>
                                <field name="payment_date"/>
                            </group>
                        </group>
                        <group string="Payment">
                            <field name="journal_id"/>
                            <field name="memo"/>
                        </group>
                        <footer>
                            <button name="action_create_payment" type="object" string="Register Payment" class="btn-primary"/>
                            <button string="Cancel" special="cancel" class="btn-secondary"/>
                        </footer>
                    </form>
                '''
                res['arch'] = view_arch
                res['fields'] = {
                    'down_payment_id': {'type': 'many2one', 'string': 'Down Payment'},
                    'partner_id': {'type': 'many2one', 'string': 'Vendor'},
                    'company_id': {'type': 'many2one', 'string': 'Company'},
                    'currency_id': {'type': 'many2one', 'string': 'Currency'},
                    'amount': {'type': 'float', 'string': 'Amount'},
                    'payment_date': {'type': 'date', 'string': 'Payment Date'},
                    'journal_id': {'type': 'many2one', 'string': 'Journal'},
                    'memo': {'type': 'char', 'string': 'Memo'},
                }
        
        return res

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

        move_vals = {
            'move_type': 'entry',
            'date': self.payment_date,
            'journal_id': self.journal_id.id,
            'company_id': company.id,
            'currency_id': currency.id if currency != company.currency_id else False,
            'ref': _('Down Payment: %s') % dp.name,
            'line_ids': [
                (0, 0, {
                    'account_id': account.id,
                    'name': dp.name,
                    'debit': 0.0,
                    'credit': self.amount,
                    'partner_id': dp.partner_id.id,
                    'currency_id': currency.id if currency != company.currency_id else False,
                    'amount_currency': -self.amount if currency != company.currency_id else False,
                }),
                (0, 0, {
                    'account_id': bank_account.id,
                    'name': dp.name,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': dp.partner_id.id,
                    'currency_id': currency.id if currency != company.currency_id else False,
                    'amount_currency': self.amount if currency != company.currency_id else False,
                }),
            ],
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()

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