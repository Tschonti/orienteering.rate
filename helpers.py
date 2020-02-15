import os
import requests
import urllib.parse
from flask_session import Session
from flask import redirect, render_template, request, session
from functools import wraps

def login_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if session.get("user") is None:
			return redirect("/login")
		return f(*args, **kwargs)
	return decorated_function