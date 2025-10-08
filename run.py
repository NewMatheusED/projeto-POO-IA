from app.flask_config import Config

# Em produção com gevent, precisamos monkey-patch ANTES de qualquer import que use socket/ssl
if Config.PRODUCTION == "true":
    try:
        from gevent import monkey  # type: ignore

        monkey.patch_all()
    except Exception:
        pass

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG_MODE)
