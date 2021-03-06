# coding: utf8

db.define_table('library',
    Field('name', requires=IS_NOT_EMPTY()),
    Field('checkout_days', 'integer', default='14'),
    Field('last_modified_by', db.auth_user, default=auth.user_id, readable=False, writable=False),
    )

LOCATIONS = ('checked_out', 'missing', 'binding', 'stacks')
FORMATS = ('hardback', 'paperback', 'special_binding')

db.define_table('book_copy',
    Field('isbn', requires=IS_NOT_EMPTY()),
    Field('authors', 'list:string'),
    Field('title', requires=IS_NOT_EMPTY()),
    Field('publisher'),
    Field('publication_date'),
    Field('location', requires=IS_IN_SET(LOCATIONS)),
    Field('format', requires=IS_IN_SET(FORMATS)),
    Field('barcode', requires=IS_NOT_EMPTY()),
    Field('description', 'text'),
    format='%(barcode)s'
    )

db.define_table('patron',
    Field('first_name', requires=IS_NOT_EMPTY()),
    Field('last_name', requires=IS_NOT_EMPTY()),
    Field('email', requires=IS_EMAIL()),
    Field('fines', 'decimal(4, 2)', default='00.00', writable=False),
    Field('membership_id', requires=IS_NOT_EMPTY()),
    Field('suspended', 'boolean', default=False, writable=False)
    )
    
db.define_table('checkout',
    Field('patron_id', db.patron, readable=False, writable=False),
    Field('copy_id', db.book_copy, readable=False, writable=False),
    Field('check_out_date', 'date', readable=False, writable=False),
    Field('due_date', 'date', readable=False, writable=False)
    )
    
db.define_table('review',
    Field('book_id', db.book_copy, readable=False, writable=False),
    Field('heading', requires=IS_NOT_EMPTY()),
    Field('body', 'text', requires=IS_NOT_EMPTY()),
    Field('written_by', db.auth_user, default=auth.user_id, readable=False, writable=False),
    Field('written_on', 'date', readable=False, writable=False)
    )
db.define_table('news_post',
    Field('headline', requires=IS_NOT_EMPTY()),
    Field('body', 'text', requires=IS_NOT_EMPTY()),
    Field('written_on', 'date', readable=False, writable=False)
    )
