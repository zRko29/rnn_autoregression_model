# Physics-masters

This project is meant to explore the possibility of training and RNN to replace the Standard map dynamical system.


- requirements:
    - python >= 3.9
    - pytorch lightning
    - pyyaml
    - tensorboard
    - pandas

- activate venv environment with
source /shared/mari/grandovecu/rnn_generator_env/bin/activate

- install packages in venv environment with
/shared/mari/grandovecu/rnn_generator_env/bin/python3.10 -m pip install package_name

- main functionalities:
  - to run a single training session: /shared/mari/grandovecu/rnn_generator_env/bin/python3.10 trainer.py
  - to run a single parameter update: /shared/mari/grandovecu/rnn_generator_env/bin/python3.10 update.py
  - to run hyperparameter optimizaton: bash main.sh