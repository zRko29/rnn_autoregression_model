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
    name = "classification_1"
    num_vertices = 1

    gridsearch = Gridsearch(CONFIG_DIR, num_vertices)

    for _ in range(num_vertices):
        params = gridsearch.get_params()

        map = StandardMap(seed=42, params=params)

        datamodule = Data(
            # map_object=map,
            data_path="data/1.0",
            train_size=1.0,
            plot_data=False,
            plot_data_split=False,
            print_split=True,
            params=params,
        )

        model = Model(**params)

        logs_path = "logs"

        # **************** callbacks ****************

        tb_logger = TensorBoardLogger(logs_path, name=name, default_hp_metric=False)

        save_path = os.path.join(logs_path, name, "version_" + str(tb_logger.version))

        print(f"Running version_{tb_logger.version}")
        print()

        checkpoint_callback = callbacks.ModelCheckpoint(
            monitor="acc/train",  # careful
            mode="max",
            dirpath=save_path,
            filename="model",
            save_on_train_epoch_end=True,
            save_top_k=1,
            verbose=False,
        )

        early_stopping_callback = callbacks.EarlyStopping(
            monitor="acc/train",
            mode="max",
            min_delta=1e-3,
            check_on_train_epoch_end=True,
            patience=10,
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
                # early_stopping_callback,
                progress_bar_callback,
                # gradient_avg_callback,
                CustomCallback(),
            ],
        )

        trainer.fit(model=model, datamodule=datamodule, ckpt_path=None)
