import gbinder

INTERFACE = "lineageos.waydroid.IMediaPlayers.IMediaPlayersCallback"

TRANSACTION_onCommand = 1

GBINDER_TX_FLAG_ONEWAY = 1

class IMediaPlayersCallback:
    def __init__(self, remote):
        self.remote = remote
        self.client = gbinder.Client(remote, INTERFACE)

    def addDeathHandler(self, handler):
        def local_handler(*args):
            handler(self)
        self.remote.add_death_handler(local_handler)

    def onCommand(self, player_id, command, position_ms):
        request = self.client.new_request()
        request.append_string16(player_id)
        request.append_string16(command)
        request.append_int64(position_ms)
        self.client.transact(TRANSACTION_onCommand, GBINDER_TX_FLAG_ONEWAY, request, lambda *args: None, lambda *args: None)
