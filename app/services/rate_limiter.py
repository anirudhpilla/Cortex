from redis.asyncio import Redis
from app.config import get_settings

settings = get_settings()
redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


async def check_rate_limit(
    key: str,
    *,
    limit: int,
    window_seconds: str = "60",
) -> None:
    from fastapi import HTTPException, status

    count = await redis_client.execute_command(
        "EVAL",
        RATE_LIMIT_SCRIPT,
        1,
        key,
        window_seconds,
    )

    if int(count) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests; try again shortly",
            headers={"Retry-After": str(window_seconds)},
        )
