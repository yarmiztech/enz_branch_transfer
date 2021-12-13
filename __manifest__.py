# -*- coding: utf-8 -*-
{
    'name': "Inter Company Transfer",
    'author':
        'Enzapps',
    'summary': """
This module will help to transfer stock from one company to Another Company
""",

    'description': """
        Long description of module's purpose
    """,
    'website': "",
    'category': 'base',
    'version': '12.0',
    'depends': ['base','account',"stock","boraq_company_branches"],
    "images": ['static/description/icon.png'],
    'data': [
        'security/ir.model.access.csv',
        'data/seq.xml',
        'views/inter_company.xml',
          ],
    'demo': [
    ],
    'installable': True,
    'application': True,
}
