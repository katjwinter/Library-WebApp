# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a samples controller
## - index is the default action of any application
## - user is required for authentication and authorization
## - download is for downloading files uploaded in the db (does streaming)
## - call exposes all registered services (none by default)
#########################################################################
import urllib2
import json
import datetime
import string
from gluon.tools import Crud
crud = Crud(db)
today = datetime.date.today()
now = datetime.datetime.now()

# API Key for Google Books API so we can pull book information from Google
apikey = 'AIzaSyBu6h-mWzI9x3BMwuaMntFEC_iIWpnRs2o'

# Helper method to append the librarian-specific menu items
def add_librarian_menu():
    response.menu.append([T('Check Out'), False, URL(request.application, 'default', 'checkout'),])
    response.menu.append([T('Check In'), False, URL(request.application, 'default', 'checkin'),])
    response.menu.append([T('Create Patron'), False, URL(request.application, 'default', 'create_patron'),])
    response.menu.append([T('View Patron'), False, URL(request.application, 'default', 'view_patron'),])
    response.menu.append([T('Add to Library Catalog'), False, URL(request.application, 'default', 'add_to_catalog'),])
    response.menu.append([T('Manage Library Catalog'), False, URL(request.application, 'default', 'manage_catalog'),])
    response.menu.append([T('Public Catalog'), False, URL(request.application, 'default', 'public_catalog'),])
    response.menu.append([T('Manage Librarian Accounts'), False, URL(request.application, 'default', 'manage_librarian_accounts'),])
    response.menu.append([T('Modify Library Settings'), False, URL(request.application, 'default', 'modify_library_settings'),])
    
# Helper method to append the public-specific menu items
def add_public_menu():
    response.menu.append([T('Online Catalog'), False, URL(request.application, 'default', 'public_catalog'),])
    
@auth.requires_membership('librarians')
def add_post():
    db.news_post.written_on.default = today
    form = SQLFORM(db.news_post)
    if form.process().accepted:
        session.flash = "Post added"
        redirect(URL('index'))
        
    return dict(form=form)

# Remove a news posting
@auth.requires_membership('librarians')
def remove_post():
    post_id = request.args(0)
    if post_id:
        db(db.news_post.id == post_id).delete()
        session.flash = "Post Removed"
    redirect(URL('index'))
    
# Home page - news, info, etc. Viewable by all, editable by librarians
def index():
    # See if the library has been configured yet. If not, redirect to setup page
    library = db(db.library).select().last()
    if not library:
        redirect(URL('initial_setup'))
    # If user is logged in as a librarian, add the librarian menu options for them  
    if auth.has_membership('librarians'):
        add_librarian_menu()
    else:
        add_public_menu()
    # Get the most recent 5 news posts
    news_posts = db(db.news_post).select(limitby=(0,5))
         
    return dict(news_posts=news_posts)
    
# Initial setup for the library system - creates the library's name and the first librarian account 
def initial_setup():

    # After librarian account is created, don't redirect to profile page
    auth.is_logged_in = lambda: False

    # Get library record, if it has been named
    library = db(db.library).select().last()
    # Get the librarians, if any have been created
    librarians_group = db(db.auth_group.role == 'librarians').select().first()
    if librarians_group:
        librarians = db(db.auth_membership.group_id==librarians_group.id).select()
    else:
        librarians = None
    
    # If both the library name and the first librarian have been created, redirect to home
    # Because in that case, no further setup on this page needs to be done
    if library and librarians:
        redirect(URL('index'))

    # If the first librarian has been created, but library not yet been named,
    # only show the library name form if the current user is a librarian
    # Otherwise redirect them to the login page
    if librarians and auth.has_membership('librarians'):
        # Sets the library's name and how many days books can be checked out
        form = SQLFORM(db.library)
        if form.process().accepted:
            session.flash = 'Library name and number of days for book checkouts has been set'
            redirect(URL('index'))
    # If first librarian has been created, but the current user not them, then redirect to login
    if librarians and not auth.has_membership('librarians'):
        redirect(URL('user', args='login'))
        
    # If no librarians have been created yet, present the form to create one
    if not librarians:
        # if library also hasn't been named, present form to set it up
        if not library:
            form = SQLFORM(db.library)
        # Sets the newly registered account as part of the librarians group for auth    
        def post_register(reg_form):
            librarian_group_id = auth.add_group('librarians', 'full access to the library system')
            auth.add_membership(librarian_group_id)     
        # Sets register form so that after accepting, it calls our post_register() method above
        auth.settings.register_onaccept = post_register
        # Remind the librarian that they don't need to fill in the patron membership field
        db.auth_user.patron_membership_id.comment = "leave blank for librarian accounts"
        reg_form = auth.register()
        
    # Otherwise if the first librarian account has been created, don't create the form   
    else:
        reg_form = None
    
    return dict(form=form, reg_form=reg_form)

