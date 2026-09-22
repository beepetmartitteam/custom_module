from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseProforma(models.Model):
    _name = 'purchase.proforma'
    _description = 'Purchase Supplier Proforma Invoice'
    _order = 'id desc'

    # =========================================================
    # BASIC INFORMATION
    # =========================================================

    name = fields.Char(
        string='Proforma Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='restrict',
    )

    partner_id = fields.Many2one(
        related='purchase_order_id.partner_id',
        string='Vendor',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        related='purchase_order_id.company_id',
        string='Company',
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        related='purchase_order_id.currency_id',
        string='Currency',
        store=True,
        readonly=True,
    )

    # =========================================================
    # SUPPLIER PROFORMA
    # =========================================================

    proforma_number = fields.Char(
        string='Supplier Proforma Number',
        required=True,
    )

    proforma_date = fields.Date(
        string='Proforma Date',
        required=True,
        default=fields.Date.context_today,
    )

    due_date = fields.Date(
        string='Payment Due Date',
    )

    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        currency_field='currency_id',
    )

    tax_amount = fields.Monetary(
        string='Tax Amount',
        currency_field='currency_id',
    )

    amount_total = fields.Monetary(
        string='Proforma Total',
        currency_field='currency_id',
    )

    # =========================================================
    # DOWN PAYMENT
    # =========================================================

    down_payment_percentage = fields.Float(
        string='Down Payment %',
        digits='Product Unit of Measure',
    )

    down_payment_amount = fields.Monetary(
        string='Down Payment Amount',
        currency_field='currency_id',
    )

    # =========================================================
    # NOTES / ATTACHMENTS
    # =========================================================

    notes = fields.Text(
        string='Notes',
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'purchase_proforma_attachment_rel',
        'proforma_id',
        'attachment_id',
        string='Attachments',
    )

    # =========================================================
    # WORKFLOW
    # =========================================================

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('verified', 'Verified'),
            ('dp_requested', 'DP Requested'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # =========================================================
    # DOWN PAYMENT RELATION
    # =========================================================

    down_payment_ids = fields.One2many(
        'purchase.down.payment',
        'proforma_id',
        string='Down Payments',
    )

    down_payment_count = fields.Integer(
        string='Down Payment Count',
        compute='_compute_down_payment_count',
    )

    # =========================================================
    # COMPUTE
    # =========================================================

    @api.depends('down_payment_ids')
    def _compute_down_payment_count(self):
        for record in self:
            record.down_payment_count = len(record.down_payment_ids)

    # =========================================================
    # CREATE
    # =========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'purchase.proforma'
                ) or _('New')

        records = super().create(vals_list)

        for record in records:
            if not record.purchase_order_id:
                raise ValidationError(
                    _('Purchase Order is required.')
                )

        return records

    # =========================================================
    # SUBMIT
    # =========================================================

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(
                    _('Only draft proforma invoices can be submitted.')
                )

            if not record.purchase_order_id:
                raise ValidationError(
                    _('Purchase Order is required.')
                )

            if not record.proforma_number:
                raise ValidationError(
                    _('Supplier Proforma Number is required.')
                )

            if not record.proforma_date:
                raise ValidationError(
                    _('Proforma Date is required.')
                )

            if record.amount_total <= 0:
                raise ValidationError(
                    _('Proforma total must be greater than zero.')
                )

            record.state = 'submitted'

    # =========================================================
    # VERIFY
    # =========================================================

    def action_verify(self):
        for record in self:

            if record.state != 'submitted':
                raise UserError(
                    _(
                        'Only submitted proforma invoices '
                        'can be verified.'
                    )
                )

            if record.amount_total <= 0:
                raise ValidationError(
                    _('Proforma total must be greater than zero.')
                )

            if record.down_payment_percentage < 0:
                raise ValidationError(
                    _('Down payment percentage cannot be negative.')
                )

            if record.down_payment_percentage > 100:
                raise ValidationError(
                    _('Down payment percentage cannot exceed 100%.')
                )

            if record.down_payment_amount <= 0:
                raise ValidationError(
                    _('Down payment amount must be greater than zero.')
                )

            if record.down_payment_amount > record.amount_total:
                raise ValidationError(
                    _(
                        'Down payment cannot be greater than '
                        'proforma total.'
                    )
                )

            record.state = 'verified'

    # =========================================================
    # REQUEST DOWN PAYMENT
    # =========================================================

    def action_request_down_payment(self):
        for record in self:

            if record.state != 'verified':
                raise UserError(
                    _(
                        'Only verified proforma invoices '
                        'can request down payment.'
                    )
                )

            if record.down_payment_amount <= 0:
                raise ValidationError(
                    _('Down payment amount must be greater than zero.')
                )

            if record.down_payment_amount > record.amount_total:
                raise ValidationError(
                    _(
                        'Down payment cannot be greater than '
                        'proforma total.'
                    )
                )

            # -------------------------------------------------
            # Check existing active DP
            # -------------------------------------------------

            active_down_payments = record.down_payment_ids.filtered(
                lambda dp: dp.state != 'cancelled'
            )

            if active_down_payments:
                raise UserError(
                    _(
                        'A down payment already exists for '
                        'this Supplier Proforma.'
                    )
                )

            # -------------------------------------------------
            # Create Down Payment
            # -------------------------------------------------

            self.env['purchase.down.payment'].create({
                'purchase_order_id': record.purchase_order_id.id,
                'proforma_id': record.id,
                'amount': record.down_payment_amount,
            })

            record.state = 'dp_requested'

    # =========================================================
    # CANCEL
    # =========================================================

    def action_cancel(self):
        for record in self:

            if record.state == 'cancelled':
                continue

            # -------------------------------------------------
            # Cannot cancel if DP is already confirmed,
            # approved, or paid.
            # -------------------------------------------------

            active_down_payments = record.down_payment_ids.filtered(
                lambda dp: dp.state not in ('cancelled', 'draft')
            )

            if active_down_payments:
                raise UserError(
                    _(
                        'This Proforma cannot be cancelled because '
                        'it already has an active Down Payment.'
                    )
                )

            record.state = 'cancelled'

    # =========================================================
    # VIEW DOWN PAYMENTS
    # =========================================================

    def action_view_down_payments(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Down Payments'),
            'res_model': 'purchase.down.payment',
            'view_mode': 'list,form',
            'domain': [
                ('proforma_id', '=', self.id),
            ],
            'context': {
                'default_purchase_order_id': self.purchase_order_id.id,
                'default_proforma_id': self.id,
            },
        }