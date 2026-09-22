from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    purchase_down_payment_account_id = fields.Many2one(
        'account.account',
        string='Purchase Down Payment Account',
        help=(
            'Account used to record purchase down payments. '
            'The account is debited when a down payment is paid '
            'and credited when the down payment is applied to a vendor bill.'
        ),
    )