# Allow librarians to change the library name or number of days books can be checked out
# Person who last modified the information is recorded for auditing such as an employee
# sets books never due or sets an obscene library name :)
@auth.requires_membership('librarians')
def modify_library_settings():
    # Add librarian menu
    add_librarian_menu()
    # Retrieve the current settings
    current_setting = db(db.library).select().last()
    # Display form to change the settings
    db.library.name.default = current_setting.name # This will preserve current name if only checkout days are changed
    form = SQLFORM(db.library, onsuccess=None)
    if form.process().accepted:
        session.flash = 'Library name and/or number of days for book checkouts has been changed'
        redirect(URL('modify_library_settings'))
    return dict(form=form, current_setting=current_setting)
    
# Check out books for a patron
@auth.requires_membership('librarians')
def checkout():
    # Add librarian menu
    add_librarian_menu()
    # Build form to get book's barcode and the patron's id
    form = SQLFORM.factory(Field('barcode', requires=IS_NOT_EMPTY()), Field('patron_id', requires=IS_NOT_EMPTY()), col3={'patron_id':'Read from patron library card'})
    if form.process(onsuccess=None).accepted:
        # Retrieve patron to see if they are suspended
        patron = db(db.patron.id==form.vars.patron_id).select().first()
        # If the patron is suspended, they cannot check out books
        if patron.suspended:
            response.flash = "ALERT: This patron is suspended and cannot check out books until fines are reduced"
        # If they are not suspended, then proceed with book checkout
        else:
            book = db(db.book_copy.barcode==form.vars.barcode).select().first()
            if book:
                # Update location to reflect that the book is checked out
                book.update_record(location='checked_out')
                # Retrieve the number of days a book is allowed to be checked out
                library = db(db.library).select().last()
                checkout_days = library.checkout_days
                delta = datetime.timedelta(days=checkout_days)
                # Set the due date based on how many days a book can be checked out
                due_date = today + delta
                # Create a checkout record for this transaction
                success = db.checkout.insert(patron_id=form.vars.patron_id, copy_id=book.id, check_out_date=today, due_date=today)
                if success:
                    response.flash = "Book checked out successfully"
                else:
                    response.flash = "ERROR: Unable to update database. Check with your administrator"
            else:
                response.flash="ERROR: Scan again. Book with this barcode not found"
            
    return dict(form=form)

# Check in books from a patron
@auth.requires_membership('librarians')
def checkin():
    add_librarian_menu()
    form = SQLFORM.factory(Field('barcode', requires=IS_NOT_EMPTY()))
    if form.process(onsuccess=None).accepted:
        # Find the matching book_copy record for this barcode
        book = db(db.book_copy.barcode==form.vars.barcode).select().first()
        if book:
            # Update the book's location to reflect its return to the stacks
            book.update_record(location='stacks')
            checkout_record = db(db.checkout.copy_id==book.id).select().first() # Checkout record for this copy
            # Make sure book was in fact checked out
            if checkout_record:
                # If the book is overdue, calculate by how much and add to patron's total
                if checkout_record.due_date < today:
                    delta = today - checkout_record.due_date
                    days_overdue = delta.days
                    fines = .25 * days_overdue
                    patron = db(db.patron.id==checkout_record.patron_id).select().first()
                    new_fine_total = fines + patron.fines
                    # Check if fine is now too large
                    if new_fine_total > 99.99:
                        new_fine_total = 99.99
                        response.flash = "Fines have reached maximum. Account suspended"
                        patron.update_record(fines=new_fine_total) # Update with new (max) amount
                        patron.update_record(suspended=True) # Suspend account due to fines
                    else:
                        # Update the patron's record to reflect the addition of the new fines
                        patron.update_record(fines=new_fine_total)
                        response.flash = "Fines have resulted from this transaction. Go to View Patron page to collect"
                else:
                    response.flash = "Book returned successfully without fines"
                db(db.checkout.copy_id==book.id).delete() # Delete the record from checkout
            else:
                response.flash = "ERROR: Book not found in database. Scan barcode again"
        else:
            response.flash = "ERROR: Book is not in the system as checked out"
            
    return dict(form=form)
    
