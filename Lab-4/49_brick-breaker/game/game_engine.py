import math
import pygame
from .paddle import Paddle
from .ball import Ball
from .brick import Brick
from .SOUND import SoundManager

# Game Engine

WHITE = (255, 255, 255)
BG = (15, 15, 25)
BRICK_COLORS = [
    (200, 60, 60),
    (200, 140, 60),
    (200, 200, 60),
    (80, 180, 80),
    (80, 140, 200),
]

# Maximum angle (from vertical) the ball can leave the paddle at.
# 60 degrees keeps vy at >= 50% of speed, so the ball never goes near-horizontal.
MAX_BOUNCE_ANGLE = math.radians(60)
# Difficulty presets.
#   ball: per-axis starting speed (actual speed = ball * sqrt(2)), px/frame
#   paddle: paddle width in px
# "medium" matches the original game (ball 4, paddle 100).
DIFFICULTIES = {
    "easy":   {"label": "Easy",   "key": "1", "ball": 3.0, "paddle": 140, "note": "slower ball, wider paddle"},
    "medium": {"label": "Medium", "key": "2", "ball": 4.0, "paddle": 100, "note": "default"},
    "hard":   {"label": "Hard",   "key": "3", "ball": 5.5, "paddle": 70,  "note": "faster ball, smaller paddle"},
}


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.rows, self.cols = 5, 8

        self.font = pygame.font.SysFont("Arial", 28)
        self.title_font = pygame.font.SysFont("Arial", 56, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 22)

        self.sounds = SoundManager()  # silent (never crashes) if audio is unavailable

        # Dim overlay drawn behind the end-screen text (created once)
        self.overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 170))

        self._new_game("medium")

    def _new_game(self, difficulty="medium"):
        """Set up (or restart) a fresh game at the given difficulty."""
        self.difficulty = difficulty
        settings = DIFFICULTIES[difficulty]
        self.ball_component = settings["ball"]
        self.ball_speed = self.ball_component * math.sqrt(2)
        paddle_w = settings["paddle"]

        self.paddle = Paddle(self.width // 2 - paddle_w // 2, self.height - 30, paddle_w, 14)

        self.ball = Ball(self.width // 2, self.height - 50, radius=8)
        self.ball.vx, self.ball.vy = self.ball_component, -self.ball_component

        self.bricks = self._build_bricks(self.rows, self.cols)

        self.lives = 3
        self.score = 0
        self.game_over = False
        self.result = None  # "win" or "lose"

    def _build_bricks(self, rows, cols):
        bricks = []
        margin, gap, top = 30, 6, 60
        brick_w = (self.width - margin * 2 - gap * (cols - 1)) // cols
        brick_h = 22
        for r in range(rows):
            for c in range(cols):
                x = margin + c * (brick_w + gap)
                y = top + r * (brick_h + gap)
                bricks.append(Brick(x, y, brick_w, brick_h))
        return bricks

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            self.sounds.toggle_mute()

        # Paddle movement is handled per-frame in handle_input.
        # Here we only react to single key presses on the end-of-game menu.
        if self.game_over and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return
            for name, cfg in DIFFICULTIES.items():
                if event.unicode == cfg["key"]:
                    self._new_game(name)
                    return

    def handle_input(self):
        if self.game_over:
            return
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.paddle.move(-self.paddle.speed, self.width)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.paddle.move(self.paddle.speed, self.width)

    # ------------------------------------------------------------------
    # Collision helpers
    # ------------------------------------------------------------------
    def _bounce_off_paddle(self):
        """Set the ball's outgoing direction based on where it hit the paddle.

        Hit dead centre  -> straight up.
        Hit the left edge -> up and to the left (up to MAX_BOUNCE_ANGLE).
        Hit the right edge -> up and to the right.
        Speed stays constant; only the direction changes.
        """
        paddle_center = self.paddle.x + self.paddle.width / 2
        # offset in [-1, 1]: -1 = far left of paddle, +1 = far right
        offset = (self.ball.x - paddle_center) / (self.paddle.width / 2)
        offset = max(-1.0, min(1.0, offset))

        angle = offset * MAX_BOUNCE_ANGLE
        self.ball.vx = self.ball_speed * math.sin(angle)
        self.ball.vy = -self.ball_speed * math.cos(angle)  # always upward

        # Place the ball on top of the paddle so it can't get stuck inside it
        self.ball.y = self.paddle.y - self.ball.radius

    def _bounce_off_brick(self, brick):
        """Flip vx or vy depending on which face of the brick was hit.

        We measure how far the ball has penetrated each face. The face with the
        smallest penetration is the one the ball actually came through.
        """
        b = self.ball.rect()
        r = brick.rect()

        overlap_left = b.right - r.left      # ball entering from the left
        overlap_right = r.right - b.left     # ball entering from the right
        overlap_top = b.bottom - r.top       # ball entering from the top
        overlap_bottom = r.bottom - b.top    # ball entering from the bottom

        min_x = min(overlap_left, overlap_right)
        min_y = min(overlap_top, overlap_bottom)

        if min_x < min_y:
            # Side hit -> reverse horizontal direction
            if overlap_left < overlap_right:
                self.ball.x -= overlap_left     # push out to the left
                self.ball.vx = -abs(self.ball.vx)
            else:
                self.ball.x += overlap_right    # push out to the right
                self.ball.vx = abs(self.ball.vx)
        else:
            # Top/bottom hit -> reverse vertical direction
            if overlap_top < overlap_bottom:
                self.ball.y -= overlap_top      # push out above
                self.ball.vy = -abs(self.ball.vy)
            else:
                self.ball.y += overlap_bottom   # push out below
                self.ball.vy = abs(self.ball.vy)

    # ------------------------------------------------------------------
    def update(self):
        if self.game_over:
            return

        self.ball.move()

        # Walls (use abs() + clamp so the ball can't jitter inside a wall)
        if self.ball.x - self.ball.radius <= 0:
            self.ball.x = self.ball.radius
            self.ball.vx = abs(self.ball.vx)
            self.sounds.play("wall")
        elif self.ball.x + self.ball.radius >= self.width:
            self.ball.x = self.width - self.ball.radius
            self.ball.vx = -abs(self.ball.vx)
            self.sounds.play("wall")
        if self.ball.y - self.ball.radius <= 0:
            self.ball.y = self.ball.radius
            self.ball.vy = abs(self.ball.vy)
            self.sounds.play("wall")

        # Paddle: only bounce when the ball is travelling downward, otherwise
        # it can re-trigger every frame while still overlapping the paddle.
        if self.ball.vy > 0 and self.ball.rect().colliderect(self.paddle.rect()):
            self._bounce_off_paddle()
            self.sounds.play("paddle")

        # Bricks: at most one brick per frame
        for brick in self.bricks:
            if brick.alive and self.ball.rect().colliderect(brick.rect()):
                brick.alive = False
                self.score += 1
                self._bounce_off_brick(brick)
                self.sounds.play("brick")
                break

        if self.ball.y - self.ball.radius > self.height:
            self.lives -= 1
            if self.lives <= 0:
                self.game_over = True
                self.result = "lose"
                self.sounds.play("lose")
            else:
                self._reset_ball()

        # "not self.game_over" stops a win firing on the same frame as a loss
        if not self.game_over and all(not b.alive for b in self.bricks):
            self.game_over = True
            self.result = "win"
            self.sounds.play("win")

    def _reset_ball(self):
        self.ball.x, self.ball.y = self.width // 2, self.height - 50
        self.ball.vx, self.ball.vy = self.ball_component, -self.ball_component

    def render(self, screen):
        screen.fill(BG)

        pygame.draw.rect(screen, WHITE, self.paddle.rect())
        pygame.draw.circle(screen, WHITE, (int(self.ball.x), int(self.ball.y)), self.ball.radius)

        for i, brick in enumerate(self.bricks):
            if brick.alive:
                row = i // self.cols
                color = BRICK_COLORS[row % len(BRICK_COLORS)]
                pygame.draw.rect(screen, color, brick.rect())

        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        screen.blit(score_text, (10, 10))
        lives_text = self.font.render(f"Lives: {self.lives}", True, WHITE)
        screen.blit(lives_text, (self.width - 130, 10))

        if self.game_over:
            self._render_end_screen(screen)

    def _render_end_screen(self, screen):
        screen.blit(self.overlay, (0, 0))

        if self.result == "win":
            title, color = "YOU WIN!", (80, 220, 100)
        else:
            title, color = "GAME OVER", (230, 70, 70)

        cy = self.height // 2
        lines = [
            (self.title_font, title, color, cy - 120),
            (self.font, f"Final Score: {self.score}", WHITE, cy - 60),
            (self.small_font, "Play again - choose a difficulty:", WHITE, cy - 10),
        ]
        for i, (name, cfg) in enumerate(DIFFICULTIES.items()):
            text = f"[{cfg['key']}] {cfg['label']} - {cfg['note']}"
            if name == self.difficulty:
                text += "  (last played)"
            lines.append((self.small_font, text, WHITE, cy + 30 + i * 30))
        lines.append((self.small_font, "Press ESC to exit", (170, 170, 170), cy + 150))

        for font, text, col, y in lines:
            surf = font.render(text, True, col)
            screen.blit(surf, surf.get_rect(center=(self.width // 2, y)))