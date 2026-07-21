# -*- coding: utf-8 -*-
{
    'name': "Rental Quotation System",
    'version': '18.0.1.0.0',
    'summary': """Advanced rental quotation system with configurable approval workflow""",
    'description': """
        Rental Quotation Management System
        ==================================
        
        Features:
        - Create professional rental quotations
        - Configurable approval workflow rules
        - Multi-level approval system
        - Email notifications and templates
        - Integration with existing real estate module
        - Dashboard and reporting
        - Customer portal access
        
        Key Components:
        - Rental quotations with multiple units
        - Flexible approval rules based on amount, discount, user roles
        - Approval history tracking
        - Automatic conversion to rental contracts
        - Professional PDF reports
    """,
    'author': 'Marsa Matrooh',
    'website': "https://www.marsanmatrooh.com",
    'category': 'Real Estate',
    'depends': ['base', 'mail', 'web', 'account', 'nthub_realestate'],
    'data': [
        # Security
        'security/groups.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/sequence_data.xml',
        'data/quotation_terms_templates.xml',
        'data/default_terms_templates.xml',
        'data/cron_data.xml',
        
        # Reports (must be loaded before views that reference them)
        'report/rental_quotation_arabic_style_report.xml',
        
        # Views (dashboard_views.xml and menus.xml must be loaded after views they reference)
        'views/quotation_terms_template_views.xml',
        'views/rental_quotation_views.xml',
        'views/dashboard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rental_quotation/static/src/js/quotation_dashboard.js',
            'rental_quotation/static/src/xml/quotation_dashboard_template.xml',
            'rental_quotation/static/src/css/dashboard_style.css',
        ],
    },
    'demo': [
        # 'demo/demo_data.xml',  # Will be added when created
    ],
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}