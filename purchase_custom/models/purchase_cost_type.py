from odoo import fields, models


class PurchaseCostType(models.Model):
    _name = 'purchase.cost.type'
    _description = 'Purchase Cost Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Cost Type',
        required=True,
    )

    code = fields.Char(
        string='Code',
        required=True,
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    active = fields.Boolean(
        string='Active',
        default=True,
    )

    allow_local = fields.Boolean(
        string='Local Purchase',
        default=True,
    )

    allow_import = fields.Boolean(
        string='Import Purchase',
        default=True,
    )

    description = fields.Text(
        string='Description',
    )

    _sql_constraints = [
        (
            'code_unique',
            'unique(code)',
            'Cost Type Code must be unique.',
        ),
    ]