# -*- coding: utf-8 -*-
# Code Solution - Mail Enterprise (without web_enterprise dependency)

{
    'name': 'Mail Enterprise',
    'category': 'Productivity/Discuss',
    'depends': ['mail'],  # Removed web_mobile dependency (which requires web_enterprise)
    'description': """
Mail Enterprise
===============

Display a preview of the last chatter attachment in the form view for large
screen devices.

This is a modified version without web_enterprise dependency.
""",
    'auto_install': False,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'mail_enterprise/static/src/core/common/**/*',
            'mail_enterprise/static/src/**/*',
        ],
        'web.assets_tests': [
            'mail_enterprise/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'mail_enterprise/static/tests/**/*',
        ],
    }
}
