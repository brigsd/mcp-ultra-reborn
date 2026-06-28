"""Budget do loop de iteracao (fase 6).

Controla quando o loop para: numero de iteracoes, alvo de IoU de forma atingido,
ou melhoria minima por iteracao (plateau).
"""


class Budget:
    def __init__(self, max_iterations=3, target_shape_iou=0.92, min_improvement=0.004):
        self.max_iterations = int(max_iterations)
        self.target_shape_iou = float(target_shape_iou)
        self.min_improvement = float(min_improvement)

    @classmethod
    def from_json(cls, data):
        data = data or {}
        return cls(
            max_iterations=data.get("max_iterations", 3),
            target_shape_iou=data.get("target_shape_iou", 0.92),
            min_improvement=data.get("min_improvement", 0.004),
        )

    def to_dict(self):
        return {
            "max_iterations": self.max_iterations,
            "target_shape_iou": self.target_shape_iou,
            "min_improvement": self.min_improvement,
        }
