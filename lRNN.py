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
from utils.ltraining_helper import lModel, Data, Gridsearch, CustomCallback

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
    name = "overfitting_10"
    num_vertices = 2

    gridsearch = Gridsearch(CONFIG_DIR, num_vertices)

    for _ in range(num_vertices):
        params = gridsearch.get_params()

        map = StandardMap(seed=42, params=params)

        datamodule = Data(
            map_object=map,
            train_size=1.0,
            if_plot_data=False,
            if_plot_data_split=False,
            params=params,
        )

        model = lModel(**params)

        logs_path = "logs"

        # **************** callbacks ****************

        tb_logger = TensorBoardLogger(logs_path, name=name, default_hp_metric=False)

        save_path = os.path.join(logs_path, name, "version_" + str(tb_logger.version))

        print(f"Running version_{tb_logger.version}")
        print()

        checkpoint_callback = callbacks.ModelCheckpoint(
            monitor="loss/train",  # careful
            mode="min",
            dirpath=save_path,
            filename="lmodel",
            save_on_train_epoch_end=True,
            save_top_k=1,
        )

        early_stopping_callback = callbacks.EarlyStopping(
            monitor="loss/val",
            mode="min",
            min_delta=1e-7,
            patience=15,
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