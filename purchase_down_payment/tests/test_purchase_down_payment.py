from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPurchaseDownPayment(TransactionCase):
    """Test Purchase Down Payment workflow"""

    def setUp(self):
        super(TestPurchaseDownPayment, self).setUp()
        
        # Create company
        self.company = self.env['res.company'].create({
            'name': 'Test Company',
        })
        
        # Create partner/vendor
        self.vendor = self.env['res.partner'].create({
            'name': 'Test Vendor',
            'supplier_rank': 1,
        })
        
        # Create product
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
            'purchase_method': 'purchase',
        })
        
        # Create purchase order
        self.purchase_order = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 10.0,
                    'product_uom': self.product.uom_po_id.id,
                    'price_unit': 100.0,
                })
            ],
        })
        
        # Configure down payment account
        self.down_payment_account = self.env['account.account'].create({
            'name': 'Down Payment Account',
            'code': 'DP001',
            'account_type': 'asset_current',
            'company_id': self.company.id,
        })
        
        self.company.purchase_down_payment_account_id = self.down_payment_account.id
        
        # Configure payment journal
        self.journal = self.env['account.journal'].create({
            'name': 'Test Bank Journal',
            'code': 'TBNK',
            'type': 'bank',
            'company_id': self.company.id,
            'default_account_id': self.env['account.account'].create({
                'name': 'Bank Account',
                'code': 'BNK001',
                'account_type': 'asset_current',
                'company_id': self.company.id,
            }).id,
        })
        
        # Create supplier proforma
        self.proforma = self.env['purchase.proforma'].create({
            'purchase_order_id': self.purchase_order.id,
            'state': 'dp_requested',
        })

    def test_down_payment_creation(self):
        """Test down payment creation"""
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,  # 30% of 100
        })
        
        self.assertEqual(down_payment.state, 'draft')
        self.assertEqual(down_payment.amount, 30.0)
        self.assertTrue(down_payment.name)

    def test_create_aligns_purchase_order_from_proforma(self):
        """Nested forms may send a parent PO that does not match the proforma."""
        other_order = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
        })
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': other_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,
        })
        self.assertEqual(down_payment.purchase_order_id, self.purchase_order)
        self.assertEqual(down_payment.proforma_id, self.proforma)
        
    def test_down_payment_confirmation(self):
        """Test down payment confirmation"""
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,
        })
        
        down_payment.action_confirm()
        
        self.assertEqual(down_payment.state, 'confirmed')
        
    def test_down_payment_approval(self):
        """Test down payment approval"""
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,
        })
        
        down_payment.action_confirm()
        down_payment.action_approve()
        
        self.assertEqual(down_payment.state, 'approved')
        
    def test_register_payment_wizard(self):
        """Test payment registration wizard"""
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,
        })
        
        down_payment.action_confirm()
        down_payment.action_approve()
        
        # Open payment wizard
        action = down_payment.action_register_payment()
        
        self.assertEqual(action['res_model'], 'purchase.down.payment.payment.wizard')
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['context']['default_down_payment_id'], down_payment.id)
        
    def test_payment_creation(self):
        """Test payment creation through wizard"""
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,
        })
        
        down_payment.action_confirm()
        down_payment.action_approve()
        
        # Create payment
        wizard = self.env['purchase.down.payment.payment.wizard'].with_context(
            default_down_payment_id=down_payment.id
        ).create({
            'down_payment_id': down_payment.id,
            'amount': 30.0,
            'journal_id': self.journal.id,
            'payment_date': fields.Date.context_today(self),
        })
        
        wizard.action_create_payment()
        
        down_payment.refresh()
        self.assertEqual(down_payment.state, 'paid')
        self.assertEqual(down_payment.payment_amount, 30.0)
        self.assertTrue(down_payment.payment_move_id)
        
    def test_down_payment_cancellation(self):
        """Test down payment cancellation"""
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,
        })
        
        down_payment.action_cancel()
        
        self.assertEqual(down_payment.state, 'cancelled')
        
    def test_cannot_cancel_paid_down_payment(self):
        """Test that paid down payments cannot be cancelled"""
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': 30.0,
        })
        
        down_payment.action_confirm()
        down_payment.action_approve()
        
        wizard = self.env['purchase.down.payment.payment.wizard'].with_context(
            default_down_payment_id=down_payment.id
        ).create({
            'down_payment_id': down_payment.id,
            'amount': 30.0,
            'journal_id': self.journal.id,
            'payment_date': fields.Date.context_today(self),
        })
        
        wizard.action_create_payment()
        
        with self.assertRaises(Exception):
            down_payment.action_cancel()

    def _create_paid_down_payment(self, amount=30.0):
        down_payment = self.env['purchase.down.payment'].create({
            'purchase_order_id': self.purchase_order.id,
            'proforma_id': self.proforma.id,
            'amount': amount,
        })
        down_payment.action_confirm()
        down_payment.action_approve()
        wizard = self.env['purchase.down.payment.payment.wizard'].with_context(
            default_down_payment_id=down_payment.id
        ).create({
            'down_payment_id': down_payment.id,
            'amount': amount,
            'journal_id': self.journal.id,
            'payment_date': fields.Date.context_today(self),
        })
        wizard.action_create_payment()
        return down_payment

    def test_apply_wizard_rebuilds_lines_without_down_payment_id(self):
        """web_save often omits readonly One2many fields."""
        down_payment = self._create_paid_down_payment(30.0)
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': [(0, 0, {
                'name': 'Test Product',
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })

        wizard = self.env['purchase.down.payment.apply.wizard'].create({
            'vendor_bill_id': bill.id,
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
            'currency_id': bill.currency_id.id,
            'line_ids': [(0, 0, {'apply_amount': 0.0})],
        })

        self.assertEqual(wizard.line_ids.down_payment_id, down_payment)
        self.assertAlmostEqual(wizard.line_ids.apply_amount, 30.0)
        self.assertAlmostEqual(wizard.line_ids.available_amount, 30.0)
