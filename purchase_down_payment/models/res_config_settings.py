from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    purchase_down_payment_account_id = fields.Many2one(
        related='company_id.purchase_down_payment_account_id',
        string='Purchase Down Payment Account',
        readonly=False,
        domain="[('company_id', '=', company_id)]",
    )