# -*- coding: utf-8 -*-
{
    'name': 'Code Solution Theme',
    'version': '18.0.1.1.0',
    'category': 'Themes/Backend',
    'summary': 'Modern Enterprise-like Theme for Odoo with AppsBar Sidebar',
    'description': """
Code Solution Theme
===================
A professional, modern backend theme inspired by Odoo Enterprise.

Features:
- Modern color scheme with gradient navbar
- Apps Sidebar (AppsBar) for quick navigation
- Improved UI/UX components
- Full RTL (Arabic) support
- Enhanced list, kanban, and form views
- Developer credit badge

Developed by Code Solution
    """,
    'author': 'Code Solution',
    'website': 'https://codesolution.com',
    'license': 'LGPL-3',
    'depends': ['web', 'base_setup'],
    'data': [
        'views/webclient_templates.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('before', 'web/static/src/scss/primary_variables.scss', 
             'code_solution_theme/static/src/scss/primary_variables.scss'),
            'code_solution_theme/static/src/scss/variables_appsbar.scss',
        ],
        'web._assets_secondary_variables': [
            ('before', 'web/static/src/scss/secondary_variables.scss', 
             'code_solution_theme/static/src/scss/secondary_variables.scss'),
        ],
        'web._assets_backend_helpers': [
            ('before', 'web/static/src/scss/bootstrap_overridden.scss', 
             'code_solution_theme/static/src/scss/bootstrap_overridden.scss'),
            'code_solution_theme/static/src/scss/mixins.scss',
        ],
        'web.assets_frontend': [
            'code_solution_theme/static/src/webclient/home_menu/home_menu_background.scss',
            'code_solution_theme/static/src/webclient/navbar/navbar.scss',
        ],
        'web.assets_backend': [
            # WebClient extension
            'code_solution_theme/static/src/webclient/webclient.js',
            # Other styles
            'code_solution_theme/static/src/webclient/**/*.scss',
            'code_solution_theme/static/src/views/**/*.scss',
            'code_solution_theme/static/src/core/**/*.scss',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
