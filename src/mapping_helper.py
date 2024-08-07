import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, List
import pyprind


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
        vertical_band_points: int = 0,
        horizontal_band_points: int = 0,
        seed: bool = None,
        params: dict = None,
    ) -> None:
        self.init_points: int = init_points or params.get("init_points")
        self.steps: int = steps or params.get("steps")
        self.K: float | List[float] = K or params.get("K")
        self.sampling: str = sampling or params.get("sampling")
        self.vertical_band_points: int = vertical_band_points
        self.horizontal_band_points: int = horizontal_band_points

        self.rng: np.random.Generator = np.random.default_rng(seed=seed)
        self.spectrum: np.ndarray = np.array([])

    def retrieve_data(self) -> Tuple[np.ndarray]:
        return self.theta_values, self.p_values

    def generate_data(self) -> None:
        theta_i: np.ndarray
        p_i: np.ndarray
        theta_i, p_i = self._get_initial_points()

        if not isinstance(self.K, list):
            K_list: List[float] = [self.K]
        else:
            if len(self.K) == 3 and isinstance(self.K[2], int):
                K_list: List[float] = np.linspace(*self.K)
            else:
                K_list: List[float] = self.K

        self.theta_values: np.ndarray = np.zeros(
            (self.steps, theta_i.shape[0] * len(K_list))
        )
        self.p_values: np.ndarray = np.zeros((self.steps, p_i.shape[0] * len(K_list)))

        self.theta_values[0] = np.tile(theta_i, len(K_list))
        self.p_values[0] = np.tile(p_i, len(K_list))

        pbar = pyprind.ProgBar(
            len(K_list) * self.steps,
            bar_char="█",
            title="Generating data for Standard Map",
        )

        for i, K in enumerate(K_list):
            theta = theta_i.copy()
            p = p_i.copy()
            for step in range(1, self.steps):
                theta = np.mod(theta + p, 1)
                p = np.mod(p + K / (2 * np.pi) * np.sin(2 * np.pi * theta), 1)
                self.theta_values[
                    step, i * theta_i.shape[0] : (i + 1) * theta_i.shape[0]
                ] = theta
                self.p_values[step, i * p_i.shape[0] : (i + 1) * p_i.shape[0]] = p

                pbar.update()
        print()

    def _get_initial_points(self) -> Tuple[np.ndarray, np.ndarray]:
        params: List = [0.0, 1.0, self.init_points]

        if self.sampling == "random":
            theta_init = self.rng.uniform(*params)
            p_init = self.rng.uniform(*params)

        elif self.sampling == "linear":
            theta_init = np.linspace(*params)
            p_init = np.linspace(*params)

        elif self.sampling == "grid":
            params = [0.0, 1.0, int(np.sqrt(self.init_points))]
            theta_init, p_init = np.meshgrid(np.linspace(*params), np.linspace(*params))
            theta_init = theta_init.flatten()
            p_init = p_init.flatten()

        else:
            raise ValueError("Invalid sampling method")

        thickness = 0.1
        edge_theta_init = np.array([])
        edge_p_init = np.array([])

        if self.vertical_band_points > 0:
            vert_edge_theta = np.concatenate(
                [
                    self.rng.uniform(0.0, thickness, self.vertical_band_points),
                    self.rng.uniform(1.0 - thickness, 1.0, self.vertical_band_points),
                ]
            )
            vert_edge_p = np.concatenate(
                [
                    self.rng.uniform(0.0, 1.0, self.vertical_band_points),
                    self.rng.uniform(0.0, 1.0, self.vertical_band_points),
                ]
            )
            edge_theta_init = np.concatenate((edge_theta_init, vert_edge_theta))
            edge_p_init = np.concatenate((edge_p_init, vert_edge_p))

        if self.horizontal_band_points > 0:
            hor_edge_theta = np.concatenate(
                [
                    self.rng.uniform(0.0, 1.0, self.horizontal_band_points),
                    self.rng.uniform(0.0, 1.0, self.horizontal_band_points),
                ]
            )
            hor_edge_p = np.concatenate(
                [
                    self.rng.uniform(0.0, thickness, self.horizontal_band_points),
                    self.rng.uniform(1.0 - thickness, 1.0, self.horizontal_band_points),
                ]
            )
            edge_theta_init = np.concatenate((edge_theta_init, hor_edge_theta))
            edge_p_init = np.concatenate((edge_p_init, hor_edge_p))

            theta_init = np.concatenate((theta_init, edge_theta_init))
            p_init = np.concatenate((p_init, edge_p_init))

        return theta_init, p_init

    def plot_data(self) -> None:
        plt.figure(figsize=(7, 4))
        plt.plot(self.theta_values, self.p_values, "bo", markersize=0.3)
        plt.xlabel(r"$\theta$")
        plt.ylabel("p")
        plt.xlim(-0.05, 1.05)
        plt.ylim(-0.05, 1.05)
        plt.title(f"K = {self.K}")
        plt.show()

    def subplot_data(self) -> None:
        fig, ax = plt.subplots(2, 2, figsize=(8, 7), sharex=True, sharey=True)
        ind = 0
        for i in range(2):
            for j in range(2):
                pts = self.init_points
                ax[i, j].plot(
                    self.theta_values[:, ind * pts : (ind + 1) * pts],
                    self.p_values[:, ind * pts : (ind + 1) * pts],
                    "bo",
                    markersize=0.3,
                )
                ax[i, j].set_title(f"K = {self.K[ind]}")
                if j == 0:
                    ax[i, j].set_ylabel("p")
                if i == 1:
                    ax[i, j].set_xlabel(r"$\theta$")
                ind += 1
        plt.tight_layout()
        plt.savefig("figures/standard_map.png")
        plt.show()


if __name__ == "__main__":
    map = StandardMap(
        init_points=120 * 120,
        steps=1,
        vertical_band_points=5000,
        horizontal_band_points=0,
        sampling="grid",
        K=[0.1],
        seed=42,
    )
    map.generate_data()
    map.plot_data()