# Create a new patron account
@auth.requires_membership('librarians')
def create_patron():
    # Add the librarian task menu
    add_librarian_menu()
    
    # Form for creating a patron
    form = SQLFORM(db.patron, fields=['first_name', 'last_name', 'email'])
    if form.process().accepted:
        patron = db(db.patron).select().last()
        # Set patron's membership ID
        # By default we are setting this to the date plus the record ID
        stripped_datetime = str(now).translate(None, string.punctuation)
        stripped_datetime = stripped_datetime.replace(' ', '')
        patron.membership_id = stripped_datetime + str(patron.id)
        # Create an auth_user record for the patron so they can log in to the
        # public part of the site to post reviews etc.
        # Note we do not bother creating an auth_group for the user and adding them to it
        # because we won't be making use of them belonging to that default group anyway
        db.auth_user.insert(
            first_name=form.vars.first_name, 
            last_name=form.vars.last_name, 
            email=form.vars.email, 
            password=patron.membership_id, # Would be printed on their library card, so isn't quite the long, cruel password that it seems
            patron_membership_id=patron.membership_id)
        response.flash = "Patron created with membership id / default online password : " + str(patron.membership_id)
    
    return dict(form=form)
    
# View a patron account (typically to see and handle fines)
@auth.requires_membership('librarians')
def view_patron():
    # Add the librarian task menu
    add_librarian_menu()
    
    patron = None
    
    # Form to get the patron id number
    form = SQLFORM.factory(Field('patron_id'), Field('email'))
    if form.process(onsuccess=None).accepted:
        if form.vars.patron_id:
            patron = db(db.patron.id==form.vars.patron_id).select().first()
        elif form.vars.email:
            patron = db(db.patron.email==form.vars.email).select().first()
            
    return dict(form=form, patron=patron)
    
# Pay all or part of a patron's fines
@auth.requires_membership('librarians')
def pay_fine():
    # Add the librarian task menu
    add_librarian_menu()
    
    # Get the patron record
    patron = db(db.patron.id==request.vars.patron_id).select().first()
    
    form = SQLFORM.factory(Field('Amount', requires=IS_DECIMAL_IN_RANGE(00.00, patron.fines), default='00.00'),
        submit_button='Pay')
    if form.process(onsuccess=None).accepted:
            new_fine_amount = patron.fines - form.vars.Amount
            patron.update_record(fines=new_fine_amount)
    
    return dict(patron=patron, form=form)
    
# Create or delete librarian accounts
# Only accessible by other librarians
@auth.requires_membership('librarians')
def manage_librarian_accounts():
    # Add the librarian task menu
    add_librarian_menu()
    # Get list of existing librarians
    librarians_group_row = db(db.auth_group.role == 'librarians').select().first()
    librarians_group_id = librarians_group_row.id
    librarians = db( (db.auth_user.id==db.auth_membership.user_id) & (db.auth_membership.group_id==librarians_group_id) ).select()
    
    # Allow a librarian to create a new account for someone else
    form = SQLFORM(db.auth_user)
    if form.validate():
        admin_user = auth.user # save current librarian account as form submission will automatically change it to new acct
        auth.get_or_create_user(form.vars) # Create the new account from our form
        auth.add_membership(librarians_group_id) # Add the newly created account to the librarians group
        auth.user = admin_user # restore current librarian account as currently logged in account
        session.flash = "New librarian account successfully created"
        redirect(URL('manage_librarian_accounts'))
   
    return dict(new_user_form=form, librarians=librarians)
    
# Helper function to search Google Books API for book info for a given ISBN
def pull_from_google(isbn):
    page = 'https://www.googleapis.com/books/v1/volumes?q=isbn:' + isbn + '&key' + apikey
    request = urllib2.Request(page)
    raw_response = urllib2.urlopen(request)
    response = raw_response.read()
    full_data = json.loads(response)
    results = full_data.get('items')
    return results

