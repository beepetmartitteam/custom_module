from odoo import api, fields, models


class PurchaseOrderCostLine(models.Model):
    _name = 'purchase.order.cost.line'
    _description = 'Purchase Order Estimated Additional Cost'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='cascade',
        index=True,
    )

    company_id = fields.Many2one(
        related='purchase_order_id.company_id',
        store=True,
        readonly=True,
    )

    cost_type_id = fields.Many2one(
        'purchase.cost.type',
        string='Cost Type',
        required=True,
    )

    description = fields.Char(
        string='Description',
    )

    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
    )

    estimated_amount = fields.Monetary(
        string='Estimated Amount',
        currency_field='currency_id',
        required=True,
        default=0.0,
    )

    exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(16, 6),
        help=(
            'Manual exchange rate expressed as company currency '
            'per one unit of the cost currency.'
        ),
    )

    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True,
    )

    amount_company_currency = fields.Monetary(
        string='Amount in Company Currency',
        currency_field='company_currency_id',
        compute='_compute_amount_company_currency',
        store=True,
    )

    note = fields.Text(
        string='Notes',
    )

    @api.depends(
        'estimated_amount',
        'currency_id',
        'exchange_rate',
        'purchase_order_id.date_order',
        'company_id',
    )
    def _compute_amount_company_currency(self):
        for line in self:
            company = line.company_id

            if not company:
                line.amount_company_currency = 0.0
                continue

            if not line.currency_id:
                line.amount_company_currency = 0.0
                continue

            if line.currency_id == company.currency_id:
                line.amount_company_currency = line.estimated_amount
                continue

            if line.exchange_rate:
                line.amount_company_currency = (
                    line.estimated_amount * line.exchange_rate
                )
                continue

            date = (
                line.purchase_order_id.date_order.date()
                if line.purchase_order_id.date_order
                else fields.Date.context_today(line)
            )

            line.amount_company_currency = line.currency_id._convert(
                line.estimated_amount,
                company.currency_id,
                company,
                date,
            )

    @api.onchange('cost_type_id')
    def _onchange_cost_type_id(self):
        if not self.cost_type_id:
            return

        if self.purchase_order_id:
            self.vendor_id = self.purchase_order_id.partner_id

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        if self.purchase_order_id and self.purchase_order_id.currency_id:
            if self.currency_id == self.purchase_order_id.currency_id:
                self.exchange_rate = 0.0

