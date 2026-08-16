from dataclasses import dataclass, field


@dataclass
class ForearmResult:
    angle: float | None = None
    tracking: bool = False
    events: list = field(default_factory=list)   # future: mode-switch / click events


class ForearmController:

    def update(self, landmarks, angle) -> ForearmResult:
        if not landmarks:
            return ForearmResult(tracking=False)
        return ForearmResult(angle=angle, tracking=True)

    def close(self):
        pass
