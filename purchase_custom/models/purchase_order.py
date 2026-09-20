from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_type = fields.Selection(
        selection=[
            ('local', 'Local'),
            ('import', 'Import'),
        ],
        string='Purchase Type',
        default='local',
        required=True,
        tracking=True,
    )

    payment_method = fields.Selection(
        selection=[
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('credit_card', 'Credit Card'),
            ('other', 'Other'),
        ],
        string='Payment Method',
        tracking=True,
    )

    purchase_purpose = fields.Selection(
        selection=[
            ('stock', 'Stock'),
            ('asset', 'Asset'),
            ('expense', 'Expense'),
            ('other', 'Other'),
        ],
        string='Purchase Purpose',
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
    )

    project_id = fields.Many2one(
        'project.project',
        string='Project',
    )

    country_origin_id = fields.Many2one(
        'res.country',
        string='Country of Origin',
    )

    port_loading = fields.Char(
        string='Port of Loading',
    )

    port_discharge = fields.Char(
        string='Port of Discharge',
    )

    estimated_cost_line_ids = fields.One2many(
        'purchase.order.cost.line',
        'purchase_order_id',
        string='Estimated Additional Costs',
    )

    estimated_additional_cost = fields.Monetary(
        string='Estimated Additional Cost',
        currency_field='currency_id',
        compute='_compute_estimated_costs',
        store=True,
    )

    estimated_total_cost = fields.Monetary(
        string='Estimated Total Cost',
        currency_field='currency_id',
        compute='_compute_estimated_costs',
        store=True,
    )

    @api.depends(
        'estimated_cost_line_ids.amount_company_currency',
        'amount_total',
        'currency_id',
    )
    def _compute_estimated_costs(self):
        for order in self:
            company_currency = order.company_id.currency_id

            additional_cost = sum(
                order.estimated_cost_line_ids.mapped(
                    'amount_company_currency'
                )
            )

            if order.currency_id == company_currency:
                additional_cost_po_currency = additional_cost
            else:
                date = (
                    order.date_order.date()
                    if order.date_order
                    else fields.Date.context_today(order)
                )

                additional_cost_po_currency = company_currency._convert(
                    additional_cost,
                    order.currency_id,
                    order.company_id,
                    date,
                )

            order.estimated_additional_cost = (
                additional_cost_po_currency
            )

            order.estimated_total_cost = (
                order.amount_total
                + additional_cost_po_currency
            )

    @api.onchange('purchase_type')
    def _onchange_purchase_type(self):
        if self.purchase_type != 'import':
            self.country_origin_id = False
            self.port_loading = False
            self.port_discharge = False
            self.incoterm_id = False