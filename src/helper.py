import torch.optim as optim
import pytorch_lightning as pl
import torch
from torch.utils.data import DataLoader
import numpy as np
import matplotlib.pyplot as plt
import time
from datetime import timedelta
import os, yaml
from typing import Tuple

from src.mapping_helper import StandardMap


class Model(pl.LightningModule):
    def __init__(
        self,
        **params: dict,
    ):
        super(Model, self).__init__()
        self.save_hyperparameters()

        self.num_rnn_layers: int = params.get("num_rnn_layers")
        self.num_lin_layers: int = params.get("num_lin_layers")
        self.sequence_type: str = params.get("sequence_type")
        dropout: float = params.get("dropout")
        self.lr: float = params.get("lr")
        self.optimizer: str = params.get("optimizer")

        # ----------------------
        # NOTE: This logic is kept so that variable layer sizes can be reimplemented in the future
        rnn_layer_size: int = params.get("hidden_size")
        lin_layer_size: int = params.get("linear_size")

        self.hidden_sizes: list[int] = [rnn_layer_size] * self.num_rnn_layers
        self.linear_sizes: list[int] = [lin_layer_size] * (self.num_lin_layers - 1)
        # ----------------------

        self.training_step_outputs = []
        self.validation_step_outputs = []

        # Create the RNN layers
        self.rnns = torch.nn.ModuleList([])
        self.rnns.append(torch.nn.RNNCell(2, self.hidden_sizes[0]))
        for layer in range(self.num_rnn_layers - 1):
            self.rnns.append(
                torch.nn.RNNCell(self.hidden_sizes[layer], self.hidden_sizes[layer + 1])
            )

        # Create the linear layers
        self.lins = torch.nn.ModuleList([])
        if self.num_lin_layers == 1:
            self.lins.append(torch.nn.Linear(self.hidden_sizes[-1], 2))
        elif self.num_lin_layers > 1:
            self.lins.append(
                torch.nn.Linear(self.hidden_sizes[-1], self.linear_sizes[0])
            )
            for layer in range(self.num_lin_layers - 2):
                self.lins.append(
                    torch.nn.Linear(
                        self.linear_sizes[layer], self.linear_sizes[layer + 1]
                    )
                )
            self.lins.append(torch.nn.Linear(self.linear_sizes[-1], 2))
        self.dropout = torch.nn.Dropout(p=dropout)

        # takes care of dtype
        self.to(torch.double)

    def _init_hidden(self, shape0: int, hidden_shapes: int) -> list[torch.Tensor]:
        return [
            torch.zeros(shape0, hidden_shape, dtype=torch.double).to(self.device)
            for hidden_shape in hidden_shapes
        ]

    def forward(self, input_t: torch.Tensor) -> torch.Tensor:
        outputs = []
        # h_ts[i].shape = [features, hidden_sizes]
        h_ts = self._init_hidden(input_t.shape[0], self.hidden_sizes)

        for input in input_t.split(1, dim=2):
            input = input.squeeze(2)

            # rnn layers
            h_ts[0] = self.rnns[0](input, h_ts[0])
            h_ts[0] = self.dropout(h_ts[0])
            for i in range(1, self.num_rnn_layers):
                h_ts[i] = self.rnns[i](h_ts[i - 1], h_ts[i])
                h_ts[i] = self.dropout(h_ts[i])

            # linear layers
            output = self.lins[0](h_ts[-1])
            for i in range(1, self.num_lin_layers):
                output = self.lins[i](output)
            # output = torch.relu(self.lins[0](h_ts[-1]))
            # for i in range(1, self.num_lin_layers):
            #     output = torch.relu(self.lins[i](output))

            outputs.append(output)

        return torch.stack(outputs, dim=2)

    def configure_optimizers(self) -> optim.Optimizer:
        if self.optimizer == "adam":
            return optim.Adam(self.parameters(), lr=self.lr, amsgrad=True)
        elif self.optimizer == "rmsprop":
            return optim.RMSprop(self.parameters(), lr=self.lr)
        elif self.optimizer == "sgd":
            return optim.SGD(self.parameters(), lr=self.lr, momentum=0.9, nesterov=True)

    def training_step(self, batch, batch_idx) -> torch.Tensor:
        inputs: torch.Tensor
        targets: torch.Tensor
        inputs, targets = batch

        predicted = self(inputs)
        if self.sequence_type == "many-to-one":
            predicted = predicted[:, :, -1:]
        loss = torch.nn.functional.mse_loss(predicted, targets)
        self.log(
            "loss/train",
            loss,
            on_epoch=True,
            prog_bar=True,
            on_step=False,
            sync_dist=False,
        )
        self.training_step_outputs.append(loss)
        return loss

    def validation_step(self, batch, batch_idx) -> torch.Tensor:
        inputs: torch.Tensor
        targets: torch.Tensor
        inputs, targets = batch

        predicted = self(inputs)
        if self.sequence_type == "many-to-one":
            predicted = predicted[:, :, -1:]
        loss = torch.nn.functional.mse_loss(predicted, targets)
        self.log(
            "loss/val",
            loss,
            on_epoch=True,
            prog_bar=True,
            on_step=False,
            sync_dist=False,
        )
        self.validation_step_outputs.append(loss)
        return loss

    def predict_step(self, batch, batch_idx) -> dict[str, torch.Tensor]:
        predicted: torch.Tensor = batch[:, :, : self.regression_seed]
        targets: torch.Tensor = batch[:, :, self.regression_seed :]

        for i in range(batch.shape[2] - self.regression_seed):
            predicted_value = self(predicted[:, :, i:])[:, :, -1:]
            predicted = torch.cat([predicted, predicted_value], axis=2)

        predicted = predicted[:, :, self.regression_seed :]
        loss = torch.nn.functional.mse_loss(predicted, targets)

        return {"predicted": predicted, "targets": targets, "loss": loss}


