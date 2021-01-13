import logging
import threading

from TwitchChannelPointsMiner.classes.WebSocketsPool import WebSocketsPool
from TwitchChannelPointsMiner.classes.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.classes.Streamer import Streamer
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.Exceptions import StreamerDoesNotExistException

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - [%(funcName)s]: %(message)s", datefmt="%d/%m/%y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class TwitchChannelPointsMiner:
    def __init__(
        self,
        username: str,
        predictions: bool = True,
        raid: bool = True,
    ):
        self.twitch = Twitch(username)
        self.predictions = predictions
        self.raid = raid
        self.streamers = []
        self.minute_watcher_thread = None
        self.ws_pool = None

    def mine(self, streamers: list = []):
        self.run(streamers)

    def run(self, streamers: list = []):
        self.twitch.login()

        for streamer_username in streamers:
            streamer_username.lower().strip()
            try:
                channel_id = self.twitch.get_channel_id(streamer_username)
                streamer = Streamer(streamer_username, channel_id)
                self.streamers.append(streamer)
            except StreamerDoesNotExistException:
                logger.info(f"😞  Streamer {streamer_username} does not exist")

        for streamer in self.streamers:
            self.twitch.load_channel_points_context(streamer)
            self.twitch.check_streamer_online(streamer)
            # logger.info(streamer)

        self.minute_watcher_thread = threading.Thread(
            target=self.twitch.send_minute_watched_events, args=(self.streamers,)
        )
        self.minute_watcher_thread.start()

        self.ws_pool = WebSocketsPool(twitch=self.twitch, streamers=self.streamers)
        topics = [
            PubsubTopic(
                "community-points-user-v1", user_id=self.twitch.twitch_login.get_user_id()
            )
        ]
        for streamer in self.streamers:
            topics.append(PubsubTopic("video-playback-by-id", streamer=streamer))

            if self.raid is True:
                topics.append(PubsubTopic("raid", streamer=streamer))

            if self.predictions is True:
                topics.append(PubsubTopic("predictions-channel-v1", streamer=streamer))

        for topic in topics:
            self.ws_pool.submit(topic)
