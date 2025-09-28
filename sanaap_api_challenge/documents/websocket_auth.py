import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)
User = get_user_model()


class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        user = scope.get("user")
        if user and user.is_authenticated:
            return await self.inner(scope, receive, send)

        try:
            query_string = scope.get("query_string", b"").decode()
            query_params = parse_qs(query_string)

            token_key = None

            if "token" in query_params:
                token_key = query_params["token"][0]

            headers = dict(scope.get("headers", []))
            if not token_key and b"authorization" in headers:
                auth_header = headers[b"authorization"].decode()
                if auth_header.startswith("Token "):
                    token_key = auth_header[6:]  # Remove "Token " prefix
                elif auth_header.startswith("Bearer "):
                    token_key = auth_header[7:]  # Remove "Bearer " prefix

            if token_key:
                user = await self.get_user_from_token(token_key)
                if user:
                    scope["user"] = user
                    logger.debug("WebSocket authenticated user %s via token", user.id)
                    return await self.inner(scope, receive, send)

                scope["user"] = AnonymousUser()
                logger.warning(
                    "Invalid token provided for WebSocket: %s...",
                    token_key[:10],
                )
            else:
                scope["user"] = AnonymousUser()
                logger.debug("No token provided for WebSocket authentication")

        except Exception:
            logger.exception("Error during WebSocket token authentication")
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token_key):
        try:
            token = Token.objects.select_related("user").get(key=token_key)
        except Token.DoesNotExist:
            return None
        else:
            return token.user


def token_auth_middleware_stack(inner):
    return TokenAuthMiddleware(inner)


TokenAuthMiddlewareStack = token_auth_middleware_stack
