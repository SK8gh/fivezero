"""
    Implements the FiveZero bot orchestrating all the objects to beat everyone at Gomoku
"""

from engine import FiveZeroEngine
from client import GameClient
from utils import Move, Board
from datetime import datetime
import configuration as conf
import cProfile

from abc import ABC
import logging

profiler = cProfile.Profile()
profiler.enable()


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

        if 'gameInfo' not in game_info:
            return

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

        logging.debug(f"Received {move['color'].lower()} move: [{move['row']}, {move['column']}]")

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

        self._client.hub.on_error(self._on_error)

    def _on_board_update(self, data):
        raise NotImplementedError

    def _on_player_disqualified(self, data):
        pass

    def _on_error(self, data):
        raise NotImplementedError

    def _on_settings_changed(self, data):
        pass

    def _on_game_started(self, data):
        logging.info(f"Game has started")

    def _on_role_changed(self, data):
        raise NotImplementedError

    def _on_move_played(self, data):
        """
        called when a move is played on the board
        """
        # parsing game information & player information
        move_data = self.parsers.get("MovePlayed").parse(data)

        # extracting the color of the move
        move_color = move_data['color'].upper()

        if conf.Colors[move_color] == self._engine.color:
            # Engine received its own move as an update
            return

        # extracting the move made by the opponent from the parsed move data
        opponent_move = Move(
            index=Board.index(move_data['row'], move_data['column']),
            color=conf.Colors[move_color].value
        )

        # Playing the move received from the other play
        self._engine.board.move(opponent_move)

        # computing the engine move
        engine_move: Move = self._engine.search(
            # previous move timestamp, used to compute the deadline timestamp at which the engine must answer
            move_timestamp=datetime.fromisoformat(move_data['move_timestamp'])
        )

        self._engine.board.move(engine_move)

        self._client.play_move(
            move=engine_move,
            room=move_data['room_name']
        )

        self._engine.board.print()

    def _on_user_joined(self, data):
        logging.info("User joined the game")

        # parsing game information & player information
        game_info = self.parsers.get("UserJoined").parse(data)

        assert game_info['username'] == conf.USERNAME

        engine_color: str = game_info['color']

        logging.info(f"FiveZero plays {engine_color}")

        color_int = conf.Colors[engine_color.upper()]

        self._engine.set_color(color_int)

    def _on_game_over(self, data):
        logging.info(f"Game ended: {data[0]}! Disabling profiler")

        profiler.disable()

        logging.info(f"Dumping statistics")
        profiler.dump_stats("fivezero.prof")
