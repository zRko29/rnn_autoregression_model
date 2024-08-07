import os
import pytorch_lightning as pl
from src.mapping_helper import StandardMap
from src.data_helper import Data
from src.dmd import DMD
from argparse import ArgumentParser, Namespace
from src.utils import (
    read_yaml,
    get_inference_folders,
    plot_2d,
    plot_heat_map,
    plot_spatial_errors,
)
from typing import Optional, List
import warnings

warnings.filterwarnings(
    "ignore",
    module="pytorch_lightning",
)
import logging

logging.getLogger("pytorch_lightning").setLevel(0)
pl.seed_everything(42, workers=True)


def main(args: Namespace):
    version: Optional[int] = args.version or None
    directory_path: str = "logs/cluster/K01/long_term"
    # directory_path: str = "logs/tests"

    folders = get_inference_folders(directory_path, version)

    for log_path in folders:
        print()
        print(f"log_path: {log_path}")
        params_path: str = os.path.join(log_path, "hparams.yaml")
        params: dict = read_yaml(params_path)

        params_update = {}
        params_update.update({"sampling": "random"})
        params_update.update({"steps": 160})
        params_update.update({"init_points": 50})
        # params_update.update({"acc_threshold": 1.0e-4})

        params.update(params_update)
        maps: List[StandardMap] = [
            StandardMap(seed=42, params=params),
            StandardMap(seed=41, params=params),
        ]
        input_suffixes: list[str] = ["standard", "random1"]

        for map, input_suffix in zip(maps, input_suffixes):

            predictions, _ = inference(args, log_path, params, map, params_update)

            print(
                f"{input_suffix} loss: {predictions['loss'].item():.3e}, accuracy: {predictions['accuracy'].item():.5f}"
            )

            plot_2d(
                predictions["predicted"],
                predictions["targets"],
                show_plot=False,
                plot_lines=True,
                save_path=os.path.join(log_path, input_suffix),
                loss=predictions["loss"].item(),
                accuracy=predictions["accuracy"].item(),
            )

            plot_heat_map(
                predictions["predicted"],
                predictions["targets"],
                save_path=os.path.join(log_path, input_suffix) + "_histogram",
                show_plot=False,
            )

            plot_spatial_errors(
                predictions["predicted"],
                predictions["targets"],
                save_path=os.path.join(log_path, input_suffix) + "_errors",
                show_plot=False,
            )

            # dmd: DMD = DMD([predictions["predicted"], predictions["targets"]])
            # dmd.plot_source_matrix(titles=["Predicted", "Targets"])
            # dmd._generate_dmd_results()
            # dmd.plot_eigenvalues(titles=["Predicted", "Targets"])
            # dmd.plot_abs_values(titles=["Predicted", "Targets"])

        print()
        print("-----------------------------")


def inference(
    args: Namespace,
    log_path: str,
    params: dict,
    map: StandardMap,
    params_update: dict,
) -> tuple[dict, Data]:

    if params.get("rnn_type") == "vanillarnn":
        from src.VanillaRNN import Vanilla as Model
    elif params.get("rnn_type") == "mgu":
        from src.MGU import MGU as Model
    elif params.get("rnn_type") == "resrnn":
        from src.ResRNN import ResRNN as Model

    Model.compile_model = args.compile

    model_path: str = os.path.join(log_path, f"model.ckpt")
    model = Model(**params).load_from_checkpoint(
        model_path, map_location="cpu", **params_update
    )
    model.eval()

    # regression seed to take
    model.regression_seed = params.get("seq_length")

    datamodule: Data = Data(
        map_object=map,
        params=params,
    )

    trainer = pl.Trainer(
        precision=params["precision"],
        enable_progress_bar=False,
        logger=False,
        deterministic=True,
    )

    predictions: dict = trainer.predict(model=model, dataloaders=datamodule)[0]

    return predictions, datamodule


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--version", "-v", nargs="*", type=int, default=None)
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()

    main(args)
