"""The JSON API for the snake game."""
from snake.game import Game

game = Game()


def handle(method, path, body):
    global game
    if method == "GET" and path == "/api/state":
        return 200, game.state()
    if method == "POST" and path == "/api/reset":
        game = Game()
        return 200, game.state()
    if method == "POST" and path == "/api/step":
        game.step()
        return 200, game.state()
    if method == "POST" and path == "/api/turn":
        direction = (body or {}).get("direction")
        try:
            game.turn(direction)
        except ValueError as exc:
            return 400, {"error": str(exc)}
        return 200, game.state()
    return 404, {"error": f"no route {method} {path}"}
