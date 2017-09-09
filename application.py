from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])[0]["cash"]
    report= db.execute("SELECT name, symbol, SUM(number), price FROM records WHERE user_id= :id GROUP BY symbol", id=session["user_id"])

    total= 0
    for info in report:
        symbol= lookup(info["symbol"])
        info["number"]= info["SUM(number)"]
        info["total"]= info["price"]* info["SUM(number)"]
        info["price"]= usd(info["price"])
        total+= info["total"]
        info["total"]= usd(info["total"])

    return render_template("index.html", report=report, cash=cash, symbol=symbol, total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    if request.method == "POST":
        name= lookup(request.form.get("symbol"))
        if not name:
            return apology("Symbol does not exist")
        count= int(request.form.get("number"))
        if not count or count <=0:
            return apology("Number does not exist or should be greater than 0")

        rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        rows = float(rows[0]["cash"])

        if rows < (count*name["price"]):
            return apology("You do not have enough money to purchase this stock.")

        else:
            rows=rows - (count*name["price"])
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=rows, id= session["user_id"])
            db.execute("INSERT INTO records(user_id, name, symbol, number, price) VALUES(:id, :name, :symbol, :number, :price)",
            id=session["user_id"], name=name["name"], symbol=name["symbol"],number= int(request.form.get("number")), price=name["price"])

        return redirect(url_for("index"))
    elif request.method == "GET":
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    hist= db.execute("SELECT user_id, name, symbol, number, price, date FROM records WHERE user_id= :id", id=session["user_id"])
    return render_template("history.html", hist= hist)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        name= lookup(request.form.get("symbol"))
        if not name:
            return apology("Name does not exist")
        name["price"] = usd(name["price"])
        return render_template("quoted.html", letters=name)
    elif request.method == "GET":
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    if request.method == "POST":
        if not request.form.get ("username"):
            return apology("Need username")
        elif not request.form.get ("password"):
            return apology("Need password")
        elif not request.form.get ("validate"):
            return apology("Need password again")
        elif request.form.get ("password") != request.form.get ("validate"):
            return apology("Passwords do not match")

        hash = pwd_context.hash(request.form.get("password"))

        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"),
        hash=hash)
        if not result:
            return apology("Invalid username")

        rows = db.execute("SELECT id FROM users WHERE username = :username", username=request.form.get("username"))
        session["user_id"]= rows[0]["id"]

        return redirect(url_for("index"))

    elif request.method == "GET":
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        name= lookup(request.form.get("symbol"))
        if not name:
            return apology("Symbol does not exist")
        count= int(request.form.get("number"))
        if not count or count <=0:
            return apology("Number does not exist or should be greater than 0")

        present= db.execute("SELECT SUM(number) FROM records WHERE user_id= :id AND name= :name AND symbol= :symbol",
        id=session["user_id"], name=name["name"], symbol=name["symbol"])
        if not present[0]["SUM(number)"]:
            return apology("No instance of stock found")

        if present[0]["SUM(number)"]<count:
            return apology("Count exceeds number of stocks owned")

        rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        rows = float(rows[0]["cash"])


        if rows < (count*name["price"]):
            return apology("Stock cannot be sold.")

        else:
            rows=rows + (count*name["price"])
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=rows, id= session["user_id"])
            db.execute("INSERT INTO records(user_id, name, symbol, number, price) VALUES(:id, :name, :symbol, :number, :price)",
            id=session["user_id"], name=name["name"], symbol=name["symbol"],number= -(int(request.form.get("number"))), price=name["price"])

        return redirect(url_for("index"))
    elif request.method == "GET":
        return render_template("sell.html")
