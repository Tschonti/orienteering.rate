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
from sqlalchemy import and_
from operator import itemgetter
from mytoken import generate_confirmation_token, confirm_token
from imel import send_email
from flask_mail import Mail, Message
from flask_babel import Babel, _
from operator import itemgetter
import requests
import time
from flask_socketio import SocketIO, emit
from flask_wtf.csrf import CSRFProtect, CSRFError
from bs4 import BeautifulSoup

# Configure database
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

# Initialize apps and framworks
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
mail = Mail(app)
babel = Babel(app)
socketio = SocketIO(app)
csrf = CSRFProtect(app)

if __name__ == '__main__':
    socketio.run(app)

### Tables of the database ###

# Table for users, connected to the Age table
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

# Table for the values of Age groups (Youth, Elite, Master)		
class Agen(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	value = db.Column(db.String(80), unique=True, nullable=False)
	def __repr__(self):
		return '<%r>' % self.value

# Table that contains every rating. Connected to the Event and User table.		
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

# Table that contains every event. Connected to the Classification, Country and User table.	
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

# Table for the values of Classifications (Regional, National, National champs, International and IOF events)		
class Classifn(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	value = db.Column(db.String(80), unique=True, nullable=False)
	def __repr__(self):
		return '<%r>' % self.value

# Table for the values of countries (only contains the countries that have at least one event associated with them.)			
class Countryn(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	value = db.Column(db.String(80), unique=True, nullable=False)
	def __repr__(self):
		return '<%r>' % self.value

# Table that contains every comment. Connected to the User and Event table.
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

# Table that contains every rating of comments. Connected to the User and Comment table. 
class Commentrate(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
	comment = db.relationship('Comment', backref=db.backref('posts', lazy=True))
	usersn_id = db.Column(db.Integer, db.ForeignKey('usersn.id'), nullable=False)
	usersn = db.relationship('Usersn', backref=db.backref('postaas', lazy=True))
	rating = db.Column(db.Integer, nullable=False)
	def __repr__(self):
		return '<%r>' % self.rating

# Table for other, misc. data. For example: last date of api import
class Util(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(80), nullable=False)
	data = db.Column(db.DateTime, nullable=False)
		
db.create_all()

# Function that checks whether the user's account is confirmed via email.
def conf_required():
	us = Usersn.query.filter_by(id=session["user"]).first()
	if us.confirmed == 0:
		return 0
	else:
		return 1

# A route that imports suitable events from Liveresultat's database through their public API.
# Currently not part of the project
@app.route("/importapi", methods=['GET'])
@login_required
def importapi():
	return redirect("/")
	"""
	if conf_required() == 0:
		return redirect("/confirmed")
	#res = requests.get("https://eventor.orienteering.org/api/events", params={"fromDate": "2020-01-01", "toDate": '2020-03-31'}, headers={"ApiKey": "378a90e9017641ccbd37792431f6bc4b"})
	
	lastdate = Util.query.first()
	reallastdate = datetime.date(lastdate.data.year, lastdate.data.month, lastdate.data.day)
	if datetime.date.today() > reallastdate:
		res = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getcompetitions"})
		if res.status_code != 200:
			return render_template("error.html", err=res.status_code)
		data = res.json()
		for comp in data["competitions"]:
			try:
				comp["multidaystage"]
			except KeyError:
				try:
					datedata = datetime.datetime.strptime(comp["date"], '%Y-%m-%d')
				except:
					continue
				dt=datetime.date(datedata.year, datedata.month, datedata.day)
				if dt >= reallastdate and dt < datetime.date.today():
					event = Eventn.query.filter_by(id = comp["id"]).first()
					if event is None:
						runners = 0
						res2 = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclasses", "comp": str(comp["id"])})
						if res2.status_code != 200:
							return render_template("error.html", err=res2.status_code)
						datac = res2.json()
						for c in datac["classes"]:
							res3 = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclassresults", "comp": str(comp["id"]), "class": c["className"]})
							if res3.status_code != 200:
								return render_template("error.html", err=res3.status_code)
							datar = res3.json()
							runners += len(datar["results"])
							if runners > 20:
								break
						if runners > 20:
							db.session.add(Eventn(id=comp["id"], name=comp["name"], org=comp["organizer"], usersn_id=51, start_date=comp["date"], 
								end_date=comp["date"], location="Unknown", classifn_id=6, link="#", countryn_id=28))			
							db.session.commit()
	lastdate.data = datetime.date.today()
	db.session.commit()
	return redirect("/")		
 	"""

@app.route("/importoneapi", methods=['POST'])
@login_required
def importoneapi():
	link = request.form.get("id")
	try:
		index = link.index("comp=") + len("comp=")
		eventid = int(link[index:index+5])
	except:
		flash(_('Invalid event link!'), "danger")
		return redirect("/")

	resp = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getcompetitioninfo", "comp": eventid})
	if resp.status_code != 200:
		flash(_('Invalid event link!'), "danger")
		return redirect("/")
	comp = resp.json()
	try:
		comp["multidaystage"]
	except KeyError:
		try:
			datedata = datetime.datetime.strptime(comp["date"], '%Y-%m-%d')
		except:
			flash(_('Invalid event!'), "danger")
			return redirect("/")
		dt=datetime.date(datedata.year, datedata.month, datedata.day)
		if dt < datetime.date.today():
			event = Eventn.query.filter_by(id = comp["id"]).first()
			if event is None:
				runners = 0
				res2 = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclasses", "comp": str(comp["id"])})
				if res2.status_code != 200:
					flash(_('Invalid event!'), "danger")
					return redirect("/")
				datac = res2.json()
				for c in datac["classes"]:
					res3 = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclassresults", "comp": str(comp["id"]), "class": c["className"]})
					if res3.status_code != 200:
						flash(_('Not enough results to treat this as a real event.'), "danger")
						return redirect("/")
					datar = res3.json()
					runners += len(datar["results"])
					if runners > 20:
						break
				if runners > 20:
					db.session.add(Eventn(id=comp["id"], name=comp["name"], org=comp["organizer"], usersn_id=51, start_date=comp["date"], 
						end_date=comp["date"], location="Unknown", classifn_id=6, link="#", countryn_id=28))			
					db.session.commit()
					return redirect("/event/" + str(eventid))
				else:
					flash(_('Not enough results to treat this as a real event.'), "danger")
					return redirect("/")
			else:
				flash(_("Event already in the database"), "success")
				return redirect("/event/" + str(eventid))
	flash(_('Invalid event link!'), "danger")
	return redirect("/")
	

# Route to delete all events imported from Liveresultat
# Currently not in the project
"""
@app.route("/deleteapi", methods=['GET'])
@login_required
def deleteapi():
	if session["user"] != 2:
		return redirect("/")
	cc = 0
	for n in range(13862, 17602):
		#eventc = Eventn.query.filter_by(id=n).first()
		#if eventc is not None:
		try:
			Eventn.query.filter_by(id=n).delete()
			cc += 1
			db.session.commit()
		except:
			continue
	flash(str(cc), "success")
	return redirect("/")
"""

# A route reached by submitting the second form on /new. It extracts the neccessary information to store an event in the database from the HTML
# of the event's page on MTFSZ Adatbank, the link to which is provided by the user.
@app.route("/webscrape/", methods=['POST'])
@login_required
def webscrape():
	if conf_required() == 0:
		return redirect("/confirmed")
	eventlink = request.form.get("id")
	if eventlink.endswith("/"):
		temp = eventlink[-5:]
		eventid = temp[:4]
	else:
		eventid = eventlink[-4:]
	
	try:
		int(eventid)
	except:
		flash(_('Invalid event link!'), "danger")
		return redirect("/")
	session2 = requests.Session()
	session2.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.131 Safari/537.36'
	resp = session2.get('http://adatbank.mtfsz.hu/esemeny/show/esemeny_id/' + str(eventid))
	source = resp.text

	if resp.status_code != 200:
		flash(_('Invalid event link!'), "danger")
		return redirect("/")

	eventc = Eventn.query.filter_by(id=eventid).first()
	if eventc is not None:
		flash(_("Event already in the database"), "success")
		return redirect("/event/" + str(eventid))
	
	soup = BeautifulSoup(source, 'lxml')

	content = soup.find("div", {"id": "content"}).contents
	
	fotabla = content[1].contents[7].contents[1].contents[2].contents[3].find_all("tr")

	alsotabla = content[1].contents[7].contents[1].contents[5].contents[3].find_all("tr")

	orszagos = 0
	for row in alsotabla:
		if len(row.contents) > 5:
			imgs = row.contents[5].find_all("img")
			if imgs[2]['alt'] == "Országos" or imgs[2]['alt'] == "Kiemelt":
				orszagos += 1	

	adatok = {"Név:": "Ismeretlen", "Dátum:": "Ismeretlen", "Helyszín:": "Ismeretlen", "Státusz:": "Ismeretlen", "Rendező szervezetek:": "Ismeretlen"}

	for r in fotabla:
		try:
			if r.contents[1].text.strip() == "Rendező szervezetek:":
				adatok[r.contents[1].text.strip()] = r.contents[3].text.strip()
			elif adatok[r.contents[0].text.strip()] == "Ismeretlen":
				adatok[r.contents[0].text.strip()] = r.contents[1].text.strip()			
		except:
			continue
	
	datum = adatok["Dátum:"].split("-")

	if adatok["Név:"].endswith(" OB"):
		classif = 3
	elif orszagos > 0:
		classif = 2
	else:
		classif = 1

	if adatok["Státusz:"] == "Ellenőrzött eredmény" or adatok["Státusz:"] == "Lezajlott" or adatok["Státusz:"] == "Jegyzőkönyv beadva":
		if len(datum) == 1:
			strt = datetime.datetime.strptime(datum[0], '%Y.%m.%d.')
			end = datetime.datetime.strptime(datum[0], '%Y.%m.%d.')
		elif len(datum[1]) == 3:
			strt = datetime.datetime.strptime(datum[0], '%Y.%m.%d')
			end = datetime.datetime.strptime(datum[0][:8] + datum[1], '%Y.%m.%d.')
		else:
			strt = datetime.datetime.strptime(datum[0], '%Y.%m.%d')
			end = datetime.datetime.strptime(datum[0][:5] + datum[1], '%Y.%m.%d.')
		db.session.add(Eventn(id=int(eventid), name=adatok["Név:"], usersn_id=68, start_date=strt, 
							end_date=end, org=adatok["Rendező szervezetek:"], location=adatok["Helyszín:"], classifn_id=classif, link='http://adatbank.mtfsz.hu/esemeny/show/esemeny_id/' + str(eventid), countryn_id=1))			
		db.session.commit()
		return redirect("/event/" + str(eventid))
	return redirect("/")

@babel.localeselector
def get_locale():
	if not request.cookies.get('lang'):
		return request.accept_languages.best_match(app.config['LANGUAGES'])
	else:
		return request.cookies.get('lang')

@app.route('/en')
def en():
	res = make_response(redirect(request.referrer))
	res.set_cookie('lang', 'en')
	return res

@app.route('/hu')
def hu():
	res = make_response(redirect(request.referrer))
	res.set_cookie('lang', 'hu')
	return res	
	
@app.route("/", methods=["GET"])
def index():
	if request.cookies.get('use') and not session.get("user"):
		us = Usersn.query.filter_by(id=request.cookies.get("use")).first()
		session["user"] = us.id
		session["usern"] = us.username
		session["conf"] = us.confirmed
		flash(_('This site uses cookies to store your login information.'), "warning")
		session.modified = True
		return redirect("/")
	#flash(_('This site is currently under development. Some features may not work properly.'), "danger")
	try:
		age = int(request.args.get('age'))
	except:
		age = request.args.get('age')
	try:
		classif = int(request.args.get('classif'))
	except:
		classif = request.args.get('classif')
	try:
		country = int(request.args.get('country'))
	except:
		country = request.args.get('country')
	try:
		fil = int(request.args.get('fil'))
	except:
		fil = request.args.get('fil')
	rated = db.session.execute("""SELECT eventn.id, eventn.name, eventn.start_date, eventn.end_date, eventn.location, classifn.value, countryn.value, Avg(raten.overall_r) AS ovr_avg
				FROM countryn INNER JOIN ((agen INNER JOIN usersn ON agen.id = usersn.agen_id) INNER JOIN ((classifn INNER JOIN eventn ON classifn.id = eventn.classifn_id) INNER JOIN raten ON eventn.id = raten.eventn_id) ON usersn.id = raten.usersn_id) ON countryn.id = eventn.countryn_id
				WHERE (((agen.id)<5))
				GROUP BY eventn.id, eventn.name, eventn.start_date, eventn.end_date, eventn.location, classifn.value, countryn.value
				""")
	unrated = db.session.execute("""SELECT eventn.id, eventn.name, eventn.start_date, eventn.end_date, eventn.location, classifn.value, countryn.value
				FROM countryn INNER JOIN (classifn INNER JOIN eventn ON classifn.id = eventn.classifn_id) ON countryn.id = eventn.countryn_id
				WHERE eventn.id NOT IN (
					SELECT eventn.id
					FROM eventn INNER JOIN raten ON eventn.id = raten.eventn_id )
				""")
	ratd = {}
	if "user" in session:
		command = """SELECT eventn.id, raten.overall_r
				FROM eventn INNER JOIN (usersn INNER JOIN raten ON usersn.id = raten.usersn_id) ON eventn.id = raten.eventn_id
				WHERE (((usersn.id)= {userid}))"""	
		myr = db.session.execute(command.format(userid = session["user"]))
		for i in myr:
			ratd[str(i[0])] = i[1]
	evlist = []
	for row in rated:
		temp = []
		for i in row:
			try:
				date = datetime.date(i.year, i.month, i.day)
				temp.append(date)
			except:
				try:
					temp.append(round(i, 1))
				except:
					temp.append(i)
		temp.append("/event/" + str(row[0]))
		if "user" in session:	
			if str(row[0]) in ratd:
				temp.append(ratd[str(row[0])])
			else:
				temp.append(0)
		else:
			temp.append(-1)
		evlist.append(temp)
	evlist.sort(reverse=True, key=itemgetter(7))
	topev = evlist[:5].copy()
	for row in unrated:
		temp = []
		for i in row:
			try:
				date = datetime.date(i.year, i.month, i.day)
				temp.append(date)
			except:
				temp.append(i)
		temp.append("0 (not rated)")
		temp.append("/event/" + str(row[0]))
		temp.append(0)
		evlist.append(temp)
	evlist.sort(reverse=True, key=itemgetter(3))
	recev = evlist[:5].copy()
	for i in evlist:
		i[2] = i[2].strftime("%d/%m/%Y")
		i[3] = i[3].strftime("%d/%m/%Y")
	filt = [0, 0, 0]
	countries = Countryn.query.order_by(Countryn.value).all()
	classes = Classifn.query.all()
	ages = Agen.query.all()

	lastdate = Util.query.first()
	reallastdate = datetime.date(lastdate.data.year, lastdate.data.month, lastdate.data.day).strftime("%d/%m/%Y")

	if (classif == 0 or classif is None) and (age == 0 or age is None) and (country == 0 or country is None):
		if fil is None or fil == 0:
			return render_template("index.html", lastdate=reallastdate, evlist=evlist, filt=filt, countries= countries, classes=classes, ages=ages, topev = topev, recev = recev, requ='get')
		else:
			return render_template("index.html", lastdate=reallastdate, evlist=evlist, filt=filt, countries= countries, classes=classes, ages=ages, topev = topev, recev = recev, requ='fil')			
	def fillsql(comman):
		if (classif == 0 or classif is None) and (age == 0 or age is None):
			resu = db.session.execute(comman.format(ageid= ">0", classifid= ">0", countryid="=" + str(country)))
		elif (country == 0 or country is None) and (age == 0 or age is None):
			resu = db.session.execute(comman.format(ageid= ">0", countryid= ">0", classifid="=" + str(classif)))
		elif (classif == 0 or classif is None) and (country == 0 or country is None):
			resu = db.session.execute(comman.format(countryid= ">0", classifid= ">0", ageid="=" + str(age)))
		elif classif == 0 or classif is None:
			resu = db.session.execute(comman.format(classifid= ">0", ageid= "=" + str(age), countryid="=" + str(country)))
		elif country == 0 or country is None:
			resu = db.session.execute(comman.format(countryid= ">0", ageid= "=" + str(age), classifid="=" + str(classif)))
		elif age == 0 or age is None:
			resu = db.session.execute(comman.format(ageid= ">0", classifid= "=" + str(classif), countryid="=" + str(country)))
		else:
			resu = db.session.execute(comman.format(ageid= "="+str(age), classifid= "=" + str(classif), countryid="=" + str(country)))
		return resu

	comm = """SELECT eventn.id, eventn.name, eventn.start_date, eventn.end_date, eventn.location, classifn.value, countryn.value, Avg(raten.overall_r) AS ovr_avg
				FROM countryn INNER JOIN ((agen INNER JOIN usersn ON agen.id = usersn.agen_id) INNER JOIN ((classifn INNER JOIN eventn ON classifn.id = eventn.classifn_id) INNER JOIN raten ON eventn.id = raten.eventn_id) ON usersn.id = raten.usersn_id) ON countryn.id = eventn.countryn_id
				WHERE ((agen.id {ageid}) AND (classifn.id {classifid}) AND (countryn.id {countryid}))
				GROUP BY eventn.id, eventn.name, eventn.start_date, eventn.end_date, eventn.location, classifn.value, countryn.value"""
	
	
	comm2 = """SELECT eventn.id, eventn.name, eventn.start_date, eventn.end_date, eventn.location, classifn.value, countryn.value
				FROM countryn INNER JOIN (classifn INNER JOIN eventn ON classifn.id = eventn.classifn_id) ON countryn.id = eventn.countryn_id
				WHERE eventn.id NOT IN (
					SELECT eventn.id
					FROM (agen INNER JOIN usersn ON agen.id = usersn.agen_id) INNER JOIN (eventn INNER JOIN raten ON eventn.id = raten.eventn_id) ON usersn.id = raten.usersn_id
					WHERE (eventn.classifn_id {classifid}) AND (eventn.countryn_id {countryid}) AND (usersn.agen_id {ageid}))
					 AND (classifn.id {classifid}) AND (countryn.id {countryid})"""
	
	rated2 = fillsql(comm)
	unrated2 = fillsql(comm2)

	evlist = []
	for row in rated2:
		temp = []
		for i in row:
			try:
				date = datetime.date(i.year, i.month, i.day)
				temp.append(date.strftime("%d/%m/%Y"))
			except:
				try:
					temp.append(round(i, 1))
				except:
					temp.append(i)
		temp.append("/event/" + str(row[0]))
		if "user" in session:	
			if str(row[0]) in ratd:
				temp.append(ratd[str(row[0])])
			else:
				temp.append(0)
		else:
			temp.append(-1)
		evlist.append(temp)
	for row in unrated2:
		temp = []
		for i in row:
			try:
				date = datetime.date(i.year, i.month, i.day)
				temp.append(date.strftime("%d/%m/%Y"))
			except:
				temp.append(i)
		temp.append("0 (not rated)")
		temp.append("/event/" + str(row[0]))
		temp.append(0)
		evlist.append(temp)
	filt = [classif, country, age]
	return render_template("index.html", lastdate=reallastdate, evlist=evlist, filt=filt, countries= countries, classes=classes, ages=ages, topev = topev, recev = recev, requ='fil')			
	
@app.route("/register", methods=["GET", "POST"])
def register():
	session.clear()
	if request.method == "GET":
		if not request.cookies.get('use'):
			return render_template("register.html")
		else:
			us = Usersn.query.filter_by(id=request.cookies.get("use")).first()
			session["user"] = us.id
			session["usern"] = us.username
			session["conf"] = us.confirmed
			flash(_('This site uses cookies to store your login information.'), "warning")
			session.modified = True
			return redirect("/")
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
		send_email(email, subject, html) ##
		db.session.add(Usersn(username=uname, email=email, pw_hash=generate_password_hash(request.form.get("password")), confirmed = False, agen_id = request.form.get("age")))
		db.session.commit()
		us = Usersn.query.filter_by(username=uname).first()
		session["conf"] = 0
		session["user"] = us.id
		session["usern"] = us.username
		session["confed"]=0
		session.modified = True
		usid = str(us.id)
		if request.form.get("remember") is None:
			res = make_response(redirect("/confirmed"))
			res.set_cookie('use', "0", max_age=0)
			return res
		else:
			resp = make_response(redirect("/confirmed"))
			resp.set_cookie('use', usid, max_age=60*60*24*365*2)
			return resp

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
		flash(_("The email has been sent."), "success")
		return redirect("/login")
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
		if not request.cookies.get('use'):
			return render_template("login.html")
		else:
			us = Usersn.query.filter_by(id=request.cookies.get("use")).first()
			session["user"] = us.id
			session["usern"] = us.username
			session["conf"] = us.confirmed
			flash(_('This site uses cookies to store your login information.'), "warning")
			session.modified = True
			return redirect("/")
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
		usid = str(us.id)
		if request.form.get("remember") is None:
			res = make_response(redirect('/'))
			res.set_cookie('use', "0", max_age=0)
			return res
		else:
			resp = make_response(redirect('/'))
			resp.set_cookie('use', usid, max_age=60*60*24*365*2)
			return resp		

@app.route("/logout")
def logout():
	# Forget any user_id
	session.pop("user", None)
	session.pop("conf", None)
	session.pop("usern", None)
	session.modified = True
	flash(_("Logged out"), "success")
	# Redirect user to login form
	res = make_response(redirect('/login'))
	res.set_cookie('use', "0", max_age=0)
	return res

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
		
@app.route("/selectage", methods=["POST"])
def selectage():
	try:
		age = int(request.form.get("age"))
	except:
		abort(404)
	eventid = request.form.get("eventid")
	eventc = Eventn.query.filter_by(id=eventid).first()
	if eventc is None:
		abort(404)
	rates = Raten.query.filter_by(eventn_id=eventid).all()
	if age == 0:
		ovr_avg = db.session.query(func.avg(Raten.overall_r)).filter(Raten.eventn_id == eventc.id)
		tr_avg = db.session.query(func.avg(Raten.terrain_r)).filter(Raten.eventn_id == eventc.id)
		mcr_avg = db.session.query(func.avg(Raten.map_course_r)).filter(Raten.eventn_id == eventc.id)
		or_avg = db.session.query(func.avg(Raten.org_r)).filter(Raten.eventn_id == eventc.id)
		darab = len(rates)
	else:
		ovr_avg = db.session.query(func.avg(Raten.overall_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == age)	
		tr_avg = db.session.query(func.avg(Raten.terrain_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == age)	
		mcr_avg = db.session.query(func.avg(Raten.map_course_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == age)	
		or_avg = db.session.query(func.avg(Raten.org_r)).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == age)
		darab = db.session.query(Raten.overall_r).join(Usersn).filter(Raten.eventn_id ==eventc.id, Usersn.agen_id == age).count()
	if ovr_avg[0][0] is None:
		ratings = [0]
	else:
		ratings = [str(round(ovr_avg[0][0], 1)), str(round(tr_avg[0][0], 1)), str(round(mcr_avg[0][0], 1)), str(round(or_avg[0][0], 1)), darab]
	return json.dumps({'status':'OK', 'ratings':ratings})

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
	s_date = datetime.date(eventc.start_date.year, eventc.start_date.month, eventc.start_date.day).strftime("%d/%m/%Y")
	e_date = datetime.date(eventc.end_date.year, eventc.end_date.month, eventc.end_date.day).strftime("%d/%m/%Y")
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
	ovr_avg = db.session.query(func.avg(Raten.overall_r)).filter(Raten.eventn_id == eventc.id)
	tr_avg = db.session.query(func.avg(Raten.terrain_r)).filter(Raten.eventn_id == eventc.id)
	mcr_avg = db.session.query(func.avg(Raten.map_course_r)).filter(Raten.eventn_id == eventc.id)
	or_avg = db.session.query(func.avg(Raten.org_r)).filter(Raten.eventn_id == eventc.id)
	darab = len(rates)
	if ovr_avg[0][0] is None:
		ratings.append([0, 0, 0, 0])
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
	classlist = []	
	if int(eventid) > 13000 or int(eventid) == 3:
		if int(eventid) == 3:
			res = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclasses", "comp": "16654"})
		else:	
			res = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclasses", "comp": eventid})
		if res.status_code != 200:
			return render_template("error.html", err=res.status_code)
		data = res.json()
		for i in data["classes"]:
			classlist.append(i["className"])
	return render_template("event.html", evlist=evlist, myrate = myrate, rated = rated, ratings=ratings, comm=comm, mycomm=mycomm, comments=comments, classlist=classlist)

@app.route("/results", methods=["POST"])
@login_required
def results():
	event = Eventn.query.get(request.form.get("eventid"))
	if event is None:
		abort(404)
	if event.id == 3:
		res = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclassresults", "unformattedTimes": "false", "comp": "16654", "class": request.form.get("class")})
	else:	
		res = requests.get("https://liveresultat.orientering.se/api.php", params={"method": "getclassresults", "unformattedTimes": "false", "comp": request.form.get("eventid"), "class": request.form.get("class")})
	if res.status_code != 200:
		return render_template("error.html", err=res.status_code)
	data = res.json()
	return render_template("results.html", data=data, classs=request.form.get("class"), event=event.name)

@socketio.on("nrate")
def nrate(data):
	try:	
		eventid = int(data["eventid"])
		ovr = int(data["ovr"])
		ter = int(data["ter"])
		map = int(data["map"])
		org = int(data["org"])
		comment = data["comment"].strip()
		selected = int(data["selected"])
	except:
		emit("invalide", {"error": _("invalid rating or event"), "user": session["user"]}, broadcast=True)	
	usrate = Raten.query.filter_by(usersn_id=session['user'], eventn_id = eventid).first()
	if usrate is not None:
		emit("invalide", {"error": "already rated"}, broadcast=True)
	else:
		vanecom = 0
		cid =0
		cont =0
		dt = 0
		edit =0
		if len(comment)>0:
			db.session.add(Comment(usersn_id=session["user"], content = comment, eventn_id=eventid, edited = 0))
			com = Comment.query.filter_by(eventn_id = eventid, usersn_id=session["user"]).first()
			db.session.add(Commentrate(comment_id = com.id, usersn_id=session["user"], rating = 1))
			vanecom = 1
			cid = com.id
			cont = com.content
			dt = com.date_time.strftime("%Y-%m-%d %H:%M") + " UTC"
			edit = com.edited
		db.session.add(Raten(eventn_id=eventid, usersn_id=session["user"], overall_r=ovr, terrain_r=ter, map_course_r=map, org_r=org))
		db.session.commit()
		use = Usersn.query.filter_by(id=session['user']).first()
		if selected == 0 or selected == use.agen_id:
			if selected == 0:
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).filter(Raten.eventn_id == eventid)
				tr_avg = db.session.query(func.avg(Raten.terrain_r)).filter(Raten.eventn_id == eventid)
				mcr_avg = db.session.query(func.avg(Raten.map_course_r)).filter(Raten.eventn_id == eventid)
				or_avg = db.session.query(func.avg(Raten.org_r)).filter(Raten.eventn_id == eventid)
				darab = db.session.query(Raten.overall_r).filter(Raten.eventn_id ==eventid).count()
			else:	
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				tr_avg = db.session.query(func.avg(Raten.terrain_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				mcr_avg = db.session.query(func.avg(Raten.map_course_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				or_avg = db.session.query(func.avg(Raten.org_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)
				darab = db.session.query(Raten.overall_r).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected).count()
			emit("new rating", {"eventid": eventid, "selected": selected, "user": session["user"], "username": session["usern"], "change": 1, "vanecom": vanecom, "cid": cid, "comment": cont, "dt": dt, "edit": edit, "ovr": str(round(ovr_avg[0][0], 1)), "ter": str(round(tr_avg[0][0], 1)), "map": str(round(mcr_avg[0][0], 1)), "org": str(round(or_avg[0][0], 1)), "darab": darab, "myovr": ovr, "myter": ter, "mymap": map, "myorg": org}, broadcast=True)
		else:
			emit("new rating", {"eventid": eventid, "selected": selected, "user": session["user"], "username": session["usern"], "change": 0, "vanecom": vanecom, "cid": cid, "comment": cont, "dt": dt, "edit": edit, "myovr": ovr, "myter": ter, "mymap": map, "myorg": org}, broadcast=True)
	
@socketio.on("neditrate")
def neditrate(data):
	try:	
		eventid = int(data["eventid"])
		ovr = int(data["ovr"])
		ter = int(data["ter"])
		map = int(data["map"])
		org = int(data["org"])
		comment = data["comment"].strip()
		selected = int(data["selected"])
	except:
		emit("invalide", {"error": _("invalid rating or event"), "user": session["user"]}, broadcast=True)
	usrate = Raten.query.filter_by(usersn_id=session['user'], eventn_id = eventid).first()
	if usrate is None:
		emit("invalide", {"error": _("not rated"), "user": session["user"]}, broadcast=True)
	else:
		vanecom = 0
		cid = 0
		cont = 0
		dt = 0
		edit = 0
		uscomm = Comment.query.filter_by(usersn_id=session['user'], eventn_id = eventid).first()
		if len(comment)>0:
			if uscomm is None:
				db.session.add(Comment(usersn_id=session["user"], content = comment, eventn_id=eventid, edited = 0))
				uscomm = Comment.query.filter_by(eventn_id = eventid, usersn_id=session["user"]).first()
				db.session.add(Commentrate(comment_id = uscomm.id, usersn_id=session["user"], rating = 1))
				vanecom = 1
			else:
				uscomm.content = comment
				uscomm.date_time = datetime.datetime.utcnow()
				uscomm.edited = 1
				vanecom = 2
			cid = uscomm.id
			cont = uscomm.content
			dt = uscomm.date_time.strftime("%Y-%m-%d %H:%M") + " UTC"
			edit = uscomm.edited
		else:
			if uscomm is not None:
				cid = uscomm.id
				Commentrate.query.filter_by(comment_id =uscomm.id).delete()
				Comment.query.filter_by(usersn_id=session['user'], eventn_id = eventid).delete()
				vanecom = 3
		nuofcomments = db.session.query(Comment.id).filter(Comment.eventn_id == eventid).count()
		usrate.overall_r = ovr
		usrate.terrain_r = ter
		usrate.map_course_r = map
		usrate.org_r =org
		usrate.date_time = datetime.datetime.utcnow()
		db.session.commit()
		use = Usersn.query.filter_by(id=session['user']).first()
		if selected == 0 or selected == use.agen_id:
			if selected == 0:
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).filter(Raten.eventn_id == eventid)
				tr_avg = db.session.query(func.avg(Raten.terrain_r)).filter(Raten.eventn_id == eventid)
				mcr_avg = db.session.query(func.avg(Raten.map_course_r)).filter(Raten.eventn_id == eventid)
				or_avg = db.session.query(func.avg(Raten.org_r)).filter(Raten.eventn_id == eventid)
				darab = db.session.query(Raten.overall_r).filter(Raten.eventn_id ==eventid).count()
			else:	
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				tr_avg = db.session.query(func.avg(Raten.terrain_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				mcr_avg = db.session.query(func.avg(Raten.map_course_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				or_avg = db.session.query(func.avg(Raten.org_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)
				darab = db.session.query(Raten.overall_r).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected).count()
			emit("editedrate", {"eventid": eventid, "user": session["user"], "nuofcomments": nuofcomments, "selected": selected, "username": session["usern"], "change": 1, "vanecom": vanecom, "cid": cid, "comment": cont, "dt": dt, "edit": edit, "ovr": str(round(ovr_avg[0][0], 1)), "ter": str(round(tr_avg[0][0], 1)), "map": str(round(mcr_avg[0][0], 1)), "org": str(round(or_avg[0][0], 1)), "darab": darab, "myovr": ovr, "myter": ter, "mymap": map, "myorg": org}, broadcast=True)
		else:
			emit("editedrate", {"eventid": eventid, "user": session["user"], "nuofcomments": nuofcomments, "selected": selected, "username": session["usern"], "change": 0, "vanecom": vanecom, "cid": cid, "comment": cont, "dt": dt, "edit": edit, "myovr": ovr, "myter": ter, "mymap": map, "myorg": org}, broadcast=True)
	
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
	if session["user"] != 2 and session["user"] != eve.usersn_id and eve.id < 10000:
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
	eevent = Eventn.query.filter_by(id = request.form.get("eventid")).first()
	if session["user"] == 2 and eevent.usersn_id == session["user"]:
		eevent.name = request.form.get("name")
	eevent.start_date = request.form.get("start_date")
	eevent.end_date = request.form.get("end_date")
	eevent.countryn_id =country.id
	eevent.location = request.form.get("location")
	eevent.classifn_id = request.form.get("classif")
	eevent.link = request.form.get("link")
	db.session.commit()
	return redirect(url_for('event', eventid = request.form.get("eventid")))
	
@app.route("/deleteev", methods=["POST"])
@login_required
def deleteev():
	if conf_required() == 0:
		return redirect("/confirmed")
	evnt = Eventn.query.filter_by(id=request.form.get("eventid")).first()
	if session["user"] != 2 and evnt.usersn_id != session["user"]:
		return render_template("error.html", err=_("You're not allowed to delete this event.")), 403
	c = Eventn.query.filter_by(countryn_id = evnt.countryn_id).all()
	Raten.query.filter_by(eventn_id = request.form.get("eventid")).delete()
	comms = Comment.query.filter_by(eventn_id = evnt.id).all()
	for j in comms:
		Commentrate.query.filter_by(comment_id = j.id).delete()
		Comment.query.filter_by(eventn_id = evnt.id).delete()
	Eventn.query.filter_by(id=request.form.get("eventid")).delete()
	if len(c) == 1 and evnt.countryn_id != 28:
		Countryn.query.filter_by(id = evnt.countryn_id).delete()
	db.session.commit()
	return redirect("/events")
	
@socketio.on("deleterate")
def deleterate(data):
	try:	
		eventid = int(data["eventid"])
		selected = int(data["selected"])
	except:
		emit("invalide", {"error": _("invalid rating or event"), "user": session["user"]}, broadcast=True)	
	Raten.query.filter_by(eventn_id = eventid, usersn_id = session['user']).delete()
	comm = Comment.query.filter_by(eventn_id = eventid, usersn_id = session['user']).first()
	vanecom = 0
	comid = 0
	darab = 0
	if comm is not None:
		Commentrate.query.filter_by(comment_id = comm.id).delete()
		Comment.query.filter_by(eventn_id = eventid, usersn_id = session['user']).delete()
		vanecom = 1
		comid = comm.id
	db.session.commit()
	nuofcomments = db.session.query(Comment.id).filter(Comment.eventn_id == eventid).count()
	use = Usersn.query.filter_by(id=session['user']).first()
	if selected == 0 or selected == use.agen_id:
		if selected == 0:
			darab = db.session.query(Raten.overall_r).filter(Raten.eventn_id ==eventid).count()
			if darab > 0:
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).filter(Raten.eventn_id == eventid)
				tr_avg = db.session.query(func.avg(Raten.terrain_r)).filter(Raten.eventn_id == eventid)
				mcr_avg = db.session.query(func.avg(Raten.map_course_r)).filter(Raten.eventn_id == eventid)
				or_avg = db.session.query(func.avg(Raten.org_r)).filter(Raten.eventn_id == eventid)			
		else:	
			darab = db.session.query(Raten.overall_r).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected).count()
			if darab > 0:
				ovr_avg = db.session.query(func.avg(Raten.overall_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				tr_avg = db.session.query(func.avg(Raten.terrain_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				mcr_avg = db.session.query(func.avg(Raten.map_course_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)	
				or_avg = db.session.query(func.avg(Raten.org_r)).join(Usersn).filter(Raten.eventn_id ==eventid, Usersn.agen_id == selected)				
		if darab > 0:
			ovr= str(round(ovr_avg[0][0], 1))
			ter= str(round(tr_avg[0][0], 1))
			map= str(round(mcr_avg[0][0], 1))
			org= str(round(or_avg[0][0], 1))
		else:
			ovr= "0"
			ter= "0"
			map= "0"
			org= "0"
		emit("deletedr", {'user': session["user"], "selected": selected, 'eventid': eventid, "nuofcomments": nuofcomments, "vanecom": vanecom, "comid": comid, "change": 1, "ovr": ovr, "ter": ter, "map": map, "org": org, "darab": darab}, broadcast = True)
	else:
		emit("deletedr", {'user': session["user"], "selected": selected, 'eventid': eventid, "nuofcomments": nuofcomments, "vanecom": vanecom, "comid": comid, "change": 0, "darab": darab}, broadcast=True)

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
	res = make_response(redirect('/'))
	res.set_cookie('use', "0", max_age=0)
	return res

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

@app.errorhandler(500)
def servererror(e):
	return render_template('500.html'), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('error.html', err=e.description), 400