class Data(pl.LightningDataModule):
    def __init__(
        self,
        map_object: StandardMap,
        train_size: float,
        plot_data: bool,
        plot_data_split: bool,
        print_split: bool,
        params: dict,
    ) -> None:
        super(Data, self).__init__()
        map_object.generate_data()

        thetas: np.ndarray
        ps: np.ndarray
        thetas, ps = map_object.retrieve_data()

        if plot_data:
            map_object.plot_data()

        self.seq_len: int = params.get("seq_length")
        self.batch_size: int = params.get("batch_size")
        self.shuffle_paths: bool = params.get("shuffle_paths")
        self.shuffle_batches: bool = params.get("shuffle_batches")
        self.shuffle_sequences: bool = params.get("shuffle_sequences")
        sequence_type: str = params.get("sequence_type")

        self.rng: np.random.Generator = np.random.default_rng(seed=42)

        # data.shape = [init_points, 2, steps]
        self.data = np.stack([thetas.T, ps.T], axis=1)

        # first shuffle trajectories and then make sequences
        if self.shuffle_paths:
            self.rng.shuffle(self.data)

        # many-to-many or many-to-one types of sequences
        sequences = self._make_sequences(self.data, type=sequence_type)

        if plot_data_split:
            self.plot_data_split(sequences, train_size)

        xy_pairs = self._make_input_output_pairs(sequences, type=sequence_type)

        t = int(len(xy_pairs) * train_size)
        self.train_data = xy_pairs[:t]
        self.val_data = xy_pairs[t:]

        if print_split:
            print(f"Sequences shape: {sequences.shape}")
            print(
                f"Train data shape: {len(self.train_data)} pairs of shape ({len(self.train_data[0][0][0])}, {len(self.train_data[0][1][0])})"
            )
            if train_size < 1.0:
                print(
                    f"Validation data shape: {len(self.val_data)} pairs of shape ({len(self.val_data[0][0][0])}, {len(self.val_data[0][1][0])})"
                )
            print()

    def _make_sequences(self, data: np.ndarray, type: str) -> np.ndarray:
        init_points: int
        features: int
        steps: int
        init_points, features, steps = data.shape

        if type == "many-to-many":
            # sequences.shape = [init_points*(steps//seq_len), 2, seq_len]
            sequences = np.split(data, steps // self.seq_len, axis=2)

            if not self.shuffle_sequences:
                sequences = np.array(
                    [seq[i] for i in range(init_points) for seq in sequences]
                )
            else:
                sequences = np.concatenate((sequences), axis=0)
                self.rng.shuffle(sequences)
        elif type == "many-to-one":
            if self.seq_len < steps:
                # sequences.shape = [init_points * (steps - seq_len), features, seq_len + 1]
                sequences = np.lib.stride_tricks.sliding_window_view(
                    data, (1, features, self.seq_len + 1)
                )
                sequences = sequences.reshape(
                    init_points * (steps - self.seq_len), features, self.seq_len + 1
                )
            elif self.seq_len == steps:
                sequences = data
        else:
            raise ValueError("Invalid type.")

        return sequences

    def _make_input_output_pairs(self, sequences, type: str) -> list[tuple[np.ndarray]]:
        if type == "many-to-many":
            return [(seq[:, :-1], seq[:, 1:]) for seq in sequences]
        elif type == "many-to-one":
            return [(seq[:, :-1], seq[:, -1:]) for seq in sequences]
        else:
            raise ValueError("Invalid type.")

    def train_dataloader(self) -> DataLoader:
        return DataLoader(
            Dataset(self.train_data),
            batch_size=self.batch_size,
            shuffle=self.shuffle_batches,
        )

    def val_dataloader(self) -> DataLoader:
        return DataLoader(
            Dataset(self.val_data),
            batch_size=2 * self.batch_size,
            shuffle=False,
        )

    def predict_dataloader(self) -> torch.Tensor:
        return torch.tensor(self.data).to(torch.double).unsqueeze(0)

    def plot_data_split(self, dataset: torch.Tensor, train_ratio: float) -> None:
        train_size = int(len(dataset) * train_ratio)
        train_data = dataset[:train_size]
        val_data = dataset[train_size:]
        plt.figure(figsize=(6, 4))
        plt.plot(
            train_data[:, 0, 0],
            train_data[:, 1, 0],
            "bo",
            markersize=2,
            label="Training data",
        )
        plt.plot(
            val_data[:, 0, 0],
            val_data[:, 1, 0],
            "ro",
            markersize=2,
            label="Validation data",
        )
        plt.plot(train_data[:, 0, 1:], train_data[:, 1, 1:], "bo", markersize=0.3)
        plt.plot(val_data[:, 0, 1:], val_data[:, 1, 1:], "ro", markersize=0.3)
        plt.legend()
        plt.show()


class CustomCallback(pl.Callback):
    def __init__(self, print: bool):
        super(CustomCallback, self).__init__()
        self.print = print
        self.min_train_loss = np.inf
        self.min_val_loss = np.inf

    def on_train_start(self, trainer, pl_module):
        trainer.logger.log_hyperparams(
            pl_module.hparams,
            {"metrics/min_val_loss": np.inf, "metrics/min_train_loss": np.inf},
        )

    def on_train_epoch_end(self, trainer, pl_module):
        mean_loss = torch.stack(pl_module.training_step_outputs).mean()
        if mean_loss < self.min_train_loss:
            self.min_train_loss = mean_loss
            pl_module.log(
                "metrics/min_train_loss",
                mean_loss,
                sync_dist=False,
            )
        pl_module.training_step_outputs.clear()

    def on_validation_epoch_end(self, trainer, pl_module):
        mean_loss = torch.stack(pl_module.validation_step_outputs).mean()
        if mean_loss < self.min_val_loss:
            self.min_val_loss = mean_loss
            pl_module.log(
                "metrics/min_val_loss",
                mean_loss,
                sync_dist=False,
            )
        pl_module.validation_step_outputs.clear()

    def on_fit_start(self, trainer, pl_module):
        if self.print:
            print()
            print("Training started!")
            print()
            self.t_start = time.time()

    def on_fit_end(self, trainer, pl_module):
        if self.print:
            print()
            print("Training ended!")
            train_time = time.time() - self.t_start
            print(f"Training time: {timedelta(seconds=train_time)}")
            print()


class Dataset(torch.utils.data.Dataset):
    def __init__(self, data: np.ndarray):
        self.data: np.ndarray = data

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        x, y = self.data[idx]
        x = torch.tensor(x).to(torch.double)
        y = torch.tensor(y).to(torch.double)
        return x, y


class Gridsearch:
    def __init__(self, path: str, use_defaults: bool = False) -> None:
        self.path = path
        self.use_defaults = use_defaults

    def update_params(self) -> dict:
        with open(self.path, "r") as file:
            params: dict = yaml.safe_load(file)
            if not self.use_defaults:
                params = self._update_params(params)

            try:
                del params["gridsearch"]
            except KeyError:
                pass

        return params

    def _update_params(self, params) -> dict:
        # don't use any seed
        rng: np.random.Generator = np.random.default_rng()
        for key, space in params.get("gridsearch").items():
            type = space.get("type")
            if type == "int":
                params[key] = int(rng.integers(space["lower"], space["upper"] + 1))
            elif type == "choice":
                list = space.get("list")
                choice = rng.choice(list)
                try:
                    choice = float(choice)
                except:
                    choice = str(choice)
                params[key] = choice
            elif type == "float":
                params[key] = rng.uniform(space["lower"], space["upper"])
            # print(f"{key} = {params[key]}")

        # to add variable layer size
        # if "layers" in key:
        #         num_layers = params[key]
        #         space = space["layer_sizes"]
        #         layer_type = space["layer_type"] + "_sizes"
        #         params[layer_type] = []
        #         for _ in range(num_layers):
        #             layer_size = rng.integers(space["lower"], space["upper"] + 1)
        #             params[layer_type].append(int(layer_size))
        #             if not space["varied"]:
        #                 params[layer_type][-1] = params[layer_type][0]
        #         if layer_type == "lin_sizes":
        #             params[layer_type] = params[layer_type][:-1]
        # print(f"{layer_type}: {params[layer_type]}")

        return params


def plot_2d(
    predicted: torch.Tensor,
    targets: torch.Tensor,
    show_plot: bool = True,
    save_path: str = None,
    title: str = None,
) -> None:
    predicted = predicted.detach().numpy()
    targets = targets.detach().numpy()
    plt.figure(figsize=(6, 4))
    plt.plot(targets[:, 0, 0], targets[:, 1, 0], "ro", markersize=2, label="targets")
    plt.plot(
        predicted[:, 0, 0],
        predicted[:, 1, 0],
        "bo",
        markersize=2,
        label="predicted",
    )
    plt.plot(targets[:, 0, 1:], targets[:, 1, 1:], "ro", markersize=0.5)
    plt.plot(predicted[:, 0, 1:], predicted[:, 1, 1:], "bo", markersize=0.5)
    plt.legend()
    if title is not None:
        plt.title(f"Loss = {title:.3e}")
    if save_path is not None:
        plt.savefig(save_path + ".pdf")
    if show_plot:
        plt.show()
    else:
        plt.close()
