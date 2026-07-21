# -*- coding: utf-8 -*-
{
    'name': 'HR Contract Allowances | بدلات العقود',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Add multiple types of allowances to employee contracts | إضافة أنواع متعددة من البدلات لعقود الموظفين',
    'description': """
        This module extends the HR Contract module to allow multiple types of allowances:
        - Transportation Allowance
        - Housing Allowance
        - Food Allowance
        - Communication Allowance
        - Performance Allowance
        - Medical Allowance
        - Overtime Allowance
        - Special Allowance
        
        هذا المودول يوسع مودول عقود الموارد البشرية لإتاحة أنواع متعددة من البدلات:
        - بدل المواصلات
        - بدل السكن
        - بدل الطعام
        - بدل الاتصالات
        - بدل الأداء
        - بدل طبي
        - بدل الوقت الإضافي
        - بدل خاص
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['hr_contract', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/allowance_types_data.xml',
        'views/hr_contract_views.xml',
        'views/hr_allowance_type_views.xml',
        'views/hr_allowance_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}