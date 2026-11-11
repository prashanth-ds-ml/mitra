"""Snake: the board, the moves and the rules."""
import random

MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


class Game:
    def __init__(self, width=20, height=20, seed=None):
        self.width, self.height = width, height
        self.rng = random.Random(seed)
        cx, cy = width // 2, height // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = "right"
        self.score = 0
        self.over = False
        self.food = None
        self.place_food()

    def place_food(self):
        free = [(x, y) for x in range(self.width) for y in range(self.height) if (x, y) not in self.snake]
        self.food = self.rng.choice(free) if free else None

    def turn(self, direction):
        if direction not in MOVES:
            raise ValueError(f"unknown direction: {direction}")
        if direction != OPPOSITE[self.direction]:
            self.direction = direction

    def step(self):
        if self.over:
            return
        dx, dy = MOVES[self.direction]
        hx, hy = self.snake[0]
        head = (hx + dx, hy + dy)
        if not (0 <= head[0] < self.width and 0 <= head[1] < self.height):
            self.over = True
            return
        eating = head == self.food
        body = self.snake if eating else self.snake[:-1]
        if head in body:
            self.over = True
            return
        self.snake = [head] + body
        if eating:
            self.score += 1
            self.place_food()

    def state(self):
        return {
            "width": self.width,
            "height": self.height,
            "snake": [list(c) for c in self.snake],
            "food": list(self.food) if self.food else None,
            "score": self.score,
            "over": self.over,
            "direction": self.direction,
        }
