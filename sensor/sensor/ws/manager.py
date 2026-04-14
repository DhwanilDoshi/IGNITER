# F:\sensor\ws\manager.py

class WSManager:
    async def broadcast(self, message: dict):
        print("Broadcast:", message)

ws_manager = WSManager()
