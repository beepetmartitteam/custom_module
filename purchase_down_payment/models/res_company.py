from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Purchase Proforma Accounting Configuration
    purchase_proforma_journal_id = fields.Many2one(
        'account.journal',
        string='Proforma Journal',
        domain="[('company_id', '=', id), ('type', '=', 'general')]",
        check_company=True,
    )

    purchase_proforma_advance_account_id = fields.Many2one(
        'account.account',
        string='Proforma Purchase Advance Account',
        domain="[('company_ids', 'in', [id]), ('deprecated', '=', False)]",
        check_company=True,
    )

    purchase_proforma_payable_account_id = fields.Many2one(
        'account.account',
        string='Proforma Accounts Payable',
        domain="[('company_ids', 'in', [id]), ('account_type', '=', 'liability_payable'), ('deprecated', '=', False)]",
        check_company=True,
    )

    # Purchase Down Payment Accounting Configuration
    purchase_down_payment_account_id = fields.Many2one(
        'account.account',
        string='Purchase Down Payment Account',
        domain="[('company_ids', 'in', [id]), ('deprecated', '=', False)]",
        check_company=True,
    )