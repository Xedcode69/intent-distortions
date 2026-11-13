import time
from collections import OrderedDict,deque
from starlette.responses import JSONResponse

class RequestLimits:
    """Bound request memory and CPU-heavy public verification, including chunked bodies."""
    def __init__(self,app,max_bytes=262144):self.app,self.max_bytes=app,max_bytes;self.windows=OrderedDict()
    async def __call__(self,scope,receive,send):
        if scope["type"]!="http":return await self.app(scope,receive,send)
        path=scope["path"];peer=(scope.get("client") or ("unknown",))[0]
        if path.startswith("/api/v1/verify") or path.endswith("/verify") or path=="/api/v1/receipts":
            now=time.monotonic();key=(peer,"verify")
            window=self.windows.setdefault(key,deque())
            while window and window[0]<now-60:window.popleft()
            if len(window)>=60:return await JSONResponse({"detail":"Verification rate limit exceeded"},429,headers={"Retry-After":"60"})(scope,receive,send)
            window.append(now);self.windows.move_to_end(key)
            while len(self.windows)>4096:self.windows.popitem(last=False)
        chunks=[];size=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect":return
            part=message.get("body",b"");size+=len(part)
            if size>self.max_bytes:return await JSONResponse({"detail":"Request body too large"},413)(scope,receive,send)
            chunks.append(part)
            if not message.get("more_body",False):break
        delivered=False
        async def buffered_receive():
            nonlocal delivered
            if delivered:return await receive()
            delivered=True;return {"type":"http.request","body":b"".join(chunks),"more_body":False}
        async def secure_send(message):
            if message["type"]=="http.response.start":
                headers=list(message.get("headers",[]));headers.extend([(b"x-content-type-options",b"nosniff"),(b"referrer-policy",b"no-referrer"),(b"x-frame-options",b"DENY")])
                if not any(k.lower()==b"cache-control" for k,v in headers):headers.append((b"cache-control",b"no-store"))
                message={**message,"headers":headers}
            await send(message)
        await self.app(scope,buffered_receive,secure_send)

def remove_demo_routes(app):
    app.router.routes[:]=[route for route in app.router.routes if not getattr(route,"path","").startswith("/api/v1/demo")]
    app.openapi_schema=None
