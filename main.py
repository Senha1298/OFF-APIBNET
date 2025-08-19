import os
from app import app

if __name__ == "__main__":
    # Configuração para produção (Heroku) e desenvolvimento
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
