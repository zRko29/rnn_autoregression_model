import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple


class StandardMap:
    """
    A class representing the Standard Map dynamical system.
    """

    def __init__(
        self,
        init_points: int = None,
        steps: int = None,
        K: float = None,
        sampling: str = None,
        seed: bool = None,
        n: int = None,
        params: dict = None,
    ) -> None:
        self.init_points: int = init_points or params.get("init_points")
        self.steps: int = steps or params.get("steps")
        self.K: float = K or params.get("K")
        self.sampling: str = sampling or params.get("sampling")

        self.rng: np.random.Generator = np.random.default_rng(seed=seed)
        self.n: int = n
        self.spectrum: np.ndarray = np.array([])

    def retrieve_data(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.theta_values, self.p_values

    def generate_data(self) -> None:
        theta: np.ndarray
        p: np.ndarray
        theta, p = self._get_initial_points()

        if not isinstance(self.K, list):
            K_list: list[float] = [self.K]
        elif isinstance(self.K, list) and len(self.K) == 1:
            K_list: list[float] = self.K
        elif isinstance(self.K, list) and len(self.K) == 3:
            K_list: list[float] = np.linspace(self.K[0], self.K[1], self.K[2])

        self.theta_values: np.ndarray = np.empty(
            (self.steps, theta.shape[0] * len(K_list))
        )
        self.p_values: np.ndarray = np.empty((self.steps, p.shape[0] * len(K_list)))

        for i, K in enumerate(K_list):
            for step in range(self.steps):
                theta = np.mod(theta + p, 1)
                p = np.mod(p + K / (2 * np.pi) * np.sin(2 * np.pi * theta), 1)
                self.theta_values[
                    step, i * theta.shape[0] : (i + 1) * theta.shape[0]
                ] = theta
                self.p_values[step, i * p.shape[0] : (i + 1) * p.shape[0]] = p

    def _get_initial_points(self) -> Tuple[np.ndarray, np.ndarray]:
        params = [0.01, 0.99, self.init_points]

        if self.sampling == "random":
            theta_init = self.rng.uniform(*params)
            p_init = self.rng.uniform(*params)

        elif self.sampling == "linear":
            theta_init = np.linspace(*params)
            p_init = np.linspace(*params)

        elif self.sampling == "grid":
            params = [0.01, 0.99, int(np.sqrt(self.init_points))]
            theta_init, p_init = np.meshgrid(np.linspace(*params), np.linspace(*params))
            theta_init = theta_init.flatten()
            p_init = p_init.flatten()

        else:
            raise ValueError("Invalid sampling method")

        return theta_init, p_init

    def plot_data(self) -> None:
        plt.figure(figsize=(7, 4))
        plt.plot(self.theta_values, self.p_values, "bo", markersize=0.5)
        plt.xlabel(r"$\theta$")
        plt.ylabel("p")
        plt.xlim(-0.05, 1.05)
        plt.ylim(-0.05, 1.05)
        plt.show()


if __name__ == "__main__":
    map = StandardMap(
        init_points=20, steps=100, sampling="random", K=[0.5, 1.0, 4], seed=42
    )
    map.generate_data()
    map.plot_data()
