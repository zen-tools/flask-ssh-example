from flask import Flask

__all__ = 'app'.split()

app = Flask(__name__)
from . import routes  # NOQA

app.config['SSH_USERNAME'] = "root"
app.config['SSH_HOSTNAME'] = "example.com"
app.config['SSH_PRIV_KEY'] = """
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
"""
