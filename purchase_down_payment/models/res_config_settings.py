from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    purchase_proforma_journal_id = fields.Many2one(
        related='company_id.purchase_proforma_journal_id',
        readonly=False,
        string='Proforma Journal',
    )

    purchase_proforma_advance_account_id = fields.Many2one(
        related='company_id.purchase_proforma_advance_account_id',
        readonly=False,
        string='Proforma Purchase Advance Account',
    )

    purchase_proforma_payable_account_id = fields.Many2one(
        related='company_id.purchase_proforma_payable_account_id',
        readonly=False,
        string='Proforma Accounts Payable',
    )

    purchase_down_payment_account_id = fields.Many2one(
        related='company_id.purchase_down_payment_account_id',
        readonly=False,
        string='Purchase Down Payment Account',
    )
