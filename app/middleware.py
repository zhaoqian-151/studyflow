from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    """Bound all incoming bodies, including chunked uploads, before multipart parsing.

    Small uploads are buffered deliberately (max 6 MiB); SSE responses are unaffected.
    """

    def __init__(self, app, max_bytes=6 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        pieces, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            piece = message.get("body", b"")
            size += len(piece)
            if size > self.max_bytes:
                return await JSONResponse({"detail": "请求体最多 6 MB"}, status_code=413)(scope, receive, send)
            pieces.append(piece)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": b"".join(pieces), "more_body": False}

        await self.app(scope, replay, send)
