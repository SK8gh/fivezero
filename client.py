from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.hub.auth_hub_connection import AuthHubConnection
import requests
import logging

# project constants
from configuration import GAME_HUB_URL, USERNAME, LOGIN_URL


class GameClient:
    """
    client objet interacting with the Game Hub API via SignalR
    """
    def __init__(self, password):
        self.token: str = self._login(password)

        self._hub: AuthHubConnection = self._create_hub()

        self.connect()

    def __del__(self):
        # Disconnecting before destroying the object
        self.disconnect()

    @staticmethod
    def _login(password: str) -> str:
        """
        logs on the API and saves the returned token
        """
        response = requests.post(
            LOGIN_URL,
            json={
                "username": USERNAME,
                "password": password,
            }
        )

        # raises an exception if the logging failed
        response.raise_for_status()

        token = response.json()["accessToken"]

        logging.info(f"Successfully logged in as {USERNAME}")

        return token

    def _create_hub(self) -> AuthHubConnection:
        """
        creates and returns the hub object that will let us communicate with the API
        """
        hub = (
            HubConnectionBuilder()
                .with_url(
                GAME_HUB_URL,
                options={
                    "access_token_factory": lambda: self.token
                }
            )
            .build()
        )

        logging.info(f"Successfully created hub connection")

        return hub

    def link_event(self, event_name: str, handler: callable):
        """
        the API sends us events, that we must treat by linking them to handlers
        """
        logging.debug(f"Linking event {event_name} to handler {handler.__name__}")

        self._hub.on(event_name, handler)

    def connect(self):
        logging.info("Connecting to the hub")

        self._hub.start()

    def disconnect(self):
        logging.info("Disconnecting from the hub")

        self._hub.stop()

    def create_room(
        self,
        room_name: str,
        move_time_seconds: int
    ):
        """
        sends a request to the API to create a new Gomoku room
        """
        args = {
            "roomName": room_name,
            "moveTimeSeconds": move_time_seconds
        }

        self._hub.send("CreateTwoPlayerRoom", [args])

        logging.debug(f"Creating two player room using payload: {args}")

    def join_room(
        self,
        room_name: str
    ):
        """
        sends a request to the API to join an existing Gomoku room
        """
        args = {
            "roomName": room_name,
            "joinAs": "Player"
        }

        logging.debug(f"Joining room using payload: {args}")

        self._hub.send("JoinRoom", [args])

    def start_game(self, room_name: str):
        """
        sends a request to the API to start the game assigned to a specific room
        """
        args = {
            "roomName": room_name
        }

        logging.debug(f"Starting game using payload: {args}")

        self._hub.send("StartGame", [args])

    def play_move(
        self,
        room_name: str,
        row: int,
        column: int
    ):
        """
        sends a request to the API to play a move
        """
        args = {
            "roomName": room_name,
            "row": row,
            "column": column
        }

        logging.debug(f"Playing move using payload: {args}")

        self._hub.send("PlayMove", [args])
