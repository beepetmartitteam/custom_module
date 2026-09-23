{
    'name': 'Purchase Down Payment',
    'version': '18.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Purchase Proforma Invoice and Down Payment Management',
    'description': """
Purchase Down Payment
=====================

Phase 1:
- Supplier Proforma Invoice
- Purchase Down Payment Request
- Down Payment Approval
- Register Payment
- Purchase Advance / Prepayment
    """,
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'account',
        'stock',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/purchase_proforma_views.xml',
        'views/purchase_down_payment_views.xml',
        'views/purchase_down_payment_form_views.xml',
        'views/purchase_order_views.xml',
        'views/purchase_down_payment_apply_views.xml',
        'views/account_move_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}