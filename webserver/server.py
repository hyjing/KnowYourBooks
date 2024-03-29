
"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""
import os
  # accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, flash, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from BookContent import BookDetail
from RatingComment import UpdateRatingComment
from Recommendation import Recommend
from LikeUnlikeBook import LikeUnlikeBooks

import json
tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@35.243.220.243/proj1part2
#
# For example, if you had username gravano and password foobar, then the following line would be:
#
#     DATABASEURI = "postgresql://gravano:foobar@35.243.220.243/proj1part2"
#
DATABASEURI = "postgresql://yc3702:9833@35.243.220.243/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
# Example of running queries in your database
# Note that this will probably not work if you already have a table named 'test' in your database, containing meaningful data. This is only an example showing you how to run queries in your database using SQLAlchemy.
#
# engine.execute("""CREATE TABLE IF NOT EXISTS test (
#   id serial,
#   name text
# );""")
# engine.execute("""INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace');""")


@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request 
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request.

  The variable g is globally accessible.
  """
  try:
    g.conn = engine.connect()
  except:
    print("uh oh, problem connecting to database")
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't, the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to, for example, localhost:8111/foobar/ with POST or GET then you could use:
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#
@app.route('/')
def index():
  if session.get('user_id'):
    return render_template("/home.html")
  return render_template("index.html")

@app.route('/delete', methods=['GET', 'POST'])
def deleteUser():
  g.conn.execute(
    'DELETE FROM yc3702.user WHERE uid = {};'.format(session['user_id'])
  )
  session.clear()
  return render_template("index.html")

@app.route('/types', methods=['GET', 'POST'])
def types():
  posts = g.conn.execute(
      "SELECT * FROM type T, liketype LT"
      " WHERE LT.uid = {} AND LT.tid = T.tid;".format(session['user_id'])
  ).fetchall()

  allTypes = g.conn.execute(
      "SELECT * FROM type T"
      " WHERE T.tid NOT IN (SELECT T2.tid FROM type T2, liketype LT WHERE LT.uid = {} AND LT.tid = T2.tid);".format(session['user_id'])
  ).fetchall()

  if request.method == 'POST':
    if 'type' in request.form:
      session['tid'] = request.form["type"]
      return redirect("/book")
    elif 'like_tid' in request.form:
      g.conn.execute(
        'INSERT INTO liketype(tid, uid) VALUES ({}, {});'.format(request.form["like_tid"], session['user_id'])
      )
      return redirect("/types")
    elif 'dislike_tid' in request.form:
        g.conn.execute(
          'DELETE FROM liketype WHERE tid = {} AND uid = {};'.format(request.form["dislike_tid"], session['user_id']))
        return redirect("/types")
  return render_template("types.html", posts=posts, allTypes=allTypes)

@app.route('/book', methods=['GET', 'POST'])
def book():
  if session.get('tid') == None:
    return redirect("/types")
  
  tid = int(session['tid'].encode("utf-8"))
  posts = g.conn.execute(
      "SELECT B.isbn, B.title, B.date, B.outline FROM book B, booktype BT" + 
      " WHERE BT.tid = {} AND B.isbn = BT.isbn;".format(tid)
  ).fetchall()

  if request.method == 'POST':
    session['isbn'] = request.form["isbn"]
    return redirect("/bookContent")
  return render_template("book.html", posts=posts)

@app.route('/search', methods=['GET', 'POST'])
def search():
  posts = []
  if request.method == 'POST':
    if 'bookname_search' in request.form:
      bookname_search = request.form["bookname_search"]
      posts = g.conn.execute(
        "SELECT B.isbn, B.title, B.date, B.outline FROM book B"
        " WHERE B.title = \'{}\';".format(bookname_search)
      ).fetchall()
    elif 'bookauthor_search' in request.form:
      bookauthor_search = request.form["bookauthor_search"]
      posts = g.conn.execute(
        "SELECT B.isbn, B.title, B.date, B.outline"
        " FROM book B"
        " WHERE B.isbn IN "
        "   (SELECT BA.isbn FROM bookauthor BA, author A"
        "      WHERE BA.wid = A.wid AND (A.last_name = \'{}\' OR A.first_name = \'{}\'));".format(bookauthor_search, bookauthor_search)
      ).fetchall()
  return render_template("/search.html", posts=posts)

@app.route('/login', methods=('GET', 'POST'))
def login():
  if request.method == 'POST':
    email = request.form['username']
    password = request.form['password']
    error = None
    user = g.conn.execute(
        'SELECT * FROM yc3702.user WHERE email = \'{}\';'.format(email)
    ).fetchone()

    if user is None:
        error = 'Incorrect uid.'
    elif user["password"] != password:
        error = "Incorrect password."

    if error is None:
        session.clear()
        session['user_id'] = user['uid']
        # session['user_name'] = user['last_name'] + ' ' + user['first_name']
        return render_template('/home.html')

    flash(error)

  return render_template('login.html')
  # abort(401)
  # this_is_never_executed()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/register', methods=('GET', 'POST'))
def register():
  if request.method == 'POST':
    email = request.form['username']
    password = request.form['password']
    last_name = request.form['lastname']
    first_name = request.form['firstname']
    gender = request.form['gender']
    db = g.conn
    error = None

    if not email:
      error = 'email is required.'
    elif not password:
      error = 'Password is required.'
    elif db.execute(
      'SELECT uid FROM yc3702.user WHERE email = \'{}\';'.format(email)
    ).fetchone() is not None:
      error = 'User \'{}\' is already registered.'.format(email)

    if error is None:
      gen = False
      if gender == 'male':
        gen = True
      db.execute(
        'INSERT INTO yc3702.user (email, password, last_name, first_name, gender) VALUES (\'{}\',\'{}\',\'{}\',\'{}\',{});'
        .format(email, password, last_name, first_name, gen)
      )
      return redirect(url_for('login'))

    flash(error)

  return render_template('register.html')


"""
*************************************************************************************************************************
*************************************************************************************************************************
"""

# TODO: rating/ comment form in BookContent.html -> POST of rating/ comment

@app.route('/bookContent', methods=['GET'])
def getBookContent():
    if 'isbn' not in session:
        session['isbn'] = request.args.get('isbn')
    # session['uid'] = 7
    # session['isbn'] = '978-0345457684'
    # debug
    session['uid'] = session['user_id']
    bd = BookDetail(g.conn, session)
    infos = bd.queryBookInformation()
    book_info = infos['book_info']
    my_comment = infos['my comment']
    other_comment = infos['other comment']
    return render_template('bookContent.html', Bookinfo=book_info, my_comment=my_comment, other_comment=other_comment)


@app.route('/author', methods=['GET'])
def getAuthor():
    return render_template('author.html', Authorinfo=session['author_info'])


@app.route('/comment', methods=['POST', "GET"])
def comment():
    if request.method == "POST":
        content = request.form["comment"]
        addComment = UpdateRatingComment(engine, g.conn)
        addComment.addComment(content, session['isbn'], session['uid'])
    elif request.method == "GET":
        uid = request.args.get("uid")
        time = request.args.get("time")
        isbn = request.args.get("isbn")
        deleteComment = UpdateRatingComment(engine, g.conn)
        deleteComment.deleteComment(uid, time, isbn)
    return redirect('/bookContent')


@app.route('/rating', methods=['POST'])
def rating():
    if request.method == "POST":
        rate = request.form["rating"]
        addRate = UpdateRatingComment(engine, g.conn)
        addRate.addRate(rate, session['isbn'], session['uid'])
    return redirect('/bookContent')


@app.route('/recommend', methods=["GET"])
def recommend():
    if request.method == "GET":
        # session['uid'] = 7
        session['uid'] = session['user_id']
        rc = Recommend(g.conn, session)
        recommend_books = rc.generateRecommendation()
        return render_template("recommendations.html", books=recommend_books)


@app.route('/myLikeBooks', methods=["GET"])
def get_my_liked_book():
    if request.method == "GET":
        # session['uid'] = 7
        session['uid'] = session['user_id']
        like = LikeUnlikeBooks(engine, g.conn)
        my_like_books = like.get_likes(session['uid'])
        return render_template('mylikes.html', books=my_like_books)


@app.route('/addlikedbook', methods=['POST'])
def addLikeBook():
    if request.method == "POST":
        like = LikeUnlikeBooks(engine, g.conn)
        like.addLike(session['isbn'], session['uid'])
    return redirect('/bookContent')


@app.route('/unlikebook', methods=['POST'])
def unlikeBook():
    if request.method == "POST":
        unlike = LikeUnlikeBooks(engine, g.conn)
        unlike.unLike(session['isbn'], session['uid'])
    return redirect('/bookContent')

if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using:

        python server.py

    Show the help text using:

        python server.py --help

    """
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'

    HOST, PORT = host, port
    print("running on %s:%d" % (HOST, PORT))
    # app.degug = True
    # app.run()
    app.run(host=HOST, port=PORT, debug=False, threaded=threaded)

  run()
