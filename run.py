import os

# Monkey patch ANTES de qualquer import que use socket/ssl/threading
# Isso deve ser a PRIMEIRA coisa no arquivo para evitar warnings
if os.getenv("PRODUCTION") == "true":
    try:
        from gevent import monkey  # type: ignore
        # Patch tudo, incluindo SSL e threading
        monkey.patch_all(ssl=True, aggressive=True)
    except Exception:
        pass

from app.flask_config import Config
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG_MODE)
