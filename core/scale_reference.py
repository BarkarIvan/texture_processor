from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleReference:
    length_value: float
    unit_key: str = "m"

    @staticmethod
    def allowed_units():
        return {"m", "cm10", "cm1"}

    def normalize_unit(self) -> str:
        return self.unit_key if self.unit_key in self.allowed_units() else "m"

    def to_meters(self) -> float:
        factors = {"m": 1.0, "cm10": 0.1, "cm1": 0.01}
        value = max(1e-6, float(self.length_value))
        return value * factors[self.normalize_unit()]
