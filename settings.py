import dj_database_url
import config
DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=True)
