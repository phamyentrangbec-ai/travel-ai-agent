"""
Travel AI Agent — Main Entry Point
Claw-a-thon 2026 | GreenNode AgentBase | Track: Chat Agent
"""
import sys
sys.dont_write_bytecode = True

from dotenv import load_dotenv
load_dotenv()

from app import app

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    print(f'\n🌏  Trip Buddy running at: http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False)
