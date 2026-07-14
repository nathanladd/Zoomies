"""Pure, side-effect-free constants shared across the server and the instructor
client. Keep this module import-safe (no filesystem/env work) so the thin
instructor app — which may point at a remote server — can import it without
triggering server-side setup. Runtime path/config lives in server.config.
"""

# Per-question answer time (seconds).
TIME_DEFAULT = 20
TIME_MIN = 5
TIME_MAX = 120
