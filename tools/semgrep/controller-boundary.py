async def unsafe_json(response):
    # ruleid: unbounded-controller-json-decoding
    return await response.json()


async def safe_json(response, async_read_json):
    # ok: unbounded-controller-json-decoding
    return await async_read_json(response)


def unsafe_request(session):
    # ruleid: controller-request-must-disable-redirects
    return session.request("GET", "https://controller.invalid")


def safe_request(session):
    # ok: controller-request-must-disable-redirects
    return session.request(
        "GET", "https://controller.invalid", allow_redirects=False
    )
