from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, json, send_from_directory, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
import os
import datetime
import config
import psycopg2
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required
from sqlalchemy.sql import func
from operator import itemgetter
from mytoken import generate_confirmation_token, confirm_token
from imel import send_email
from flask_mail import Mail, Message
from flask_babel import Babel, _

DATABASE_URL = os.environ['DATABASE_URL']
conn = psycopg2.connect(DATABASE_URL, sslmode='require')

# Configure application
app = Flask(__name__)

#app.secret_key = "blaaa"


# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
	response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
	response.headers["Expires"] = 0
	response.headers["Pragma"] = "no-cache"
	return response

# Configure session to use filesystem (instead of signed cookies)
#app.config["SESSION_FILE_DIR"] = mkdtemp()
#app.config["SESSION_PERMANENT"] = False
#app.config["SESSION_TYPE"] = "filesystem"

#Session(app)

app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
mail = Mail(app)
babel = Babel(app)

class Usersn(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(80), unique=True, nullable=False)
	email = db.Column(db.String(80), unique=True, nullable=False)
	pw_hash = db.Column(db.String(255), nullable=False)
	confirmed = db.Column(db.Boolean, nullable=False, default=False)
	confirmed_on = db.Column(db.DateTime, nullable=True)
	agen_id = db.Column(db.Integer, db.ForeignKey('agen.id'), nullable=False)
	agen = db.relationship('Agen', backref=db.backref('postss', lazy=True))
	def __repr__(self):
		return '<%r>' % self.username
		
