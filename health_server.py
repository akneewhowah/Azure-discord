import time
from aiohttp import web
import config

START_TIME = time.time()


def get_uptime_formatted() -> str:
    elapsed = int(time.time() - START_TIME)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


async def health_handler(request):
    bot = request.app.get("bot")
    is_ready = bot.is_ready() if bot else False
    latency_ms = round(bot.latency * 1000, 2) if (bot and bot.latency) else 0

    return web.json_response(
        {
            "status": "healthy" if is_ready else "starting",
            "bot_user": str(bot.user) if is_ready else None,
            "latency_ms": latency_ms,
            "uptime": get_uptime_formatted(),
            "uptime_seconds": int(time.time() - START_TIME),
            "azure_hosted": config.IS_AZURE,
            "azure_app_name": config.AZURE_APP_NAME,
        }
    )


async def home_handler(request):
    bot = request.app.get("bot")
    bot_name = bot.user.name if (bot and bot.is_ready()) else "Discord Bot"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{bot_name} - Azure Status</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                color: #f8fafc;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
            }}
            .card {{
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(12px);
                border-radius: 16px;
                padding: 2.5rem;
                max-width: 480px;
                width: 90%;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4);
                text-align: center;
            }}
            .badge {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                background: #0284c7;
                color: #fff;
                font-size: 0.85rem;
                font-weight: 600;
                padding: 4px 12px;
                border-radius: 9999px;
                margin-bottom: 1.25rem;
            }}
            .pulse {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #22c55e;
                box-shadow: 0 0 8px #22c55e;
            }}
            h1 {{
                font-size: 1.85rem;
                margin: 0 0 0.5rem 0;
            }}
            p {{
                color: #94a3b8;
                margin-bottom: 1.5rem;
            }}
            .info-box {{
                background: rgba(15, 23, 42, 0.6);
                border-radius: 8px;
                padding: 1rem;
                text-align: left;
                font-size: 0.95rem;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 0.35rem 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            .info-row:last-child {{
                border-bottom: none;
            }}
            .label {{
                color: #64748b;
            }}
            .val {{
                color: #e2e8f0;
                font-weight: 500;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge">
                <span class="pulse"></span>
                <span>Microsoft Azure Cloud Active</span>
            </div>
            <h1>🤖 {bot_name}</h1>
            <p>Your Discord bot is running smoothly in the cloud.</p>
            <div class="info-box">
                <div class="info-row"><span class="label">Platform</span><span class="val">Microsoft Azure</span></div>
                <div class="info-row"><span class="label">Instance</span><span class="val">{config.AZURE_APP_NAME}</span></div>
                <div class="info-row"><span class="label">Uptime</span><span class="val">{get_uptime_formatted()}</span></div>
                <div class="info-row"><span class="label">Health Probe</span><span class="val"><a href="/health" style="color: #38bdf8; text-decoration: none;">/health</a></span></div>
            </div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")


def create_health_app(bot):
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/", home_handler)
    app.router.add_get("/health", health_handler)
    return app