# Provides a search mechanism to pull book data from Google
# then displays the complete form so the rest of the data can be added
@auth.requires_membership('librarians')
def add_to_catalog():
    # Add librarian menu
    add_librarian_menu()

    search_form=SQLFORM.factory(Field('isbn', requires=IS_NOT_EMPTY()), submit_button='Get Info')
    if search_form.process(onsuccess=None).accepted:
        # We should only get one match to the isbn, but if in the future we want to search
        # by title or something, which may return multiple results, we will leave this
        # as an array
        matching_books = pull_from_google(search_form.vars.isbn)
        for book in matching_books:
            volume_info = book.get('volumeInfo')
            db.book_copy.title.default = volume_info.get('title')
            db.book_copy.authors.default = volume_info.get('authors')
            db.book_copy.publisher.default = volume_info.get('publisher')
            db.book_copy.publication_date.default = volume_info.get('publishedDate')
            db.book_copy.description.default = volume_info.get('description')
            db.book_copy.isbn.default = search_form.vars.isbn
            # Barcode based off the first 3 digits of isbn + today's datetime
            stripped_datetime = str(now).translate(None, string.punctuation)
            stripped_datetime = stripped_datetime.replace(' ', '')
            db.book_copy.barcode.default = stripped_datetime + search_form.vars.isbn[:3]
    
    copy_form=SQLFORM(db.book_copy, col3={'authors':'...FirstName LastName - ex: Charles Dickens'})
    
    if copy_form.process().accepted:
        response.flash="New book copy successfully added to the library's catalog"
    
    return dict(search_form=search_form, copy_form=copy_form)
    
# Search the catalog
@auth.requires_membership('librarians')
def manage_catalog():
    # Add librarian menu
    add_librarian_menu()
    # Dynamic search form (and results if it has been submitted)
    form, results = dynamic_search(db.book_copy)

    return dict(form=form, results=results)
    
# Public catalog search
def public_catalog():
    # Add public menu
    add_public_menu()
    # Dynamic search form (and results if it has been submitted)
    form, results = dynamic_search(db.book_copy)
        
    return dict(form=form, results=results)
    
# Display public details
def view_details():
    # Add public menu
    add_public_menu()
    
    book_id = request.args(0)
    copy = db(db.book_copy.id == book_id).select().first()
    
    reviews = None
    patron = False
    if auth.user:
        if auth.user.patron_membership_id:
            patron = True
        elif auth.has_membership(auth.user_id, role='librarians'):
            patron = True
    reviews = db(db.review.book_id==book_id).select()
    
    return dict(copy=copy, reviews=reviews, patron=patron)
    
@auth.requires_login()
def add_review():
    form = None
    copy_id = request.args(0)
    if copy_id:
        form = SQLFORM(db.review)
        if form.process().accepted:
            review = db(db.review).select().last()
            review.update_record(book_id = copy_id)
            review.update_record(written_on = today)
            session.flash = "Review posted!"
            redirect(URL('view_details', args=copy_id))
    return dict(form=form)

@auth.requires_membership('librarians')
def delete_review():
    review_id = request.args(0)
    if review_id:
        db(db.review.id == review_id).delete()
        session.flash = "Review Deleted"
    redirect(URL('view_details', args=request.args(1)))
    
# Modify/Delete a book in the catalog
@auth.requires_membership('librarians')
def view_copy_details():
    # Add librarian menu
    add_librarian_menu()
    
    form = None
    location = None
    book_id = request.args(0)
    if book_id:
        copy = db(db.book_copy.id == book_id).select().first()
        
        location = copy.location
        # Location field requires extra processing so that field will be handled as links
        # Provide a form for all other fields
        form = SQLFORM(db.book_copy, record=copy, fields=['isbn', 'title', 'authors', 'publisher', 'publication_date', 'format', 'barcode', 'description'], deletable=False, showid=False)
        
        if form.process().accepted:
            # Redirect back to this page due to an oddity with the form on submission where it
            # fills out the whole list of authors into each author field so if you submit again,
            # you get a list of a list of authors (like [[Joe Smith, Jane Doe],[Joe Smith, Jane Doe]]
            # I will submit the bug once finals are over :) For now, just redirecting back here as refreshing the page avoids the error
            redirect(URL('view_copy_details', args=book_id))
        
    return dict(form=form, location=location)
    
