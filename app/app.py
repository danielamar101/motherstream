import logging

logger = logging.getLogger(__name__)

def register_app(app):
    
    from app.api.rtmp_endpoints import rtmp_blueprint
    from app.api.http_endpoints import http_blueprint

    # this initializes the database connection. TODO: Load this earlier
    from app.db.routes.login import login_router
    from app.db.routes.users import user_router
    from app.db.routes.utils import util_router

    app.include_router(rtmp_blueprint)
    app.include_router(http_blueprint)

    app.include_router(login_router)
    app.include_router(user_router)
    app.include_router(util_router)






