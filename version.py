"""Single source of truth for the Zündpunkt application version.

Update __version__ here; the server, instructor app, and student web UI all
pull from this file (the web UI fetches it at runtime via GET /api/version).
"""

__version__ = "0.3.6"
VERSION = __version__