# Mark a copy missing - add fine to patron if lost while checked out and delete record
# Else just updating status to Missing
@auth.requires_membership('librarians')
def process_location_change_missing():
    copy_id = request.args(0)
    if copy_id:
        copy = db(db.book_copy.id == copy_id).select().first()
    if copy:
        checkout_copy = db(db.checkout.copy_id == copy_id).select().first()
        if checkout_copy: # book is checked out
            patron = db(db.patron.id == checkout_copy.patron_id).select().first()
            new_fine_amount = patron.fines + 25.00 # $25 fine for lost book
            patron.update_record(fines=new_fine_amount)
            session.flash = "Patron with membership ID " + patron.membership_id + " has been fined $25 for the missing book"
            # Delete checkout copy
            db(db.checkout.copy_id == copy_id).delete()
        else: # book is not checked out
            copy.update_record(location='missing') # Update record with location as missing
    # Redirect back to the detail view
    redirect(URL('view_copy_details', args=copy_id))

# Update the location to binding
@auth.requires_membership('librarians')
def process_location_change_binding():
    copy_id = request.args(0)
    if copy_id:
        copy = db(db.book_copy.id == copy_id).select().first()
    if copy:
        copy.update_record(location='binding')
    # Redirect back to the detail view
    redirect(URL('view_copy_details', args=copy_id))
    
# Update the location as back in stacks
@auth.requires_membership('librarians')
def process_location_change_stacks():
    copy_id = request.args(0)
    if copy_id:
        copy = db(db.book_copy.id == copy_id).select().first()
    if copy:
        copy.update_record(location='stacks')
    # Redirect back to the detail view
    redirect(URL('view_copy_details', args=copy_id))

# Remove a copy from the database/catalog entirely
@auth.requires_membership('librarians')
def process_delete():
    copy_id = request.args(0)
    if copy_id:
        db(db.book_copy.id == copy_id).delete()
        session.flash = "Copy removed from the catalog"
    # Return home
    redirect(URL('index'))
    
# Helper function to retrieve the number of copies of a book
def get_copies_count(isbn):
    count = 1
    copies = db(db.book_copy.isbn==isbn).select()
    if copies:
        for copy in copies:
            count = count + 1
    return count

# Remove a librarian from the librarian auth group
# Typical use would be when a librarian leaves their employment at the library
@auth.requires_membership('librarians')
def delete_librarian():
    # Get ID for librarians auth group
    librarians_group_row = db(db.auth_group.role=='librarians').select().first()
    librarians_group_id = librarians_group_row.id
    
    # Remove from librarians group membership
    if auth.has_membership(librarians_group_id, request.vars.user_id):
        auth.del_membership(librarians_group_id, request.vars.user_id)
        session.flash = 'Account removed from librarian group'
    
    # Redirect back to manage_librarian_accounts page
    redirect(URL(request.vars.next))

# Helper for dynamic_search to define the search operations
def build_query(field, op, value):
    if op == 'equals':
        if field != 'isbn':
            return field == value.lower()
        return field == value
    elif op == 'not equal':
        if field != 'isbn':
            return field != value.lower()
        return field != value
    elif op == 'contains':
        if field != 'isbn':
            return field.like('%'+value.lower()+'%')
        return field.like('%'+value+'%')

def dynamic_search(table):
    tbl = TABLE()
    selected = []
    ops = ['equals','not equal','contains']
    query = None
    results = None
    fields = ['isbn', 'title', 'authors']
    for field in fields:
        chkval = request.vars.get('chk'+field,None)
        txtval = request.vars.get('txt'+field,None)
        opval = request.vars.get('op'+field,None)
        row = TR(TD(INPUT(_type="checkbox",_name="chk"+field,
                          value=chkval=='on')),
                 TD(field),TD(SELECT(ops,_name="op"+field,
                                     value=opval)),
                 TD(INPUT(_type="text",_name="txt"+field,
                          _value=txtval)))
        tbl.append(row)
        if chkval:
            if txtval:
                query = build_query(table[field].lower(), opval, txtval)
                selected.append(table[field])           
    form = FORM(tbl,INPUT(_type="submit"))
    if query:
        results = db(query).select()
    return form, results  

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())


def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request,db)


def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()


@auth.requires_signature()
def data():
    """
    http://..../[app]/default/data/tables
    http://..../[app]/default/data/create/[table]
    http://..../[app]/default/data/read/[table]/[id]
    http://..../[app]/default/data/update/[table]/[id]
    http://..../[app]/default/data/delete/[table]/[id]
    http://..../[app]/default/data/select/[table]
    http://..../[app]/default/data/search/[table]
    but URLs must be signed, i.e. linked with
      A('table',_href=URL('data/tables',user_signature=True))
    or with the signed load operator
      LOAD('default','data.load',args='tables',ajax=True,user_signature=True)
    """
    return dict(form=crud())
