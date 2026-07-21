{
    'name': 'Product Request Portal / بورتال طلب المنتجات',
    'version': '1.0.0',
    'category': 'Warehouse',
    'summary': 'Portal for product requests with internal transfers / بورتال لطلب المنتجات مع التحويلات الداخلية',
    'description': """
        Product Request Portal Module / موديول بورتال طلب المنتجات
        ==========================================================
        
        This module provides a portal interface for users to:
        - Request products from available stock
        - Select source and destination warehouses
        - Track request status and receive confirmations
        - Automatically generate internal transfers upon receipt
        - Dashboard with ApexCharts visualization
        
        يوفر هذا الموديول واجهة بورتال للمستخدمين لـ:
        - طلب المنتجات من المخزون المتاح
        - اختيار المخازن المصدر والوجهة
        - تتبع حالة الطلب والحصول على التأكيدات
        - إنشاء تحويلات داخلية تلقائياً عند الاستلام
        - لوحة تحكم مع مخططات ApexCharts
    """,
    'author': 'Saqifaa Real Estate',
    'depends': [
        'base',
        'portal', 
        'stock',
        'product',
        'mail',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data
        'data/product_request_sequence.xml',
        
        # Views
        'views/product_request_views.xml',
        'views/product_request_line_views.xml',
        'views/res_partner_views.xml',
        'views/menu_views.xml',
        'views/portal_templates.xml',
    ],
    
    'assets': {
        'web.assets_frontend': [
            'https://cdn.jsdelivr.net/npm/apexcharts@3.44.0/dist/apexcharts.min.js',
            'product_request_portal/static/src/css/portal_styles.css',
            'product_request_portal/static/src/js/portal_charts.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}