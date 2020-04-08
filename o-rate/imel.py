from flask_mail import Message
import app

def send_email(to, subject, template):
	msg = Message(
		subject,
		recipients=[to],
		html=template,
		sender=app.app.config['DEFAULT_MAIL_SENDER'])
	app.mail.send(msg)
