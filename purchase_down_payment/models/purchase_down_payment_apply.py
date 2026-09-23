from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseDownPaymentApplyWizard(models.TransientModel):
    _name = 'purchase.down.payment.apply.wizard'
    _description = 'Apply Purchase Down Payment'

    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        required=True,
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        readonly=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        readonly=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
    )

    bill_amount = fields.Monetary(
        string='Bill Amount',
        currency_field='currency_id',
        compute='_compute_amounts',
    )

    already_applied = fields.Monetary(
        string='Already Applied DP',
        currency_field='currency_id',
        compute='_compute_amounts',
    )

    remaining_bill_amount = fields.Monetary(
        string='Remaining Bill',
        currency_field='currency_id',
        compute='_compute_amounts',
    )

    line_ids = fields.One2many(
        'purchase.down.payment.apply.wizard.line',
        'wizard_id',
        string='Down Payments',
    )

    @api.depends(
        'vendor_bill_id',
        'vendor_bill_id.amount_total',
        'vendor_bill_id.purchase_down_payment_total',
    )
    def _compute_amounts(self):
        for wizard in self:
            bill = wizard.vendor_bill_id

            if not bill:
                wizard.bill_amount = 0.0
                wizard.already_applied = 0.0
                wizard.remaining_bill_amount = 0.0
                continue

            wizard.bill_amount = bill.amount_total
            wizard.already_applied = bill.purchase_down_payment_total
            wizard.remaining_bill_amount = max(
                bill.amount_total - bill.purchase_down_payment_total,
                0.0,
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        bill_id = res.get('vendor_bill_id')

        if not bill_id:
            return res

        bill = self.env['account.move'].browse(bill_id)

        if not bill.exists():
            return res

        if bill.move_type != 'in_invoice':
            return res

        domain = [
            ('partner_id', '=', bill.partner_id.id),
            ('company_id', '=', bill.company_id.id),
            ('currency_id', '=', bill.currency_id.id),
            ('state', 'in', ['paid', 'partially_applied']),
        ]

        dps = self.env['purchase.down.payment'].search(
            domain,
            order='id asc',
        )

        lines = []

        for dp in dps:
            if dp.remaining_amount <= 0:
                continue

            lines.append(
                (
                    0,
                    0,
                    {
                        'down_payment_id': dp.id,
                        'available_amount': dp.remaining_amount,
                        'apply_amount': 0.0,
                    },
                )
            )

        res['line_ids'] = lines

        return res

    def action_apply(self):
        self.ensure_one()

        bill = self.vendor_bill_id

        if not bill:
            raise UserError(
                _('Vendor Bill is required.')
            )

        if bill.state != 'posted':
            raise UserError(
                _('The Vendor Bill must be posted.')
            )

        if bill.move_type != 'in_invoice':
            raise UserError(
                _('Only Vendor Bills can receive Down Payment applications.')
            )

        selected_lines = self.line_ids.filtered(
            lambda line: line.apply_amount > 0
        )

        if not selected_lines:
            raise UserError(
                _('Please enter at least one Down Payment amount.')
            )

        total_apply = sum(
            selected_lines.mapped('apply_amount')
        )

        if total_apply <= 0:
            raise UserError(
                _('Applied amount must be greater than zero.')
            )

        if total_apply > self.remaining_bill_amount:
            raise ValidationError(
                _(
                    'The total Down Payment applied (%s) '
                    'cannot exceed the remaining Vendor Bill amount (%s).'
                )
                % (
                    self.currency_id.format(total_apply),
                    self.currency_id.format(
                        self.remaining_bill_amount
                    ),
                )
            )

        for line in selected_lines:
            if line.apply_amount > line.available_amount:
                raise ValidationError(
                    _(
                        'Applied amount for %s exceeds '
                        'its available amount.'
                    )
                    % line.down_payment_id.name
                )

        # Validate configured account
        account = bill.company_id.purchase_down_payment_account_id

        if not account:
            raise UserError(
                _(
                    'Purchase Down Payment Account is not configured '
                    'for company %s.'
                )
                % bill.company_id.display_name
            )

        application_records = self.env[
            'purchase.down.payment.application'
        ]

        for line in selected_lines:
            dp = line.down_payment_id
            amount = line.apply_amount

            # -------------------------------------------------
            # Create Application Journal Entry
            # -------------------------------------------------

            move = self._create_application_move(
                bill=bill,
                dp=dp,
                amount=amount,
                account=account,
            )

            # -------------------------------------------------
            # Create Application History
            # -------------------------------------------------

            application = application_records.create({
                'down_payment_id': dp.id,
                'vendor_bill_id': bill.id,
                'amount': amount,
                'date': fields.Date.context_today(self),
                'application_move_id': move.id,
            })

            # -------------------------------------------------
            # Reconcile AP
            # -------------------------------------------------

            self._reconcile_vendor_bill(
                bill=bill,
                application_move=move,
            )

            # Make sure application exists
            application.state = 'posted'

            dp._update_application_state()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
        }

    def _create_application_move(
        self,
        bill,
        dp,
        amount,
        account,
    ):
        company = bill.company_id
        currency = bill.currency_id
        date = fields.Date.context_today(self)

        journal = self.env['account.journal'].search(
            [
                ('company_id', '=', company.id),
                ('type', '=', 'general'),
            ],
            limit=1,
        )

        if not journal:
            raise UserError(
                _(
                    'No Miscellaneous journal was found '
                    'for company %s.'
                )
                % company.display_name
            )

        # -----------------------------------------------------
        # Vendor payable account
        # -----------------------------------------------------

        payable_lines = bill.line_ids.filtered(
            lambda line:
                line.account_id.account_type == 'liability_payable'
                and not line.reconciled
        )

        if not payable_lines:
            raise UserError(
                _(
                    'No unreconciled Accounts Payable line '
                    'was found on Vendor Bill %s.'
                )
                % bill.name
            )

        payable_account = payable_lines[0].account_id

        # -----------------------------------------------------
        # Currency conversion
        # -----------------------------------------------------

        company_currency = company.currency_id

        if currency == company_currency:
            company_amount = amount
        else:
            company_amount = currency._convert(
                amount,
                company_currency,
                company,
                date,
            )

        move_vals = {
            'move_type': 'entry',
            'date': date,
            'journal_id': journal.id,
            'ref': _(
                'Apply Down Payment %s to %s'
            ) % (
                dp.name,
                bill.name,
            ),
            'company_id': company.id,
            'currency_id': currency.id,
        }

        move = self.env['account.move'].create(move_vals)

        # -----------------------------------------------------
        # Debit Accounts Payable
        # Credit Purchase Down Payment Asset
        # -----------------------------------------------------

        line_vals = [
            {
                'move_id': move.id,
                'name': _(
                    'Apply Down Payment %s'
                ) % dp.name,
                'partner_id': bill.partner_id.id,
                'account_id': payable_account.id,
                'currency_id': currency.id,
                'amount_currency': amount,
                'debit': company_amount,
                'credit': 0.0,
            },
            {
                'move_id': move.id,
                'name': _(
                    'Apply Down Payment %s'
                ) % dp.name,
                'partner_id': bill.partner_id.id,
                'account_id': account.id,
                'currency_id': currency.id,
                'amount_currency': -amount,
                'debit': 0.0,
                'credit': company_amount,
            },
        ]

        self.env['account.move.line'].create(line_vals)

        move.action_post()

        return move

    def _reconcile_vendor_bill(
        self,
        bill,
        application_move,
    ):
        bill_payable_lines = bill.line_ids.filtered(
            lambda line:
                line.account_id.account_type == 'liability_payable'
                and not line.reconciled
        )

        application_payable_lines = application_move.line_ids.filtered(
            lambda line:
                line.account_id.account_type == 'liability_payable'
                and not line.reconciled
        )

        if not bill_payable_lines:
            raise UserError(
                _(
                    'No unreconciled payable line was found '
                    'on Vendor Bill %s.'
                )
                % bill.name
            )

        if not application_payable_lines:
            raise UserError(
                _(
                    'No payable line was found '
                    'on the Down Payment application journal entry.'
                )
            )

        payable_lines = (
            bill_payable_lines
            | application_payable_lines
        )

        payable_lines.reconcile()


class PurchaseDownPaymentApplyWizardLine(models.TransientModel):
    _name = 'purchase.down.payment.apply.wizard.line'
    _description = 'Purchase Down Payment Apply Wizard Line'

    wizard_id = fields.Many2one(
        'purchase.down.payment.apply.wizard',
        required=True,
        ondelete='cascade',
    )

    down_payment_id = fields.Many2one(
        'purchase.down.payment',
        string='Down Payment',
        required=True,
        readonly=True,
    )

    available_amount = fields.Monetary(
        string='Available',
        currency_field='currency_id',
        readonly=True,
    )

    apply_amount = fields.Monetary(
        string='Apply Amount',
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        related='wizard_id.currency_id',
        readonly=True,
    )

    @api.constrains('apply_amount')
    def _check_apply_amount(self):
        for line in self:
            if line.apply_amount < 0:
                raise ValidationError(
                    _('Apply amount cannot be negative.')
                )

            if line.apply_amount > line.available_amount:
                raise ValidationError(
                    _(
                        'Apply amount cannot exceed '
                        'the available Down Payment amount.'
                    )
                )