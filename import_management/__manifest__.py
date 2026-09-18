{
    "name": "Import Management",
    "version": "18.0.1.0.0",
    "category": "Inventory/Purchase",
    "summary": "Core import management system",
    "description": """
        Import Management System

        Core functionality for import shipment management:
        - Import Shipment tracking with full workflow
        - Container management
        - Shipping line tracking
        - Document management (BL, Invoice, Packing List, etc.)
        - Supplier integration
        - Comprehensive status tracking
        - Landed cost integration for accurate import costing
    """,
    "author": "Beepetmart IT Development",
    "license": "LGPL-3",
    "depends": [
        "base",
        "purchase",
        "stock",
        "stock_landed_costs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/landed_cost_type_data.xml",
        "views/import_shipment_views.xml",
        "views/import_container_views.xml",
        "views/import_shipping_views.xml",
        "views/import_document_views.xml",
        "views/import_management_menus.xml",
        "views/landed_cost_views.xml",
    ],
    "installable": True,
    "application": True,
}