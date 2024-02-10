# import os
# from google.colab import drive

# drive.mount('/content/drive')
# os.chdir("/content/drive/My Drive/Work")

import pytorch_lightning as pl
from pytorch_lightning import callbacks
from pytorch_lightning.loggers import TensorBoardLogger
from lightning.pytorch.profilers import SimpleProfiler
import os

from utils.mapping_helper import StandardMap
from utils.classification_helper import Model, Data, Gridsearch, CustomCallback

import warnings

warnings.filterwarnings(
    "ignore", ".*Consider increasing the value of the `num_workers` argument*"
)
warnings.filterwarnings(
    "ignore",
    ".*The number of training batches*",
)

ROOT_DIR = os.getcwd()
CONFIG_DIR = os.path.join(ROOT_DIR, "config")


if __name__ == "__main__":
    # necessary to continue training from checkpoint, else set to None
    version = None
    name = "classification_4"
    num_vertices = 1

    gridsearch = Gridsearch(CONFIG_DIR, num_vertices)

    for _ in range(num_vertices):
        params = gridsearch.get_params()

        map = StandardMap(seed=42, params=params)

        datamodule = Data(
            data_path="data",
            train_size=0.8,
            plot_data=True,
            print_split=True,
            params=params,
            K_upper_lim=params.get("K_upper_lim"),
        )

        model = Model(**params)

        logs_path = "logs"

        # **************** callbacks ****************

        tb_logger = TensorBoardLogger(logs_path, name=name, default_hp_metric=False)

        save_path = os.path.join(logs_path, name, "version_" + str(tb_logger.version))

        print(f"Running version_{tb_logger.version}")
        print()

        checkpoint_callback = callbacks.ModelCheckpoint(
            monitor="acc/val",  # careful
            mode="max",
            dirpath=save_path,
            filename="model",
            save_on_train_epoch_end=True,
            save_top_k=1,
            verbose=False,
        )

        early_stopping_callback = callbacks.EarlyStopping(
            monitor="acc/val",
            mode="max",
            min_delta=1e-4,
            check_on_train_epoch_end=True,
            patience=30,
            verbose=False,
        )

        gradient_avg_callback = callbacks.StochasticWeightAveraging(swa_lrs=1e-3)

        progress_bar_callback = callbacks.TQDMProgressBar(refresh_rate=10)

        profiler_callback = SimpleProfiler(
            dirpath=save_path, filename="profiler_report"
        )

        # **************** trainer ****************

        trainer = pl.Trainer(
            profiler=profiler_callback,
            max_epochs=params.get("epochs"),
            enable_progress_bar=True,
            logger=tb_logger,
            callbacks=[
                checkpoint_callback,
                early_stopping_callback,
                progress_bar_callback,
                # gradient_avg_callback,
                CustomCallback(),
            ],
        )

        trainer.fit(model=model, datamodule=datamodule, ckpt_path=None)