class Agen(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	value = db.Column(db.String(80), unique=True, nullable=False)
	def __repr__(self):
		return '<%r>' % self.value
		
class Raten(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	eventn_id = db.Column(db.Integer, db.ForeignKey('eventn.id'), nullable=False)
	eventn = db.relationship('Eventn', backref=db.backref('posts', lazy=True))
	usersn_id = db.Column(db.Integer, db.ForeignKey('usersn.id'), nullable=False)
	usersn = db.relationship('Usersn', backref=db.backref('posts', lazy=True))
	overall_r = db.Column(db.Integer, nullable=False)
	terrain_r = db.Column(db.Integer)
	map_course_r = db.Column(db.Integer)
	org_r = db.Column(db.Integer)
	date_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
	def __repr__(self):
		return '<%r>' % self.overall_r
		
class Eventn(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	usersn_id = db.Column(db.Integer, db.ForeignKey('usersn.id'), nullable=False)
	usersn = db.relationship('Usersn', backref=db.backref('postas', lazy=True))
	name = db.Column(db.String(255), nullable=False)
	org = db.Column(db.String(255), nullable=False)
	start_date = db.Column(db.DateTime, nullable=False)
	end_date = db.Column(db.DateTime, nullable=False)
	location = db.Column(db.String(255), nullable=False)
	classifn_id = db.Column(db.Integer, db.ForeignKey('classifn.id'), nullable=False)
	classifn = db.relationship('Classifn', backref=db.backref('postsa', lazy=True))
	link = db.Column(db.String(255), nullable=False)
	countryn_id = db.Column(db.Integer, db.ForeignKey('countryn.id'), nullable=False)
	countryn = db.relationship('Countryn', backref=db.backref('postss', lazy=True))
	def __repr__(self):
		return '<%r>' % self.name
		
class Classifn(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	value = db.Column(db.String(80), unique=True, nullable=False)
	def __repr__(self):
		return '<%r>' % self.value
		
class Countryn(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	value = db.Column(db.String(80), unique=True, nullable=False)
	def __repr__(self):
		return '<%r>' % self.value

class Comment(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	usersn_id = db.Column(db.Integer, db.ForeignKey('usersn.id'), nullable=False)
	usersn = db.relationship('Usersn', backref=db.backref('posta', lazy=True))
	content = db.Column(db.String(1000), nullable=False)
	eventn_id = db.Column(db.Integer, db.ForeignKey('eventn.id'), nullable=False)
	eventn = db.relationship('Eventn', backref=db.backref('posta', lazy=True))
	date_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
	edited = db.Column(db.Integer, nullable=False)
	def __repr__(self):
		return '<%r>' % self.content

class Commentrate(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
	comment = db.relationship('Comment', backref=db.backref('posts', lazy=True))
	usersn_id = db.Column(db.Integer, db.ForeignKey('usersn.id'), nullable=False)
	usersn = db.relationship('Usersn', backref=db.backref('postaas', lazy=True))
	rating = db.Column(db.Integer, nullable=False)
	def __repr__(self):
		return '<%r>' % self.rating
		
db.create_all()

def conf_required():
	us = Usersn.query.filter_by(id=session["user"]).first()
	if us.confirmed == 0:
		return 0
	else:
		return 1

@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(app.config['LANGUAGES'])
	
@app.route("/", methods=["GET", "POST"])
def index():
	if request.method == "GET":
		rows = Eventn.query.all()
		countries = Countryn.query.all()
		classes = Classifn.query.all()
		ages = Agen.query.all()
		events = []
		for i in rows:
			if "user" in session:
				rated = Raten.query.filter_by(eventn_id = i.id, usersn_id = session["user"]).first()
				if rated is None:
					yourr = 0
				else:
					yourr = rated.overall_r
			else:
				yourr = -1
			ev_link = "/event/" + str(i.id)
			s_date = datetime.date(i.start_date.year, i.start_date.month, i.start_date.day)
			e_date = datetime.date(i.end_date.year, i.end_date.month, i.end_date.day)
			events.append([i.id, i.name, s_date, e_date, i.countryn.value, i.location, i.classifn.value, ev_link, yourr])
		for i in events:
			ovr_avg = db.session.query(func.avg(Raten.overall_r).label('average')).filter(Raten.eventn_id == i[0])
			if ovr_avg[0][0] is None:
				i.append(_("0 (not rated)"))
			else:
				i.append(str(round(ovr_avg[0][0], 1)))
		filt = [0, 0, 0]
		return render_template("index.html", events=events, countries=countries, classes=classes, ages=ages, filt=filt)
	else:
		classif = int(request.form.get("classif"))
		country = int(request.form.get("country"))
		age = int(request.form.get("age"))
		countries = Countryn.query.all()
		classes = Classifn.query.all()
		ages = Agen.query.all()
		if classif == 0 and country == 0:
			rows = Eventn.query.all()
		elif classif == 0:
			rows = Eventn.query.filter_by(countryn_id = country)
		elif country == 0:
			rows = Eventn.query.filter_by(classifn_id = classif)
		else:
			rows = Eventn.query.filter_by(classifn_id = classif, countryn_id = country)
		events = []
		for i in rows:
			if "user" in session:
				rated = Raten.query.filter_by(eventn_id = i.id, usersn_id = session["user"]).first()
				if rated is None:
					yourr = 0
				else:
					yourr = rated.overall_r
			else:
				yourr = -1
			ev_link = "/event/" + str(i.id)
			s_date = datetime.date(i.start_date.year, i.start_date.month, i.start_date.day)
			e_date = datetime.date(i.end_date.year, i.end_date.month, i.end_date.day)
			events.append([i.id, i.name, s_date, e_date, i.countryn.value, i.location, i.classifn.value, ev_link, yourr])
		for i in events:
			if age == 0:
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).filter(Raten.eventn_id == i[0])
			else:
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).join(Usersn).filter(Raten.eventn_id == i[0], Usersn.agen_id == age)
			if ovr_avg[0][0] is None:
				i.append(_("0 (not rated)"))
			else:
				i.append(str(round(ovr_avg[0][0], 1)))
		filt = [classif, country, age]
		return render_template("index.html", events=events, countries=countries, classes=classes, ages=ages, filt=filt)
	
@app.route("/register", methods=["GET", "POST"])
def register():
	session.clear()
	if request.method == "GET":
		return render_template("register.html")
	else:
		if not request.form.get("username"):
			return render_template("error.html", err=_("must provide username"))
		if not request.form.get("email"):
			return render_template("error.html", err=_("must provide email"))
		if not request.form.get("password"):
			return render_template("error.html", err=_("must provide password"))
		if not request.form.get("age"):
			return render_template("error.html", err=_("must provide age group"))
		if not request.form.get("confirmation"):
			return render_template("error.html", err=_("must confirm password"))
		if request.form.get("password") != request.form.get("confirmation"):
			return render_template("error.html", err=_("passwords don't match"))
		if len(request.form.get("password")) < 6 or len(request.form.get("password")) > 30:
			return render_template("error.html", err=_("passwords must contain 6-30 characters and at least one number"))
		uname = request.form.get("username").strip()
		email = request.form.get("email") 
		at =  0
		dot = 0
		for i in email:
			if i == '@':
				at += 1
			if i == '.':
				dot +=1
		if at != 1 or dot < 1 or len(email) > 80:
			return render_template("error.html", err=_("invalid email adress (max length: 80)"))
		num = 0
		for c in request.form.get("password"):
			if ord(c) > 47 and ord(c) < 58:
				num += 1
		if num == 0:
			return render_template("error.html", err=_("passwords must contain 6-30 characters and at least one number"))
		rows = Usersn.query.all()
		for i in rows:
			if i.username == uname:
				return render_template("error.html", err=_("username already taken"))
			if i.email == email:
				return render_template("error.html", err=_("email adress already in use"))
		token = generate_confirmation_token(request.form.get("email"))
		confirm_url = url_for('confirm_email', token=token, _external=True)
		html = render_template('activate.html', confirm_url=confirm_url, usn=uname)
		subject = _("Orienteering.rate email confirmation")
		send_email(email, subject, html)
		db.session.add(Usersn(username=uname, email=email, pw_hash=generate_password_hash(request.form.get("password")), confirmed = False, agen_id = request.form.get("age")))
		db.session.commit()
		us = Usersn.query.filter_by(username=uname).first()
		session["conf"] = 0
		session["user"] = us.id
		session["usern"] = us.username
		session["confed"]=0
		session.modified = True
		return redirect("/confirmed")


@app.route('/confirm/<token>', methods=['GET'])
def confirm_email(token):
	email = confirm_token(token)
	if email == False:
		return render_template("confirm.html", conf=2)	
	us = Usersn.query.filter_by(email=email).first_or_404()
	try:
		a = session["user"]
	except:		   
		session["user"] = us.id
		session["usern"] = us.username
		session.modified = True
	if us.confirmed:
		return render_template("confirm.html", conf=3)
	else:
		us.confirmed = True
		us.confirmed_on = datetime.datetime.now()
		db.session.commit()
		session["conf"] = 1
		return render_template("confirm.html", conf=1)
	
@app.route("/confirmed", methods=["GET"])
def confirmed():
	#us = Usersn.query.filter_by(id = session["user"]).first()
	if session["conf"] == 0:
		return render_template("confirm.html", conf=0)
	else:
		return render_template("confirm.html", conf=1)

@app.route('/resend', methods=['GET'])
@login_required
def resend_confirmation():
	if session["conf"] == 1:
		return render_template("confirm.html", conf=3)
	if session["confed"] == None:
		session["confed"] = 1
	else:
		session["confed"] += 1
	if session["confed"] > 1:
		return render_template("confirm.html", conf=4)
	us = Usersn.query.filter_by(id=session['user']).first_or_404()
	token = generate_confirmation_token(us.email)
	confirm_url = url_for('confirm_email', token=token, _external=True)
	html = render_template('activate.html', confirm_url=confirm_url)
	subject = _("Orienteering.rate email confirmation (again)")
	send_email(us.email, subject, html)
	flash(_("Email resent!"), "success")
	return redirect("/confirmed")		

@app.route('/forgotform', methods=['GET'])
def forgotform():
	return render_template("forgot.html")

@app.route("/forgot", methods=["POST"])
def forgot():
	if not request.form.get("email"):
		return render_template("error.html", err=_("must provide email"))
	email = request.form.get("email").strip()
	at = 0
	dot = 0
	for i in email:
		if i == '@':
			at += 1
		if i == '.':
			dot +=1
	if at != 1 or dot < 1 or len(email) > 80:
		return render_template("error.html", err=_("invalid email adress (max length: 80)"))
	us = Usersn.query.filter_by(email=email).first()
	if not us:
		return render_template("error.html", err=_("unused email adress"))
	token = generate_confirmation_token(email)
	reset_url = url_for('reset', token=token, _external=True)
	html = render_template('resetemail.html', reset_url=reset_url, usn=us.username)
	subject = _("Orienteering.rate password reset")
	send_email(email, subject, html)
	flash(_("The email has been sent."), "success")
	return redirect("/login")	 

@app.route('/reset/<token>', methods=['GET'])
def reset(token):
	email = confirm_token(token)
	if email == False:
		return render_template("error.html", err=_("Invalid reset link"))	
	us = Usersn.query.filter_by(email=email).first_or_404()
	try:
		a = session["user"]
	except:		   
		session["user"] = us.id
		session["usern"] = us.username
		if us.confirmed:
			session["conf"] = 1
		else:
			session["conf"] = 0
		session.modified = True
	return render_template("resetform.html")

@app.route("/resetform", methods=["POST"])
def resetform():
	if not request.form.get("password"):
		return render_template("error.html", err=_("must provide password"))
	if not request.form.get("confirmation"):
		return render_template("error.html", err=_("must confirm password"))
	if request.form.get("password") != request.form.get("confirmation"):
		return render_template("error.html", err=_("passwords don't match"))
	if len(request.form.get("password")) < 6 or len(request.form.get("password")) > 30:
		return render_template("error.html", err=_("passwords must contain 6-30 characters and at least one number"))
	num = 0
	for c in request.form.get("password"):
		if ord(c) > 47 and ord(c) < 58:
			num += 1
	if num == 0:
		return render_template("error.html", err=_("passwords must contain 6-30 characters and at least one number"))
	us = Usersn.query.filter_by(id=session["user"]).first()
	us.pw_hash = generate_password_hash(request.form.get("password"))
	db.session.commit()
	flash(_("Password successfully reset!"), "success")
	return redirect("/")
	
@app.route("/login", methods=["GET", "POST"])
def login():
	if request.method == "GET":
		return render_template("login.html")
	else:
		session.clear()
		# Ensure username was submitted
		if not request.form.get("username"):
			return render_template("error.html", err=_("must provide username"))
		# Ensure password was submitted
		elif not request.form.get("password"):
			return render_template("error.html", err=_("must provide password"))
		# Query database for username
		us = Usersn.query.filter_by(username=request.form.get("username").strip()).first()
		# Ensure username exists and password is correct
		if not us or not check_password_hash(us.pw_hash, request.form.get("password")):
			return render_template("error.html", err=_("invalid username and/or password"))
		# Remember which user has logged in
		session["user"] = us.id
		session["usern"] = us.username
		session["conf"] = us.confirmed
		flash(_('This site uses cookies to store your login information.'), "warning")
		session.modified = True
		# Redirect user to home page
		return redirect("/")	

@app.route("/logout")
def logout():
	# Forget any user_id
	session.pop("user", None)
	session.pop("conf", None)
	session.pop("usern", None)
	session.modified = True
	flash(_("Logged out"), "success")
	# Redirect user to login form
	return redirect("/login")

@app.route("/new", methods=["GET", "POST"])
@login_required
def new():
	if conf_required() == 0:
		return redirect("/confirmed")
	if request.method == "GET":
		return render_template("new.html")
	else:
		if not request.form.get("name"):
			return render_template("error.html", err=_("must provide event name"))
		if not request.form.get("org"):
			return render_template("error.html", err=_("must provide organizer"))	  
		if not request.form.get("start_date"):
			return render_template("error.html", err=_("must provide start date"))
		if not request.form.get("end_date"):
			return render_template("error.html", err=_("must provide end date"))
		if request.form.get("end_date") < request.form.get("start_date"):
			return render_template("error.html", err=_("invalid date"))
		if not request.form.get("location"):
			return render_template("error.html", err=_("must provide location"))
		if not request.form.get("country"):
			return render_template("error.html", err=_("must provide country"))
		if not request.form.get("classif"):
			return render_template("error.html", err=_("must choose classification"))
		if not request.form.get("link"):
			return render_template("error.html", err=_("must provide external link"))
		if len(request.form.get("name"))> 255:
			return render_template("error.html", err=_("invalid event name (max length: 255)"))
		if len(request.form.get("org"))> 255:
			return render_template("error.html", err=_("invalid organizer (max length: 255)"))	   
		if len(request.form.get("location"))> 255:
			return render_template("error.html", err=_("invalid event location (max length: 255)"))
		if len(request.form.get("link"))> 255:
			return render_template("error.html", err=_("invalid event link (max length: 255)"))
		try:
			datetime.datetime.strptime(request.form.get("start_date"), '%Y-%m-%d')
		except ValueError:
			return render_template("error.html", err=_("invalid date format (YYYY-MM-DD)"))
		try:
			datetime.datetime.strptime(request.form.get("end_date"), '%Y-%m-%d')
		except ValueError:
			return render_template("error.html", err=_("invalid date format (YYYY-MM-DD)"))	
		country = Countryn.query.filter_by(value=request.form.get("country")).first()
		if country is None:
			db.session.add(Countryn(value=request.form.get("country")))
			db.session.commit()
			country = Countryn.query.filter_by(value=request.form.get("country")).first()
		db.session.add(Eventn(name=request.form.get("name"), org=request.form.get("org"), usersn_id=session["user"], start_date=request.form.get("start_date"), 
			end_date=request.form.get("end_date"), location=request.form.get("location"), classifn_id=request.form.get("classif"), link=request.form.get("link"), countryn_id=country.id))
		db.session.commit()
		eve = Eventn.query.filter_by(name=request.form.get("name"), org=request.form.get("org"), usersn_id=session["user"], start_date=request.form.get("start_date"), 
			end_date=request.form.get("end_date"), location=request.form.get("location"), classifn_id=request.form.get("classif"), link=request.form.get("link"), countryn_id=country.id).first()
		return redirect(url_for("event", eventid = eve.id))
		
@app.route("/event/<eventid>")
@login_required
def event(eventid):
	if conf_required() == 0:
		return redirect("/confirmed")
	try:
		int(eventid)
	except ValueError:
		abort(404)
	eventc = Eventn.query.filter_by(id=eventid).first()
	if eventc is None:
		abort(404)
	rates = Raten.query.filter_by(eventn_id=eventid).all()
	s_date = datetime.date(eventc.start_date.year, eventc.start_date.month, eventc.start_date.day)
	e_date = datetime.date(eventc.end_date.year, eventc.end_date.month, eventc.end_date.day)
	evlist = [eventc.id, eventc.usersn.username, eventc.name, s_date, e_date, eventc.countryn.value, eventc.location, eventc.classifn.value, eventc.link, eventc.org]
	ratings = []
	dbcomments = Comment.query.filter_by(eventn_id=eventid).all()
	comments = []
	for i in dbcomments:
		rat = db.session.query(func.sum(Commentrate.rating).label('sum')).join(Comment).filter(Commentrate.comment_id == i.id, Comment.eventn_id == eventc.id)
		if rat[0][0] is None:
			ratt = 0
		else:
			ratt = rat[0][0]
		myvote = Commentrate.query.filter_by(comment_id = i.id, usersn_id = session["user"]).first()
		if myvote is None:
			vote = 0
		else:
			vote = myvote.rating
		dejttajm = datetime.datetime(i.date_time.year, i.date_time.month, i.date_time.day, i.date_time.hour, i.date_time.minute)
		comrates = Raten.query.filter_by(eventn_id=eventid, usersn_id = i.usersn_id).first()
		comments.append([i.id, i.usersn.username, i.content, dejttajm.strftime("%Y-%m-%d %H:%M"), i.edited, ratt, vote, comrates.overall_r, comrates.terrain_r, comrates.map_course_r, comrates.org_r])
	comments.sort(reverse=True, key=itemgetter(5))
	for i in range(4):
		darab = 0
		if i == 0:
			ovr_avg = db.session.query(func.avg(Raten.overall_r)).filter(Raten.eventn_id == eventc.id)
			tr_avg = db.session.query(func.avg(Raten.terrain_r)).filter(Raten.eventn_id == eventc.id)
			mcr_avg = db.session.query(func.avg(Raten.map_course_r)).filter(Raten.eventn_id == eventc.id)
			or_avg = db.session.query(func.avg(Raten.org_r)).filter(Raten.eventn_id == eventc.id)
			darab = len(rates)
		else:
			ovr_avg = db.session.query(func.avg(Raten.overall_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == i)	
			tr_avg = db.session.query(func.avg(Raten.terrain_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == i)	
			mcr_avg = db.session.query(func.avg(Raten.map_course_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == i)	
			or_avg = db.session.query(func.avg(Raten.org_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == i)
			darab = db.session.query(Raten.overall_r).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == i).count()	
		if ovr_avg[0][0] is None:
			ratings.append([0])
		else:
			ratings.append([round(ovr_avg[0][0], 1), round(tr_avg[0][0], 1), round(mcr_avg[0][0], 1),round(or_avg[0][0], 1), darab])
	usrate = Raten.query.filter_by(usersn_id=session['user'], eventn_id = eventc.id).first()
	mycomm = Comment.query.filter_by(usersn_id=session['user'], eventn_id = eventc.id).first()
	if mycomm is None:
		comm = 0
	else:
		comm = 1
	myrate = []
	if usrate is None:
		rated = 0
	else:
		rated = 1
		myrate.append(usrate.overall_r)
		myrate.append(usrate.terrain_r)
		myrate.append(usrate.map_course_r)
		myrate.append(usrate.org_r)
	return render_template("event.html", evlist=evlist, myrate = myrate, rated = rated, ratings=ratings, comm=comm, mycomm=mycomm, comments=comments)
@app.route("/rate", methods=["POST"])
@login_required
def rate():
	if conf_required() == 0:
		return redirect("/confirmed")
	usrate = Raten.query.filter_by(usersn_id=session['user'], eventn_id = request.form.get("eventid")).first()
	if usrate is not None:
		return redirect(url_for('event', eventid = request.form.get("eventid")))
	if not request.form.get("overall_r"):
		return render_template("error.html", err=_("must rate the event"))
	if not request.form.get("terrain_r"):
		return render_template("error.html", err=_("must rate the event"))
	if not request.form.get("mc_r"):
		return render_template("error.html", err=_("must rate the event"))
	if not request.form.get("org_r"):
		return render_template("error.html", err=_("must rate the event"))
	if request.form.get("comment"):
		if len(request.form.get("comment")) > 1000:
			return render_template("error.html", err=_("Maximum length of a comment is 1000 characters"))
		db.session.add(Comment(usersn_id=session["user"], content = request.form.get("comment"), eventn_id=request.form.get("eventid"), edited = 0))
		com = Comment.query.filter_by(eventn_id = request.form.get("eventid"), usersn_id=session["user"]).first()
		db.session.add(Commentrate(comment_id = com.id, usersn_id=session["user"], rating = 1))
	db.session.add(Raten(eventn_id=request.form.get("eventid"), usersn_id=session["user"], overall_r=request.form.get("overall_r"), terrain_r=request.form.get("terrain_r"), map_course_r=request.form.get("mc_r"), org_r=request.form.get("org_r")))
	db.session.commit()
	return redirect(url_for('event', eventid = request.form.get("eventid")))
	
@app.route("/editrate", methods=["POST"])
@login_required
def editrate():
	if conf_required() == 0:
		return redirect("/confirmed")
	if not request.form.get("overall_r"):
		return render_template("error.html", err=_("must rate the event"))
	if not request.form.get("terrain_r"):
		return render_template("error.html", err=_("must rate the event"))
	if not request.form.get("mc_r"):
		return render_template("error.html", err=_("must rate the event"))
	if not request.form.get("org_r"):
		return render_template("error.html", err=_("must rate the event"))
	erate = Raten.query.filter_by(usersn_id=session['user'], eventn_id = request.form.get("eventid")).first()
	erate.overall_r = request.form.get("overall_r")
	erate.terrain_r = request.form.get("terrain_r")
	erate.map_course_r = request.form.get("mc_r")
	erate.org_r =request.form.get("org_r")
	erate.date_time = datetime.datetime.utcnow()
	comm = Comment.query.filter_by(usersn_id=session['user'], eventn_id = request.form.get("eventid")).first()
	if request.form.get("comment"):
		if len(request.form.get("comment")) > 1000:
			return render_template("error.html", err=_("Maximum length of a comment is 1000 characters"))
		if comm is None:
			db.session.add(Comment(usersn_id=session["user"], content = request.form.get("comment"), eventn_id=request.form.get("eventid"), edited = 0))
			com = Comment.query.filter_by(eventn_id = request.form.get("eventid"), usersn_id=session["user"]).first()
			db.session.add(Commentrate(comment_id = com.id, usersn_id=session["user"], rating = 1))
		else:
			comm.content = request.form.get("comment")
			comm.date_time = datetime.datetime.utcnow()
			comm.edited = 1
	elif comm is not None:
		Commentrate.query.filter_by(comment_id =comm.id).delete()
		Comment.query.filter_by(usersn_id=session['user'], eventn_id = request.form.get("eventid")).delete()
	db.session.commit()
	return redirect(url_for('event', eventid = request.form.get("eventid")))	
	
@app.route("/ratings")
@login_required
def ratings():
	if conf_required() == 0:
		return redirect("/confirmed")
	rows = Raten.query.filter_by(usersn_id = session['user']).all()
	sorok = []
	for i in rows:
		dejttajm = datetime.datetime(i.date_time.year, i.date_time.month, i.date_time.day, i.date_time.hour, i.date_time.minute)
		sorok.append([i.eventn_id, i.eventn.name, i.eventn.classifn.value,	i.overall_r,  i.terrain_r, i.map_course_r, i.org_r, dejttajm.strftime("%Y-%m-%d %H:%M")])
	return render_template("ratings.html", sorok=sorok)

@app.route("/events")
@login_required
def events():
	if conf_required() == 0:
		return redirect("/confirmed")
	rows = Eventn.query.filter_by(usersn_id = session['user']).all()
	evlist = []
	for i in rows:
		evlist.append([i.id, i.name, datetime.date(i.start_date.year, i.start_date.month, i.start_date.day), datetime.date(i.end_date.year, i.end_date.month, i.end_date.day), i.countryn.value, i.location, i.classifn.value])
	return render_template("events.html", evlist=evlist)
	
@app.route("/editevent/<eventid>")
@login_required
def editevent(eventid):
	if conf_required() == 0:
		return redirect("/confirmed")
	try:
		int(eventid)
	except ValueError:
		abort(404)
	eve = Eventn.query.filter_by(id = eventid).first()
	if eve is None:
		abort(404)
	if session["user"] != 2 and session["user"] != eve.usersn_id:
		return render_template("error.html", err=_("403, you don't have permission to view this page."))
	return render_template("editevent.html", eve=eve)

@app.route("/editnew", methods=["POST"])
@login_required
def editnew():
	if conf_required() == 0:
		return redirect("/confirmed")
	if not request.form.get("name"):
		return render_template("error.html", err=_("Event must have a name"))
	if not request.form.get("org"):
		return render_template("error.html", err=_("must provide organizer"))	  
	if not request.form.get("start_date"):
		return render_template("error.html", err=_("Event must have a start date"))
	if not request.form.get("end_date"):
		return render_template("error.html", err=_("Event must have an end date"))
	if request.form.get("end_date") < request.form.get("start_date"):
		return render_template("error.html", err=_("invalid date"))
	if not request.form.get("location"):
		return render_template("error.html", err=_("Event must have a location"))
	if not request.form.get("country"):
		return render_template("error.html", err=_("Event must have a country"))
	if not request.form.get("classif"):
		return render_template("error.html", err=_("Event must have a classification"))
	if not request.form.get("link"):
		return render_template("error.html", err=_("Event must have an external link"))
	if len(request.form.get("name"))> 255:
		return render_template("error.html", err=_("invalid event name (max length: 255)"))
	if len(request.form.get("org"))> 255:
		return render_template("error.html", err=_("invalid organizer (max length: 255)"))		
	if len(request.form.get("location"))> 255:
		return render_template("error.html", err=_("invalid event location (max length: 255)"))
	if len(request.form.get("link"))> 255:
		return render_template("error.html", err=_("invalid event link (max length: 255)"))
	try:
		datetime.datetime.strptime(request.form.get("start_date"), '%Y-%m-%d')
	except ValueError:
		return render_template("error.html", err=_("invalid date format (YYYY-MM-DD)"))
	try:
		datetime.datetime.strptime(request.form.get("end_date"), '%Y-%m-%d')
	except ValueError:
		return render_template("error.html", err=_("invalid date format (YYYY-MM-DD)"))	
	country = Countryn.query.filter_by(value=request.form.get("country")).first()
	if country is None:
		db.session.add(Countryn(value=request.form.get("country")))
		db.session.commit()
		country = Countryn.query.filter_by(value=request.form.get("country")).first()
	eevent = Eventn.query.filter_by(usersn_id=session['user'], id = request.form.get("eventid")).first()
	eevent.name = request.form.get("name")
	eevent.start_date = request.form.get("start_date")
	eevent.end_date = request.form.get("end_date")
	eevent.country =request.form.get("country")
	eevent.location = request.form.get("location")
	eevent.classif_id = request.form.get("classif")
	eevent.link = request.form.get("link")
	db.session.commit()
	return redirect(url_for('event', eventid = request.form.get("eventid")))
	
@app.route("/deleteev", methods=["POST"])
@login_required
def deleteev():
	if conf_required() == 0:
		return redirect("/confirmed")
	evnt = Eventn.query.filter_by(id=request.form.get("eventid")).first()
	c = Eventn.query.filter_by(countryn_id = evnt.countryn_id).all()
	Raten.query.filter_by(eventn_id = request.form.get("eventid")).delete()
	comms = Comment.query.filter_by(eventn_id = evnt.id).all()
	for j in comms:
		Commentrate.query.filter_by(comment_id = j.id).delete()
		Comment.query.filter_by(eventn_id = evnt.id).delete()
	Eventn.query.filter_by(id=request.form.get("eventid")).delete()
	if len(c) == 1:
		Countryn.query.filter_by(id = evnt.countryn_id).delete()
	db.session.commit()
	return redirect("/events")
	
@app.route("/deleter", methods=["POST"])
@login_required
def deleter():
	if conf_required() == 0:
		return redirect("/confirmed")
	Raten.query.filter_by(eventn_id = request.form.get("eventid"), usersn_id = session['user']).delete()
	comm = Comment.query.filter_by(eventn_id = request.form.get("eventid"), usersn_id = session['user']).first()
	if comm is not None:
		Commentrate.query.filter_by(comment_id = comm.id).delete()
		Comment.query.filter_by(eventn_id = request.form.get("eventid"), usersn_id = session['user']).delete()
	db.session.commit()
	return redirect(url_for('event', eventid = request.form.get("eventid")))

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
	if request.method == "GET":
		us = Usersn.query.filter_by(id=session['user']).first()
		return render_template("profile.html", us=us)
	else:
		if not request.form.get("username") and request.form.get("uncheck") is None:
			return render_template("error.html", err=_("must provide username"))
		if request.form.get("uncheck") is None:
			uname = request.form.get("username").strip()
		if request.form.get("pwcheck") is None:
			if not request.form.get("npassword"):
				return render_template("error.html", err=_("must provide password"))
			if not request.form.get("confirmation"):
				return render_template("error.html", err=_("must confirm password"))
			if request.form.get("npassword") != request.form.get("confirmation"):
				return render_template("error.html", err=_("passwords don't match"))
			if len(request.form.get("npassword")) < 6 or len(request.form.get("npassword")) > 30:
				return render_template("error.html", err=_("passwords must contain 6-30 characters and at least one number"))
			num = 0
			for c in request.form.get("npassword"):
				if ord(c) > 47 and ord(c) < 58:
					num += 1
			if num == 0:
				return render_template("error.html", err=_("passwords must contain 6-30 characters and at least one number"))	
		if not request.form.get("age"):
			return render_template("error.html", err=_("must provide age group"))		
		rows = Usersn.query.all()
		if request.form.get("uncheck") is None:	   
			for i in rows:
				if i.username == uname and uname != session['usern']:
					return render_template("error.html", err=_("username already taken"))
		us = Usersn.query.filter_by(id=session['user']).first()
		if not check_password_hash(us.pw_hash, request.form.get("cpassword")):	
			return render_template("error.html", err=_("incorrect password"))
		if request.form.get("uncheck") is None:
			us.username = uname
			session["usern"] = request.form.get("username")
		if request.form.get("pwcheck") is None:
			us.pw_hash = generate_password_hash(request.form.get("npassword"))
		us.agen_id = request.form.get("age")
		db.session.commit()
		return redirect("/")

@app.route("/upvote", methods=["POST"])
@login_required
def upvote():
	if conf_required() == 0:
		return redirect("/confirmed")
	commentid = request.form.get("commentid")
	Commentrate.query.filter_by(comment_id = commentid, usersn_id = session['user']).delete()
	db.session.add(Commentrate(comment_id = commentid, usersn_id=session["user"], rating = 1))
	db.session.commit()
	rat = db.session.query(func.sum(Commentrate.rating).label('sum')).filter(Commentrate.comment_id == commentid)
	if rat[0][0] is None:
		ratt = 0
	else:
		ratt = rat[0][0]
	return json.dumps({'status':'OK', 'rating':ratt})
	
@app.route("/voted", methods=["POST"])
@login_required
def voted():
	if conf_required() == 0:
		return redirect("/confirmed")
	commentid = request.form.get("commentid")
	Commentrate.query.filter_by(comment_id = commentid, usersn_id = session['user']).delete()
	db.session.commit()
	rat = db.session.query(func.sum(Commentrate.rating).label('sum')).filter(Commentrate.comment_id == commentid)
	if rat[0][0] is None:
		ratt = 0
	else:
		ratt = rat[0][0]
	return json.dumps({'status':'OK', 'rating':ratt})
	
@app.route("/downvote", methods=["POST"])
@login_required
def downvote():
	if conf_required() == 0:
		return redirect("/confirmed")
	commentid = request.form.get("commentid")
	Commentrate.query.filter_by(comment_id = commentid, usersn_id = session['user']).delete()
	db.session.add(Commentrate(comment_id = commentid, usersn_id=session["user"], rating = -1))
	db.session.commit()
	rat = db.session.query(func.sum(Commentrate.rating).label('sum')).filter(Commentrate.comment_id == commentid)
	if rat[0][0] is None:
		ratt = 0
	else:
		ratt = rat[0][0]
	return json.dumps({'status':'OK', 'rating':ratt})

@app.route('/favicon.ico')
def favicon():
	return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')	

@app.route("/uncheck", methods=["POST"])
def uncheck():
	rows = Usersn.query.all()
	uname = request.form.get("username").strip()
	for i in rows:
		if i.username == uname:
			return json.dumps({'status':'OK', 'aval':False})
	return json.dumps({'status':'OK', 'aval':True})

@app.route("/emcheck", methods=["POST"])
def emcheck():
	rows = Usersn.query.all()
	for i in rows:
		if i.email == request.form.get("email").strip():
			return json.dumps({'status':'OK', 'aval':False})
	return json.dumps({'status':'OK', 'aval':True})
	
@app.route("/emcheck2", methods=["POST"])
def emcheck2():
	us = Usersn.query.filter_by(email=request.form.get("email").strip()).first()
	if not us:
		return json.dumps({'status':'OK', 'exist':False})
	return json.dumps({'status':'OK', 'exist':True})
	
@app.route("/pwcheck", methods=["POST"])
def pwcheck():
	us = Usersn.query.filter_by(username=request.form.get("username").strip()).first()
	if not us:
		return json.dumps({'status':'OK', 'aval':1})
	elif not check_password_hash(us.pw_hash, request.form.get("password")):
		return json.dumps({'status':'OK', 'aval':2})
	else:
		return json.dumps({'status':'OK', 'aval':0})	
	
@app.route("/deleteacc", methods=["POST"])
@login_required
def deleteacc():
	Raten.query.filter_by(usersn_id = session['user']).delete()
	Commentrate.query.filter_by(usersn_id = session['user']).delete()
	Comment.query.filter_by(usersn_id = session['user']).delete()
	evnt = Eventn.query.filter_by(usersn_id = session['user']).all()
	for i in evnt:
		c = Eventn.query.filter_by(countryn_id = i.countryn_id).all()
		Raten.query.filter_by(eventn_id = i.id).delete()
		comms = Comment.query.filter_by(eventn_id = i.id).all()
		for j in comms:
			Commentrate.query.filter_by(comment_id = j.id).delete()
			Comment.query.filter_by(eventn_id = i.id).delete()
		Eventn.query.filter_by(id=i.id).delete()
		if len(c) == 1:
			Countryn.query.filter_by(id = i.countryn_id).delete()
	Usersn.query.filter_by(id= session["user"]).delete()		
	db.session.commit()
	session.pop("user", None)
	session.pop("usern", None)
	session.pop("conf", None)
	session.modified = True
	return redirect("/")

@app.route("/allevents", methods=["GET"])
@login_required
def allevents():
	if session["user"] != 2:
		return render_template("error.html", err=_("403, you don't have permission to view this page.")), 403
	events = Eventn.query.all()
	return render_template("allevents.html", e=events)

@app.route("/commd/<commid>", methods=["GET"])
@login_required
def commd(commid):
	if session["user"] != 2:
		return render_template("error.html", err=_("403, you don't have permission to view this page.")), 403
	try:
		int(commid)
	except ValueError:
		abort(404)
	comm = Comment.query.filter_by(id=commid).first()
	if comm is None:
		abort(404)
	Commentrate.query.filter_by(comment_id =commid).delete()
	Comment.query.filter_by(id = commid).delete()
	db.session.commit()
	return redirect('/')	

@app.route("/privacy", methods=["GET"])
def privacy():
	return render_template("privacy.html")

@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404