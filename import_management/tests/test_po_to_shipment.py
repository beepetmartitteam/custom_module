# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPoToShipment(TransactionCase):
    """Test Purchase Order to Import Shipment creation with automatic container generation."""
    
    def setUp(self):
        super(TestPoToShipment, self).setUp()
        
        # Create a partner (supplier)
        self.supplier = self.env['res.partner'].create({
            'name': 'Test Supplier',
            'supplier_rank': 1,
            'email': 'supplier@example.com',
        })
        
        # Create products
        self.product1 = self.env['product.product'].create({
            'name': 'Product A',
            'default_code': 'PROD-A',
            'list_price': 100.0,
            'standard_price': 80.0,
        })
        
        self.product2 = self.env['product.product'].create({
            'name': 'Product B',
            'default_code': 'PROD-B',
            'list_price': 150.0,
            'standard_price': 120.0,
        })
        
        # Create a Purchase Order
        self.purchase_order = self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'date_order': '2024-01-01',
        })
        
        # Add order lines
        self.po_line1 = self.env['purchase.order.line'].create({
            'order_id': self.purchase_order.id,
            'product_id': self.product1.id,
            'product_qty': 10.0,
            'price_unit': 85.0,
        })
        
        self.po_line2 = self.env['purchase.order.line'].create({
            'order_id': self.purchase_order.id,
            'product_id': self.product2.id,
            'product_qty': 5.0,
            'price_unit': 130.0,
        })
    
    def test_po_to_shipment_creation(self):
        """Test that creating a shipment from PO creates containers for each line."""
        
        # Call the action to create import shipment
        action = self.purchase_order.action_create_import_shipment()
        
        # Verify action returns correct data
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'import.shipment')
        self.assertIn('res_id', action)
        
        # Get the created shipment
        shipment_id = action['res_id']
        shipment = self.env['import.shipment'].browse(shipment_id)
        
        # Verify shipment was created
        self.assertTrue(shipment.exists())
        self.assertEqual(shipment.purchase_order_id.id, self.purchase_order.id)
        self.assertEqual(shipment.supplier_id.id, self.supplier.id)
        
        # Verify containers were created for each PO line
        self.assertEqual(len(shipment.container_ids), 2)
        
        # Verify container 1 corresponds to PO line 1 (product 1)
        container1 = shipment.container_ids.filtered(lambda c: c.purchase_order_line_id.id == self.po_line1.id)
        self.assertEqual(len(container1), 1, "Should find exactly one container for PO line 1")
        self.assertEqual(container1.product_id.id, self.product1.id)
        self.assertEqual(container1.quantity, 10.0)
        self.assertIn('PROD-A', container1.name)
        
        # Verify container 2 corresponds to PO line 2 (product 2)
        container2 = shipment.container_ids.filtered(lambda c: c.purchase_order_line_id.id == self.po_line2.id)
        self.assertEqual(len(container2), 1, "Should find exactly one container for PO line 2")
        self.assertEqual(container2.product_id.id, self.product2.id)
        self.assertEqual(container2.quantity, 5.0)
        self.assertIn('PROD-B', container2.name)
    
    def test_po_to_shipment_with_empty_lines(self):
        """Test shipment creation when PO has no product lines."""
        
        # Create a PO without lines
        empty_po = self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'date_order': '2024-01-01',
        })
        
        # Call the action
        action = empty_po.action_create_import_shipment()
        
        # Verify shipment was created
        shipment_id = action['res_id']
        shipment = self.env['import.shipment'].browse(shipment_id)
        
        self.assertTrue(shipment.exists())
        
        # Verify no containers were created (no PO lines)
        self.assertEqual(len(shipment.container_ids), 0)
    
    def test_po_shipment_count(self):
        """Test that shipment count is computed correctly."""
        
        # Initially, count should be 0
        self.assertEqual(self.purchase_order.import_shipment_count, 0)
        
        # Create a shipment
        action = self.purchase_order.action_create_import_shipment()
        shipment_id = action['res_id']
        
        # Refresh the PO
        self.purchase_order.invalidate_recordset()
        
        # Count should now be 1
        self.assertEqual(self.purchase_order.import_shipment_count, 1)
        
        # Verify the smart button action
        action = self.purchase_order.action_view_import_shipments()
        self.assertEqual(action['res_model'], 'import.shipment')
        self.assertEqual(action['domain'], [('purchase_order_id', '=', self.purchase_order.id)])
    
    def test_multiple_shipments_from_same_po(self):
        """Test creating multiple shipments from the same PO."""
        
        # Create first shipment
        action1 = self.purchase_order.action_create_import_shipment()
        shipment1_id = action1['res_id']
        
        # Create second shipment
        action2 = self.purchase_order.action_create_import_shipment()
        shipment2_id = action2['res_id']
        
        # Verify both shipments exist and are different
        self.assertNotEqual(shipment1_id, shipment2_id)
        
        shipment1 = self.env['import.shipment'].browse(shipment1_id)
        shipment2 = self.env['import.shipment'].browse(shipment2_id)
        
        self.assertTrue(shipment1.exists())
        self.assertTrue(shipment2.exists())
        
        # Both should be linked to the same PO
        self.assertEqual(shipment1.purchase_order_id.id, self.purchase_order.id)
        self.assertEqual(shipment2.purchase_order_id.id, self.purchase_order.id)
        
        # Verify shipment count is 2
        self.purchase_order.invalidate_recordset()
        self.assertEqual(self.purchase_order.import_shipment_count, 2)
