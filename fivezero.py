"""
    Implements the FiveZero bot orchestrating all the objects to beat everyone at Gomoku
"""

from engine import FiveZeroEngine
from client import GameClient
import configuration as conf

from abc import ABC
import logging


class EventParser(ABC):
    @staticmethod
    def parse(data: list):
        pass


class UserJoinedParser(EventParser):
    @staticmethod
    def parse(data: list):
        game_info, _ = data

        # extracting game information
        game_info = {k: v for k, v in game_info.items() if k in ('password', 'username', 'gameInfo')}

        game_info['color'] = game_info.pop('gameInfo')['color']

        return game_info


class MovePlayedParser(EventParser):
    @staticmethod
    def parse(data: list):
        move, room_name, times = data

        for k1, k2 in zip(
                ('black_time', 'white_time', 'move_timestamp'),  # adding those keys
                ('blackTimeMs', 'whiteTimeMs', 'turnStartDate')  # from those keys existing in the 'times' variable
        ):
            move[k1] = times[k2]

        # room name is mandatory to call the PlayMove method from the client
        move['room_name'] = room_name

        return move


class FiveZeroBot:
    def __init__(self, engine: FiveZeroEngine, client: GameClient):
        self._engine: FiveZeroEngine = engine
        self._client: GameClient = client

        self.events = {
            "GameStarted": self._on_game_started,
            "UserJoined": self._on_user_joined,
            "SettingsChanged": self._on_settings_changed,
            "MovePlayed": self._on_move_played,
            "OnError": self._on_error,
            "PlayerDisqualified": self._on_player_disqualified,
            "GameOver": self._on_game_over,
        }

        # linking events from the client hub to the handlers of our bot
        self._register_events()

        # linking events and parses
        self.parsers = {
            "UserJoined": UserJoinedParser,
            "MovePlayed": MovePlayedParser,
        }

    def _register_events(self):
        """
        Linking client hub events to engine methods
        """
        logging.info(f"Registering events, linking client hub methods to engine handlers")

        for event_name, handler in self.events.items():
            # linking the event to the handler in the client objet directly
            self._client.link_event(event_name, handler)

    def _on_board_update(self, data):
        raise NotImplementedError

    def _on_player_disqualified(self, data):
        pass

    def _on_error(self, data):
        raise NotImplementedError

    def _on_settings_changed(self, data):
        raise NotImplementedError

    def _on_game_started(self, data):
        logging.info(f"Game has started")

    def _on_role_changed(self, data):
        raise NotImplementedError

    def _on_move_played(self, data):
        # parsing game information & player information
        move_data = self.parsers.get("MovePlayed").parse(data)

        engine_move = self._engine.best_move(move_data)

        self._client.play_move(
            room_name=move_data['room_name'],
            row=engine_move[0],
            column=engine_move[1]
        )

    def _on_user_joined(self, data):
        logging.info("User joined the game")

        # parsing game information & player information
        game_info = self.parsers.get("UserJoined").parse(data)

        assert game_info['username'] == conf.USERNAME

        self._engine.set_color(game_info['color'])

    def _on_game_over(self, data):
        raise NotImplementedError
