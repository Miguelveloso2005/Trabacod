import httpx

async def iniciar_transaccion(amount: int, buy_order: str, session_id: str, return_url: str):
    url = "https://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.3/transactions"
    headers = {
        "Tbk-Api-Key-Id": "597055555532",             # Código de comercio de prueba
        "Tbk-Api-Key-Secret": "597055555532",         # Clave secreta de prueba (igual al ID)
        "Content-Type": "application/json"
    }
    payload = {
        "buy_order": buy_order,
        "session_id": session_id,
        "amount": amount,
        "return_url": return_url
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

async def confirmar_transaccion(token: str):
    url = f"https://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.3/transactions/{token}"
    headers = {
        "Tbk-Api-Key-Id": "597055555532",
        "Tbk-Api-Key-Secret": "597055555532"
    }

    async with httpx.AsyncClient() as client:
        res = await client.put(url, headers=headers)
        res.raise_for_status()
        return res.json()
