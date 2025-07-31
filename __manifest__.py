# Programmer : ======= Mugni =========
{
    'name': 'GM Product Service',
    'version': '0.8',
    'category': 'Stock',
    'summary': 'Tracking status produk yang diservis oleh vendor',
    'author': 'Mugni Hidayat',
    'depends': ['base', 'stock', 'product', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'report/vendor_service_reports.xml',
        'views/vendor_service_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
